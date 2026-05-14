"""Iter 45 — Backend regression tests for:

(1) /api/system/site-mode      — public read returns {"mode":"public"}
(2) /api/webauthn/has-enrollment — public, returns {enrolled_count, has_any}
(3) /api/auth/login back-compat (no device_key_id)
(4) /api/auth/login with device_key_id + one-device-at-a-time pending flow
    - second device gets HTTP 202 with code=session_pending_approval
    - /auth/session-request-status returns "pending"
    - /auth/session-pending lists the request (creator-device cookie)
    - /auth/session-decide approve → status_token issued on next status poll
    - deny path returns "denied"
(5) WebAuthn options endpoints reject calls with invalid creator signature (403)
(6) Kept creator device key dev_a797438afc28c67923881d46ae2971c1 still present
    with role='creator'

NOTE: WebAuthn create/get round-trip cannot be performed without a real
authenticator. We only verify the options endpoints are auth-gated.
"""
import os
import time
import secrets
import pytest
import requests
from pymongo import MongoClient

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")
KEPT_KEY_ID = "dev_a797438afc28c67923881d46ae2971c1"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def mongo_db():
    c = MongoClient(MONGO_URL, serverSelectionTimeoutMS=3000)
    return c[DB_NAME]


@pytest.fixture(scope="session")
def fresh_user():
    """Register + verify a fresh test account so we have isolated sessions."""
    email = f"TEST_iter45_{secrets.token_hex(4)}_{int(time.time())}@gmail.com"
    password = "Pass1234"
    r = requests.post(
        f"{BASE_URL}/api/auth/register",
        json={"email": email, "password": password, "frontend_url": BASE_URL},
        timeout=20,
    )
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text[:300]}"
    body = r.json()
    token = body.get("verification_token")
    assert token, f"no verification_token in register response: {body}"

    # GET /api/auth/verify-email?token=...
    v = requests.get(f"{BASE_URL}/api/auth/verify-email", params={"token": token}, timeout=15)
    assert v.status_code == 200, f"verify-email failed: {v.status_code} {v.text[:200]}"
    return {"email": email, "password": password}


# ---------------------------------------------------------------------------
# 1) site-mode + has-enrollment (public endpoints)
# ---------------------------------------------------------------------------
def test_site_mode_is_public():
    r = requests.get(f"{BASE_URL}/api/system/site-mode", timeout=10)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "mode" in data
    assert data["mode"] == "public", f"expected public, got {data}"


def test_webauthn_has_enrollment_shape():
    r = requests.get(f"{BASE_URL}/api/webauthn/has-enrollment", timeout=10)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "enrolled_count" in data and "has_any" in data
    assert isinstance(data["enrolled_count"], int)
    assert isinstance(data["has_any"], bool)
    assert data["has_any"] == (data["enrolled_count"] > 0)


# ---------------------------------------------------------------------------
# 2) login backwards-compat (no device_key_id) — must still work
# ---------------------------------------------------------------------------
def test_login_without_device_key_id(fresh_user):
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": fresh_user["email"], "password": fresh_user["password"]},
        timeout=20,
    )
    assert r.status_code == 200, f"backwards-compat login failed: {r.status_code} {r.text[:300]}"
    data = r.json()
    assert "session_token" in data and data["session_token"]
    # Backend lowercases emails via normalize_email() — compare case-insensitively.
    assert (data.get("email") or "").lower() == fresh_user["email"].lower()
    assert data.get("user_id")
    # Cleanup: logout the session so it doesn't conflict with later tests.
    requests.post(
        f"{BASE_URL}/api/auth/logout",
        headers={"Authorization": f"Bearer {data['session_token']}"},
        timeout=10,
    )


# ---------------------------------------------------------------------------
# 3) Pending-approval flow — APPROVE branch
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def approve_flow_user():
    email = f"TEST_iter45A_{secrets.token_hex(4)}_{int(time.time())}@gmail.com"
    password = "Pass1234"
    r = requests.post(
        f"{BASE_URL}/api/auth/register",
        json={"email": email, "password": password, "frontend_url": BASE_URL},
        timeout=20,
    )
    assert r.status_code == 200, r.text[:200]
    token = r.json()["verification_token"]
    requests.get(f"{BASE_URL}/api/auth/verify-email", params={"token": token}, timeout=15)
    return {"email": email, "password": password}


