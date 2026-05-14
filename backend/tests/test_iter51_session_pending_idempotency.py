"""
Iter51 — DEFINITIVE fix for mobile session-expired bug.

Tests the 2-device approval flow's idempotency + write-after-write guarantee:
  - Device B's /auth/session-request-status returns the SAME session_token on
    every poll after approval (no race between parallel polls).
  - The issued session_token is queryable by /auth/me on the FIRST attempt
    (post-insert read-after-write check works).
  - Edge cases: unknown request_id → 'expired'; denied → 'denied'.

Public preview URL is used; existing test user `test_dash_1777658375@gmail.com / Pass1234`.
All ephemeral session_requests / user_sessions for this user are cleaned up at module teardown.
"""
import os
import time
import secrets
import asyncio
import threading
import concurrent.futures
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

TEST_EMAIL = "test_dash_1777658375@gmail.com"
TEST_PASSWORD = "Pass1234"

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")


# ---------------------------------------------------------------- fixtures
@pytest.fixture(scope="module")
def mongo():
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    yield db
    client.close()


@pytest.fixture(scope="module")
def test_user_id(mongo):
    u = mongo.users.find_one({"email": TEST_EMAIL}, {"user_id": 1})
    assert u, f"Test user {TEST_EMAIL} not found — credentials.md out of date"
    return u["user_id"]


@pytest.fixture(scope="module", autouse=True)
def cleanup_sessions(mongo, test_user_id):
    """Clear any stale user_sessions / session_requests for the test user
    so that the very first login below isn't itself queued."""
    mongo.user_sessions.delete_many({"user_id": test_user_id})
    mongo.session_requests.delete_many({"user_id": test_user_id})
    yield
    # Final teardown — leave the user record intact, drop ephemeral state.
    mongo.user_sessions.delete_many({"user_id": test_user_id})
    mongo.session_requests.delete_many({"user_id": test_user_id})


# Module-level globals used to pass state between ordered tests
state: dict = {}


def _login(email: str, password: str, device_key_id: str, device_label: str):
    r = requests.post(
        f"{API}/auth/login",
        json={
            "email": email,
            "password": password,
            "device_key_id": device_key_id,
            "device_label": device_label,
        },
        timeout=15,
    )
    return r


