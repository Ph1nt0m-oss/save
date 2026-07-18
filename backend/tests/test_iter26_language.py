"""
Iteration 26 — smoke test for the new optional `language` field on
/api/ai/generate-complete-app. We only assert the endpoint accepts the
payload and returns HTTP 200 with a sensible response structure.
Auth flow is also quickly re-validated (register→verify→login).
"""
import os
import time
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://no-code-builder-25.preview.emergentagent.com").rstrip("/")


def _register_verified_user():
    email = f"test_iter26_{int(time.time())}@gmail.com"
    handle = f"h26_{int(time.time())}"
    r = requests.post(
        f"{BASE_URL}/api/auth/register",
        json={"email": email, "password": "Pass1234", "pseudo": "iter26_user",
              "public_handle": handle, "frontend_url": BASE_URL},
        timeout=30,
    )
    assert r.status_code in (200, 201), f"register failed: {r.status_code} {r.text}"
    body = r.json()
    token = body.get("verification_token") or body.get("token")
    if not token:
        # Real Resend mode — no token in the response; fall back to the pre-existing verified user.
        return None, None
    v = requests.get(f"{BASE_URL}/api/auth/verify-email", params={"token": token}, timeout=15)
    assert v.status_code == 200, f"verify failed: {v.status_code} {v.text}"
    return email, "Pass1234"


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    b = r.json()
    tok = b.get("token") or b.get("access_token") or b.get("session_token")
    assert tok, f"no token in login body: {b}"
    return tok


class TestAuthFlow:
    def test_register_verify_login(self):
        email, pw = _register_verified_user()
        if not email:
            pytest.skip("Resend real mode — no token in body. Skip in-test new user creation.")
        tok = _login(email, pw)
        me = requests.get(f"{BASE_URL}/api/auth/me", headers={"Authorization": f"Bearer {tok}"}, timeout=10)
        assert me.status_code == 200
        assert me.json().get("email") == email


class TestGenerateCompleteAppLanguage:
    """Quick smoke test: language param accepted."""

    @pytest.fixture(scope="class")
    def auth_token(self):
        email, pw = _register_verified_user()
        if email:
            return _login(email, pw)
        # Fallback pre-existing verified test user
        try:
            return _login("test_dash_1777658375@gmail.com", "Pass1234")
        except Exception:
            pytest.skip("No verified user available for auth")

    def _call(self, token, language):
        payload = {
            "description": "a tiny todo list with local storage",
            "mode": "web",
            "language": language,
        }
        return requests.post(
            f"{BASE_URL}/api/ai/generate-complete-app",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=180,
        )

    def test_language_es_accepted(self, auth_token):
        r = self._call(auth_token, "es")
        # Endpoint may be slow — only assert 200 + some code/explanation in body
        assert r.status_code == 200, f"body={r.text[:400]}"
        data = r.json()
        assert isinstance(data, dict)
        assert any(k in data for k in ("code", "files", "explanation", "html", "project", "success"))

    def test_language_de_accepted(self, auth_token):
        r = self._call(auth_token, "de")
        assert r.status_code == 200, f"body={r.text[:400]}"

    def test_language_missing_still_works_backwards_compat(self, auth_token):
        payload = {"description": "a tiny calculator", "mode": "web"}
        r = requests.post(
            f"{BASE_URL}/api/ai/generate-complete-app",
            json=payload,
            headers={"Authorization": f"Bearer {auth_token}"},
            timeout=180,
        )
        assert r.status_code == 200
