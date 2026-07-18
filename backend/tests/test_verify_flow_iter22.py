"""
Iteration 22 — Tests for the new cross-tab email verification flow.

Covers:
  - POST /api/auth/register returns verification_token + expires_in_seconds=300 + verification_link
  - GET  /api/auth/verification-status → pending | verified | expired  (+ single-use)
  - GET  /api/auth/verify-email → friendly message, no cookie set, exact expired message
  - GET  /api/guide → HTML 200 with troubleshooting content
  - Legacy /api/auth/google/* and /api/auth/session are 404 (removed)
"""
import os
import time
import asyncio
import pytest
import requests
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta

load_dotenv(Path(__file__).resolve().parents[2] / "frontend" / ".env")
load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")
assert BASE_URL, "REACT_APP_BACKEND_URL missing"
assert MONGO_URL and DB_NAME, "Mongo env missing"

EXPIRED_MSG = "La durée de validation de ce lien a expiré. Merci de réessayer à nouveau sur CodeForge AI."
SUCCESS_MSG = "Votre compte est désormais certifié. Vous pouvez fermer cette page et retourner sur l'application."


# --------- Fixtures ---------
@pytest.fixture
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _unique_email(tag="iter22"):
    return f"TEST_{tag}_{int(time.time()*1000)}@example.com"


def _reg_body(email, password="Secret123!", **extra):
    """iter141 — Payload d'inscription avec public_handle unique obligatoire."""
    import secrets as _s
    body = {
        "email": email,
        "password": password,
        "pseudo": extra.pop("pseudo", "iter22_user"),
        "public_handle": extra.pop("public_handle", f"iter22_{_s.token_hex(4)}"),
        "frontend_url": BASE_URL,
    }
    body.update(extra)
    return body


# --------- Register returns polling fields ---------
class TestRegisterResponse:
    def test_register_returns_token_ttl_link(self, api):
        email = _unique_email("reg")
        r = api.post(f"{BASE_URL}/api/auth/register", json=_reg_body(email, "Secret123!", name="Iter22 User"))
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["email"] == email.lower()
        assert data["email_sent"] is False  # demo mode
        assert "verification_token" in data and isinstance(data["verification_token"], str) and len(data["verification_token"]) > 10
        assert data["expires_in_seconds"] == 300, f"Expected TTL 300s, got {data['expires_in_seconds']}"
        assert "verification_link" in data
        assert "/verify-email?token=" in data["verification_link"]
        # Link uses the frontend_url we passed
        assert data["verification_link"].startswith(BASE_URL)


# --------- Polling lifecycle ---------
class TestPollingLifecycle:
    def test_pending_then_verified_then_expired_singleuse(self, api):
        email = _unique_email("poll")
        reg = api.post(f"{BASE_URL}/api/auth/register", json=_reg_body(email)).json()
        token = reg["verification_token"]

        # Before click → pending
        r = api.get(f"{BASE_URL}/api/auth/verification-status", params={"token": token})
        assert r.status_code == 200
        assert r.json() == {"status": "pending"}

        # Click magic link (verify-email) — should NOT set a cookie
        v = api.get(f"{BASE_URL}/api/auth/verify-email", params={"token": token}, allow_redirects=False)
        assert v.status_code == 200, v.text
        body = v.json()
        assert body["message"] == SUCCESS_MSG
        assert body.get("already_verified") is False
        # No session cookie on the verify-email response
        assert "session_token" not in v.cookies, f"verify-email should NOT set session_token cookie; got {dict(v.cookies)}"

        # Poll after click → verified with session_token + user
        r2 = api.get(f"{BASE_URL}/api/auth/verification-status", params={"token": token})
        assert r2.status_code == 200
        j = r2.json()
        assert j["status"] == "verified"
        assert isinstance(j.get("session_token"), str) and len(j["session_token"]) > 10
        assert j["user"]["email"] == email.lower()
        assert j["user"].get("verified") is True
        assert "password_hash" not in j["user"]

        # Subsequent poll → expired (single-use, row deleted)
        r3 = api.get(f"{BASE_URL}/api/auth/verification-status", params={"token": token})
        assert r3.status_code == 200
        assert r3.json() == {"status": "expired"}

        # Verify session_token works on /api/auth/me
        me = requests.get(f"{BASE_URL}/api/auth/me",
                          headers={"Authorization": f"Bearer {j['session_token']}"})
        assert me.status_code == 200, me.text
        assert me.json()["email"] == email.lower()