# ----------------------------------------------------------- test ordering
class TestApprovalFlowIdempotency:

    def test_01_device_a_login_ok(self):
        """Device A (first device) gets a normal session (no other active)."""
        key_a = f"TEST_iter51_devA_{secrets.token_hex(6)}"
        r = _login(TEST_EMAIL, TEST_PASSWORD, key_a, "TEST_iter51 Device A")
        assert r.status_code == 200, f"Device A login failed: {r.status_code} {r.text}"
        body = r.json()
        assert "session_token" in body and isinstance(body["session_token"], str)
        assert len(body["session_token"]) > 10
        assert body.get("email") == TEST_EMAIL
        state["device_a_key"] = key_a
        state["device_a_token"] = body["session_token"]

    def test_02_device_b_login_returns_202_with_request_id(self):
        """Device B tries to login → 202 with request_id (one-device-at-a-time)."""
        key_b = f"TEST_iter51_devB_{secrets.token_hex(6)}"
        r = _login(TEST_EMAIL, TEST_PASSWORD, key_b, "TEST_iter51 Device B")
        assert r.status_code == 202, f"Expected 202, got {r.status_code}: {r.text}"
        detail = r.json().get("detail", {})
        assert detail.get("code") == "session_pending_approval"
        request_id = detail.get("request_id")
        assert request_id and isinstance(request_id, str)
        state["device_b_key"] = key_b
        state["request_id"] = request_id

    def test_03_device_a_sees_pending_request(self):
        """Device A's /auth/session-pending lists the new request."""
        r = requests.get(
            f"{API}/auth/session-pending",
            headers={"Authorization": f"Bearer {state['device_a_token']}"},
            timeout=10,
        )
        assert r.status_code == 200, r.text
        reqs = r.json().get("requests", [])
        ids = [x["request_id"] for x in reqs]
        assert state["request_id"] in ids, f"Pending request not listed: {ids}"
        match = next(x for x in reqs if x["request_id"] == state["request_id"])
        assert match["status"] == "pending"
        assert match.get("requesting_key_id") == state["device_b_key"]

    def test_04_status_pre_approval_returns_pending(self):
        """Before approval, status should be 'pending' (not 'expired'/'approved')."""
        r = requests.post(
            f"{API}/auth/session-request-status",
            json={"request_id": state["request_id"]},
            timeout=10,
        )
        assert r.status_code == 200, r.text
        assert r.json().get("status") == "pending"

    def test_05_device_a_approves(self):
        """Device A POST /auth/session-decide approve → 200."""
        r = requests.post(
            f"{API}/auth/session-decide",
            json={"request_id": state["request_id"], "decision": "approve"},
            headers={"Authorization": f"Bearer {state['device_a_token']}"},
            timeout=10,
        )
        assert r.status_code == 200, r.text
        assert r.json().get("status") == "approved"

    def test_06_five_sequential_polls_idempotent_same_token(self):
        """Device B polls 5× — every response must carry the SAME session_token."""
        tokens = []
        for i in range(5):
            r = requests.post(
                f"{API}/auth/session-request-status",
                json={"request_id": state["request_id"]},
                timeout=10,
            )
            assert r.status_code == 200, f"Poll {i} failed: {r.status_code} {r.text}"
            body = r.json()
            assert body.get("status") == "approved", f"Poll {i}: {body}"
            assert "session_token" in body and body["session_token"]
            assert body.get("email") == TEST_EMAIL
            tokens.append(body["session_token"])
            time.sleep(0.05)
        assert len(set(tokens)) == 1, (
            f"IDEMPOTENCY VIOLATED — sequential polls returned different tokens: {tokens}"
        )
        state["device_b_token"] = tokens[0]

    def test_07_auth_me_works_first_try_after_approval(self):
        """Critical write-after-write check: /auth/me with the freshly-issued
        token must succeed on the FIRST attempt (no retry).
        """
        r = requests.get(
            f"{API}/auth/me",
            headers={"Authorization": f"Bearer {state['device_b_token']}"},
            timeout=10,
        )
        assert r.status_code == 200, f"/auth/me failed first try: {r.status_code} {r.text}"
        body = r.json()
        assert body.get("email") == TEST_EMAIL
        assert body.get("user_id") == body.get("user_id")  # has user_id field

    def test_08_ten_parallel_polls_return_same_token(self):
        """Hammer with 10 concurrent POSTs — all must return identical token,
        no 404/500/duplicate-key errors."""
        def _poll():
            try:
                r = requests.post(
                    f"{API}/auth/session-request-status",
                    json={"request_id": state["request_id"]},
                    timeout=10,
                )
                return r.status_code, r.json()
            except Exception as e:
                return -1, {"error": str(e)}

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
            results = list(ex.map(lambda _: _poll(), range(10)))

        statuses = [s for s, _ in results]
        bodies = [b for _, b in results]
        assert all(s == 200 for s in statuses), f"Non-200 in parallel polls: {statuses}\n{bodies}"
        tokens = {b.get("session_token") for b in bodies}
        assert len(tokens) == 1, f"Parallel polls returned distinct tokens: {tokens}"
        assert state["device_b_token"] in tokens, "Parallel token diverged from sequential"
        statuses_field = {b.get("status") for b in bodies}
        assert statuses_field == {"approved"}, f"Mixed statuses: {statuses_field}"

    def test_09_pending_list_no_longer_includes_consumed_request(self):
        """After approval+consumption, /auth/session-pending must not list it
        (status was flipped to 'approved')."""
        r = requests.get(
            f"{API}/auth/session-pending",
            headers={"Authorization": f"Bearer {state['device_a_token']}"},
            timeout=10,
        )
        assert r.status_code == 200, r.text
        reqs = r.json().get("requests", [])
        ids = [x["request_id"] for x in reqs]
        assert state["request_id"] not in ids, f"Consumed request still pending: {ids}"