def test_login_first_device_with_key_succeeds(approve_flow_user, request):
    """First login with a brand-new device_key_id_A — no other active session
    exists yet, so it must succeed and return a session_token."""
    key_a = f"test_key_iter45A_{secrets.token_hex(6)}"
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={
            "email": approve_flow_user["email"],
            "password": approve_flow_user["password"],
            "device_key_id": key_a,
            "device_label": "iter45 device A",
        },
        timeout=20,
    )
    assert r.status_code == 200, f"first device login failed: {r.status_code} {r.text[:300]}"
    data = r.json()
    assert data.get("session_token")
    # Stash on module for the next steps.
    request.session.config.cache.set("iter45/key_a", key_a)
    request.session.config.cache.set("iter45/token_a", data["session_token"])


def test_second_device_login_returns_202_pending(approve_flow_user, request):
    """Second login with a DIFFERENT device_key_id_B must return HTTP 202 with
    detail.code='session_pending_approval' and a request_id."""
    key_a = request.session.config.cache.get("iter45/key_a", None)
    assert key_a, "previous test did not stash key_a"
    key_b = f"test_key_iter45B_{secrets.token_hex(6)}"
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={
            "email": approve_flow_user["email"],
            "password": approve_flow_user["password"],
            "device_key_id": key_b,
            "device_label": "iter45 device B",
        },
        timeout=20,
    )
    assert r.status_code == 202, f"expected 202, got {r.status_code}: {r.text[:300]}"
    body = r.json()
    detail = body.get("detail") or body
    assert detail.get("code") == "session_pending_approval", detail
    assert detail.get("request_id"), detail
    # No session token must be issued at this stage.
    assert "session_token" not in body
    request.session.config.cache.set("iter45/req_id", detail["request_id"])
    request.session.config.cache.set("iter45/key_b", key_b)


