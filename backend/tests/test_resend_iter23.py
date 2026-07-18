"""Iteration 23 — POST /api/auth/resend-verification + non-regression."""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"


def _email():
    return f"test_iter23_{uuid.uuid4().hex[:10]}@gmail.com"


def _register(email: str, password: str = "Pass1234"):
    return requests.post(
        f"{API}/auth/register",
        json={"email": email, "password": password,
              "pseudo": "iter23_user",
              "public_handle": f"iter23_{uuid.uuid4().hex[:6]}",
              "frontend_url": BASE_URL},
        timeout=15,
    )


def _verify(token: str):
    return requests.get(f"{API}/auth/verify-email", params={"token": token}, timeout=15)


# ---------------- RESEND ----------------

class TestResendVerification:
    def test_unverified_returns_link_and_token(self):
        email = _email()
        _register(email)
        r = requests.post(
            f"{API}/auth/resend-verification",
            json={"email": email, "frontend_url": BASE_URL},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "verification_token" in body
        assert "verification_link" in body
        assert body.get("expires_in_seconds") == 300
        assert body.get("email") == email
        assert "token=" in body["verification_link"]

    def test_already_verified_returns_neutral_no_link(self):
        email = _email()
        r = _register(email)
        token = r.json()["verification_link"].split("token=")[1]
        v = _verify(token)
        assert v.status_code == 200
        r2 = requests.post(
            f"{API}/auth/resend-verification",
            json={"email": email}, timeout=15,
        )
        assert r2.status_code == 200
        body = r2.json()
        assert "verification_link" not in body
        assert "verification_token" not in body
        assert "message" in body

    def test_unknown_email_returns_neutral_no_link(self):
        email = f"TEST_unknown_{uuid.uuid4().hex[:8]}@gmail.com"
        r = requests.post(
            f"{API}/auth/resend-verification",
            json={"email": email}, timeout=15,
        )
        assert r.status_code == 200
        body = r.json()
        assert "verification_link" not in body
        assert "verification_token" not in body
        assert "message" in body

    def test_invalid_email_returns_400(self):
        r = requests.post(
            f"{API}/auth/resend-verification",
            json={"email": "not-an-email"}, timeout=15,
        )
        assert r.status_code == 400

    def test_rate_limit_4th_call_is_429(self):
        email = _email()
        _register(email)
        statuses = []
        for _ in range(4):
            r = requests.post(
                f"{API}/auth/resend-verification",
                json={"email": email}, timeout=15,
            )
            statuses.append(r.status_code)
        # 3 ok, 4th must be 429
        assert statuses[:3] == [200, 200, 200], f"got {statuses}"
        assert statuses[3] == 429, f"got {statuses}"

    def test_resend_invalidates_previous_token(self):
        email = _email()
        r1 = _register(email)
        old_token = r1.json()["verification_link"].split("token=")[1]
        old_v_token = r1.json()["verification_token"]
        # Resend
        r2 = requests.post(
            f"{API}/auth/resend-verification",
            json={"email": email}, timeout=15,
        )
        assert r2.status_code == 200
        # Old verification-status should now report expired (row deleted)
        r3 = requests.get(
            f"{API}/auth/verification-status",
            params={"token": old_v_token}, timeout=10,
        )
        assert r3.status_code == 200
        # When the row is deleted, status becomes 'expired' or 'invalid'
        assert r3.json().get("status") in ("expired", "invalid", "unknown"), r3.json()
        # Old verify-email link no longer works
        r4 = _verify(old_token)
        assert r4.status_code in (400, 404)


# ---------------- NON-REGRESSION ----------------

class TestNonRegression:
    def test_register_verify_login(self):
        email = _email()
        pw = "Secret123!"
        r1 = requests.post(
            f"{API}/auth/register",
            json={"email": email, "password": pw,
                  "pseudo": "iter23_reg",
                  "public_handle": f"iter23_nr_{uuid.uuid4().hex[:6]}"},
            timeout=15,
        )
        assert r1.status_code == 200
        token = r1.json()["verification_link"].split("token=")[1]
        v_token = r1.json()["verification_token"]
        r2 = _verify(token)
        assert r2.status_code == 200
        # Poll picks session
        r3 = requests.get(
            f"{API}/auth/verification-status",
            params={"token": v_token}, timeout=10,
        )
        assert r3.status_code == 200
        assert r3.json()["status"] == "verified"

    def test_guide_endpoint_returns_html(self):
        r = requests.get(f"{API}/guide", timeout=10)
        assert r.status_code == 200
        ctype = r.headers.get("content-type", "")
        assert "html" in ctype.lower()

    def test_legacy_routes_404(self):
        for path in ("/auth/google/login", "/auth/google/callback"):
            r = requests.get(f"{API}{path}", allow_redirects=False, timeout=10)
            assert r.status_code in (404, 405), f"{path} -> {r.status_code}"
        r2 = requests.post(f"{API}/auth/session", json={"session_id": "x"}, timeout=10)
        assert r2.status_code in (404, 405)