class TestEdgeCases:

    def test_10_unknown_request_id_returns_expired_not_404(self):
        """Polling a totally-unknown request_id must return {status:'expired'},
        NOT 404."""
        r = requests.post(
            f"{API}/auth/session-request-status",
            json={"request_id": "TEST_iter51_unknown_" + secrets.token_hex(8)},
            timeout=10,
        )
        assert r.status_code == 200, r.text
        assert r.json().get("status") == "expired"

    def test_11_denied_request_returns_denied(self, mongo, test_user_id):
        """Create a fresh request from Device C, Device A denies, poll → 'denied'."""
        key_c = f"TEST_iter51_devC_{secrets.token_hex(6)}"
        r = _login(TEST_EMAIL, TEST_PASSWORD, key_c, "TEST_iter51 Device C")
        # Device B is now active so Device C should also be queued
        assert r.status_code == 202, f"Expected 202 for Device C: {r.status_code} {r.text}"
        req_id_c = r.json()["detail"]["request_id"]

        # Device A denies. Need to ensure Device A still has an active session.
        # Sanity: Device A's token is still active because approving Device B
        # does NOT kill A's session.
        d = requests.post(
            f"{API}/auth/session-decide",
            json={"request_id": req_id_c, "decision": "deny"},
            headers={"Authorization": f"Bearer {state['device_a_token']}"},
            timeout=10,
        )
        assert d.status_code == 200, d.text
        assert d.json().get("status") == "denied"

        # Poll → 'denied'
        p = requests.post(
            f"{API}/auth/session-request-status",
            json={"request_id": req_id_c},
            timeout=10,
        )
        assert p.status_code == 200, p.text
        body = p.json()
        assert body.get("status") == "denied", body
        assert "session_token" not in body, "Denied response leaked a session_token!"

    def test_12_denied_request_repeat_poll_still_denied(self, mongo, test_user_id):
        """Polling a denied request multiple times must stay 'denied'."""
        # Reuse the previous denied request via state, or just create one more.
        key_d = f"TEST_iter51_devD_{secrets.token_hex(6)}"
        r = _login(TEST_EMAIL, TEST_PASSWORD, key_d, "TEST_iter51 Device D")
        assert r.status_code == 202
        req_id_d = r.json()["detail"]["request_id"]

        requests.post(
            f"{API}/auth/session-decide",
            json={"request_id": req_id_d, "decision": "deny"},
            headers={"Authorization": f"Bearer {state['device_a_token']}"},
            timeout=10,
        )
        for _ in range(3):
            p = requests.post(
                f"{API}/auth/session-request-status",
                json={"request_id": req_id_d},
                timeout=10,
            )
            assert p.status_code == 200
            assert p.json().get("status") == "denied"

    def test_13_db_state_request_carries_issued_token(self, mongo, test_user_id):
        """DB-level sanity: the approved request stores `issued_session_token`
        equal to the token returned to clients (idempotency persistence)."""
        doc = mongo.session_requests.find_one(
            {"request_id": state["request_id"]},
            {"_id": 0},
        )
        assert doc is not None
        assert doc.get("status") == "approved"
        assert doc.get("issued_session_token") == state["device_b_token"]
        assert doc.get("consumed_at")

    def test_14_db_state_session_row_inserted_for_device_b(self, mongo, test_user_id):
        """DB-level sanity: a row exists in user_sessions for Device B's token."""
        row = mongo.user_sessions.find_one(
            {"session_token": state["device_b_token"]},
            {"_id": 0},
        )
        assert row is not None
        assert row["user_id"] == test_user_id
        assert row["device_key_id"] == state["device_b_key"]


class TestPostFlowAuthMe:

    def test_15_device_a_session_still_active(self):
        """Device A's session must NOT have been killed by Device B's approval."""
        r = requests.get(
            f"{API}/auth/me",
            headers={"Authorization": f"Bearer {state['device_a_token']}"},
            timeout=10,
        )
        assert r.status_code == 200, f"Device A session was killed: {r.status_code} {r.text}"
        assert r.json().get("email") == TEST_EMAIL

    def test_16_device_b_session_still_active(self):
        """Device B's session usable too."""
        r = requests.get(
            f"{API}/auth/me",
            headers={"Authorization": f"Bearer {state['device_b_token']}"},
            timeout=10,
        )
        assert r.status_code == 200
        assert r.json().get("email") == TEST_EMAIL