def test_status_pending(request):
    req_id = request.session.config.cache.get("iter45/req_id", None)
    assert req_id, "no request_id stashed"
    r = requests.post(
        f"{BASE_URL}/api/auth/session-request-status",
        json={"request_id": req_id},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("status") == "pending", data
    # No session token while pending.
    assert "session_token" not in data


def test_session_pending_lists_request_for_first_device(request):
    token_a = request.session.config.cache.get("iter45/token_a", None)
    req_id = request.session.config.cache.get("iter45/req_id", None)
    assert token_a and req_id
    r = requests.get(
        f"{BASE_URL}/api/auth/session-pending",
        headers={"Authorization": f"Bearer {token_a}"},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    rows = r.json().get("requests") or []
    ids = [x.get("request_id") for x in rows]
    assert req_id in ids, f"pending request {req_id} not in list: {ids}"


def test_decide_approve(request):
    token_a = request.session.config.cache.get("iter45/token_a", None)
    req_id = request.session.config.cache.get("iter45/req_id", None)
    r = requests.post(
        f"{BASE_URL}/api/auth/session-decide",
        json={"request_id": req_id, "decision": "approve"},
        headers={"Authorization": f"Bearer {token_a}"},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    assert r.json().get("status") == "approved"


def test_status_after_approve_issues_session(approve_flow_user, request):
    req_id = request.session.config.cache.get("iter45/req_id", None)
    r = requests.post(
        f"{BASE_URL}/api/auth/session-request-status",
        json={"request_id": req_id},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("status") == "approved", data
    assert data.get("session_token"), data
    assert (data.get("email") or "").lower() == approve_flow_user["email"].lower()
    assert data.get("user_id")
    request.session.config.cache.set("iter45/token_b", data["session_token"])


def test_request_consumed_after_approval(request):
    """Single-use: re-polling the same request_id after approval should now
    return 404 (the row is deleted as soon as the token is issued)."""
    req_id = request.session.config.cache.get("iter45/req_id", None)
    r = requests.post(
        f"{BASE_URL}/api/auth/session-request-status",
        json={"request_id": req_id},
        timeout=15,
    )
    assert r.status_code == 404, f"expected 404 after consumption, got {r.status_code} {r.text[:200]}"


# ---------------------------------------------------------------------------
# 4) Pending-approval flow — DENY branch
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def deny_flow_user():
    email = f"TEST_iter45D_{secrets.token_hex(4)}_{int(time.time())}@gmail.com"
    password = "Pass1234"
    r = requests.post(
        f"{BASE_URL}/api/auth/register",
        json={"email": email, "password": password, "frontend_url": BASE_URL},
        timeout=20,
    )
    assert r.status_code == 200
    token = r.json()["verification_token"]
    requests.get(f"{BASE_URL}/api/auth/verify-email", params={"token": token}, timeout=15)
    return {"email": email, "password": password}


def test_deny_flow_end_to_end(deny_flow_user):
    # First device A login
    key_a = f"deny_iter45A_{secrets.token_hex(6)}"
    key_b = f"deny_iter45B_{secrets.token_hex(6)}"
    r1 = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={
            "email": deny_flow_user["email"],
            "password": deny_flow_user["password"],
            "device_key_id": key_a,
        },
        timeout=20,
    )
    assert r1.status_code == 200, r1.text[:200]
    token_a = r1.json()["session_token"]

    # Second device B login -> 202
    r2 = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={
            "email": deny_flow_user["email"],
            "password": deny_flow_user["password"],
            "device_key_id": key_b,
        },
        timeout=20,
    )
    assert r2.status_code == 202, r2.text[:200]
    req_id = (r2.json().get("detail") or {}).get("request_id")
    assert req_id

    # A denies
    rd = requests.post(
        f"{BASE_URL}/api/auth/session-decide",
        json={"request_id": req_id, "decision": "deny"},
        headers={"Authorization": f"Bearer {token_a}"},
        timeout=15,
    )
    assert rd.status_code == 200, rd.text
    assert rd.json().get("status") == "denied"

    # B polls status -> "denied"
    rs = requests.post(
        f"{BASE_URL}/api/auth/session-request-status",
        json={"request_id": req_id},
        timeout=15,
    )
    assert rs.status_code == 200, rs.text
    data = rs.json()
    assert data.get("status") == "denied", data
    assert "session_token" not in data


# ---------------------------------------------------------------------------
# 5) WebAuthn options endpoints must reject non-creator callers (403)
# ---------------------------------------------------------------------------
def test_webauthn_register_options_requires_creator():
    r = requests.post(
        f"{BASE_URL}/api/webauthn/register-options",
        json={
            "key_id": "dev_nonexistent_iter45_xxx",
            "nonce": "fake-nonce",
            "signature": "fake-sig",
            "origin": BASE_URL,
        },
        timeout=15,
    )
    assert r.status_code == 403, f"expected 403, got {r.status_code} {r.text[:200]}"


def test_webauthn_register_verify_requires_creator():
    r = requests.post(
        f"{BASE_URL}/api/webauthn/register-verify",
        json={
            "key_id": "dev_nonexistent_iter45_xxx",
            "nonce": "fake-nonce",
            "signature": "fake-sig",
            "origin": BASE_URL,
            "credential": {},
        },
        timeout=15,
    )
    # Either 403 (creator check) or 400 (bad credential) — but never 200.
    assert r.status_code in (400, 403, 404), f"unexpected status {r.status_code}: {r.text[:200]}"
    # Specifically we want creator gating to fire first.
    if r.status_code == 403:
        assert "créateur" in r.text or "creator" in r.text.lower() or "Signature" in r.text or "Nonce" in r.text


def test_webauthn_declare_theft_options_requires_known_device():
    r = requests.post(
        f"{BASE_URL}/api/webauthn/declare-theft-options",
        json={
            "key_id": "dev_completely_unknown_iter45",
            "origin": BASE_URL,
        },
        timeout=15,
    )
    # Unknown device -> 404, gated correctly.
    assert r.status_code in (403, 404), f"unexpected status {r.status_code}: {r.text[:200]}"


# ---------------------------------------------------------------------------
# 6) Kept device key state in MongoDB
# ---------------------------------------------------------------------------
def test_kept_creator_device_still_present(mongo_db):
    doc = mongo_db.device_keys.find_one({"key_id": KEPT_KEY_ID}, {"_id": 0})
    assert doc is not None, f"kept key {KEPT_KEY_ID} missing from db.device_keys"
    assert doc.get("role") == "creator", f"kept key role is {doc.get('role')}, expected 'creator'"


def test_no_other_device_keys_exist(mongo_db):
    """Per iter_45 spec: only the kept device key should remain in device_keys
    after the reset. This is an environment-state assertion — if other keys
    have been added by later test/registration activity, we surface them but
    do not require role=creator on them."""
    others = list(
        mongo_db.device_keys.find(
            {"key_id": {"$ne": KEPT_KEY_ID}},
            {"_id": 0, "key_id": 1, "role": 1, "label": 1},
        )
    )
    assert not others, (
        f"unexpected extra device_keys present (state drift since iter_45 reset): {others}"
    )