# --------- Expired link returns exact French message ---------
class TestExpiredLinkMessage:
    def test_expired_token_exact_message(self, api):
        """Simulate expiration by rewriting expires_at in MongoDB to a past ISO."""
        from motor.motor_asyncio import AsyncIOMotorClient

        email = _unique_email("exp")
        reg = api.post(f"{BASE_URL}/api/auth/register", json=_reg_body(email)).json()
        token = reg["verification_token"]

        async def _expire():
            client = AsyncIOMotorClient(MONGO_URL)
            db = client[DB_NAME]
            past = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
            res = await db.email_verifications.update_one(
                {"token": token}, {"$set": {"expires_at": past}}
            )
            client.close()
            return res.modified_count

        modified = asyncio.get_event_loop().run_until_complete(_expire()) \
            if not asyncio.get_event_loop().is_running() else asyncio.run(_expire())
        assert modified == 1

        # GET verify-email → 400 with EXACT expired message
        v = api.get(f"{BASE_URL}/api/auth/verify-email", params={"token": token})
        assert v.status_code == 400, v.text
        assert v.json()["detail"] == EXPIRED_MSG

    def test_verification_status_expired_after_ttl(self, api):
        """After the same row is expired, /verification-status returns 'expired' and cleans the row."""
        from motor.motor_asyncio import AsyncIOMotorClient

        email = _unique_email("expst")
        reg = api.post(f"{BASE_URL}/api/auth/register", json=_reg_body(email)).json()
        token = reg["verification_token"]

        async def _expire():
            client = AsyncIOMotorClient(MONGO_URL)
            db = client[DB_NAME]
            past = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
            await db.email_verifications.update_one(
                {"token": token}, {"$set": {"expires_at": past}}
            )
            client.close()

        try:
            asyncio.run(_expire())
        except RuntimeError:
            asyncio.get_event_loop().run_until_complete(_expire())

        r = api.get(f"{BASE_URL}/api/auth/verification-status", params={"token": token})
        assert r.status_code == 200
        assert r.json() == {"status": "expired"}


# --------- /api/guide HTML ---------
class TestGuideEndpoint:
    def test_guide_returns_html(self, api):
        r = requests.get(f"{BASE_URL}/api/guide")
        assert r.status_code == 200, r.text
        ctype = r.headers.get("content-type", "")
        assert "text/html" in ctype, f"Expected text/html, got {ctype}"
        body = r.text
        assert "Guide dépannage GitHub" in body or "Guide" in body and "GitHub" in body
        # Should contain some HTML structure
        assert "<html" in body.lower() and "</html>" in body.lower()


# --------- Legacy removed routes ---------
class TestRemovedRoutes:
    def test_google_login_removed(self):
        r = requests.get(f"{BASE_URL}/api/auth/google/login", allow_redirects=False)
        assert r.status_code == 404, f"Expected 404, got {r.status_code}"

    def test_google_callback_removed(self):
        r = requests.get(f"{BASE_URL}/api/auth/google/callback", allow_redirects=False)
        assert r.status_code == 404

    def test_auth_session_removed(self):
        r = requests.post(f"{BASE_URL}/api/auth/session")
        assert r.status_code == 404


# --------- Login with verified email works ---------
class TestLoginAfterVerify:
    def test_login_works_post_verification(self, api):
        email = _unique_email("login")
        pwd = "Secret123!"
        reg = api.post(f"{BASE_URL}/api/auth/register", json=_reg_body(email, pwd)).json()
        # Consume the link
        api.get(f"{BASE_URL}/api/auth/verify-email", params={"token": reg["verification_token"]})
        # Now login
        r = api.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pwd})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["email"] == email.lower()
        assert "session_token" in data
