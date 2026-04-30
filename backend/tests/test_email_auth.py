"""
Email/Password + Magic Link auth regression tests (iter_20).

Covers the new auth flow that replaces Google OAuth + Emergent Auth:
- POST /api/auth/register (demo mode returns verification_link)
- GET  /api/auth/verify-email?token=... (marks verified, sets cookie)
- POST /api/auth/login (verified user → session, unverified → 403)
- POST /api/auth/logout
- GET  /api/auth/me (sans password_hash)
- Brute-force lockout: 5 failed logins → 429
- Validation: email invalide, password trop court, doublon vérifié
- Anciennes routes Emergent / Google OAuth supprimées
- SMS flow toujours fonctionnel
"""
import os
import time
import uuid
import pytest
import requests
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")


def _email():
    return f"test_{uuid.uuid4().hex[:10]}@gmail.com"


@pytest.fixture(scope="module")
def db():
    if not MONGO_URL or not DB_NAME:
        pytest.skip("Mongo env vars missing")
    c = MongoClient(MONGO_URL)
    yield c[DB_NAME]
    c.close()


# ---------------- REGISTER ----------------

class TestRegister:
    def test_register_returns_demo_link(self):
        email = _email()
        r = requests.post(f"{API}/auth/register",
                          json={"email": email, "password": "SecurePass123", "name": "Tester"},
                          timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["email"] == email
        assert body["email_sent"] is False
        assert "verification_link" in body
        assert "token=" in body["verification_link"]

    def test_register_invalid_email_returns_400(self):
        r = requests.post(f"{API}/auth/register",
                          json={"email": "not-an-email", "password": "SecurePass123"},
                          timeout=15)
        assert r.status_code == 400

    def test_register_short_password_returns_400(self):
        r = requests.post(f"{API}/auth/register",
                          json={"email": _email(), "password": "12345"},
                          timeout=15)
        assert r.status_code == 400

    def test_register_existing_verified_returns_409(self, db):
        email = _email()
        # register + verify
        r = requests.post(f"{API}/auth/register",
                          json={"email": email, "password": "SecurePass123"},
                          timeout=15)
        link = r.json()["verification_link"]
        token = link.split("token=")[1]
        r2 = requests.get(f"{API}/auth/verify-email", params={"token": token}, timeout=15)
        assert r2.status_code == 200
        # second register on same verified email -> 409
        r3 = requests.post(f"{API}/auth/register",
                           json={"email": email, "password": "OtherPass99"},
                           timeout=15)
        assert r3.status_code == 409

    def test_register_existing_unverified_resends_link(self):
        email = _email()
        r1 = requests.post(f"{API}/auth/register",
                           json={"email": email, "password": "FirstPass11"},
                           timeout=15)
        assert r1.status_code == 200
        # Re-register on unverified — should NOT 409, should reissue link
        r2 = requests.post(f"{API}/auth/register",
                           json={"email": email, "password": "SecondPass22"},
                           timeout=15)
        assert r2.status_code == 200, r2.text
        assert "verification_link" in r2.json()


# ---------------- VERIFY EMAIL ----------------

class TestVerifyEmail:
    def test_invalid_token_returns_400(self):
        r = requests.get(f"{API}/auth/verify-email",
                         params={"token": "invalid-token-xyz"}, timeout=15)
        assert r.status_code == 400

    def test_valid_token_creates_session(self):
        email = _email()
        r = requests.post(f"{API}/auth/register",
                          json={"email": email, "password": "GoodPass123"},
                          timeout=15)
        token = r.json()["verification_link"].split("token=")[1]
        s = requests.Session()
        r2 = s.get(f"{API}/auth/verify-email", params={"token": token}, timeout=15)
        assert r2.status_code == 200
        body = r2.json()
        assert body["email"] == email
        assert body["verified"] is True
        assert "session_token" in body
        assert "password_hash" not in body
        assert "session_token" in s.cookies

    def test_expired_token_returns_400(self, db):
        email = _email()
        r = requests.post(f"{API}/auth/register",
                          json={"email": email, "password": "ExpirePass99"},
                          timeout=15)
        token = r.json()["verification_link"].split("token=")[1]
        # force expiration in DB
        past = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        res = db.email_verifications.update_one({"token": token}, {"$set": {"expires_at": past}})
        assert res.matched_count == 1
        r2 = requests.get(f"{API}/auth/verify-email", params={"token": token}, timeout=15)
        assert r2.status_code == 400


# ---------------- LOGIN ----------------

@pytest.fixture
def verified_user():
    email = _email()
    pw = "MyPass123!"
    r = requests.post(f"{API}/auth/register",
                      json={"email": email, "password": pw, "name": "VerUser"},
                      timeout=15)
    token = r.json()["verification_link"].split("token=")[1]
    requests.get(f"{API}/auth/verify-email", params={"token": token}, timeout=15)
    return email, pw


class TestLogin:
    def test_login_verified_returns_session(self, verified_user):
        email, pw = verified_user
        s = requests.Session()
        r = s.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["email"] == email
        assert "session_token" in body
        assert "password_hash" not in body
        assert "session_token" in s.cookies

    def test_login_unverified_returns_403(self):
        email = _email()
        requests.post(f"{API}/auth/register",
                      json={"email": email, "password": "UnverPass99"},
                      timeout=15)
        r = requests.post(f"{API}/auth/login",
                         json={"email": email, "password": "UnverPass99"},
                         timeout=15)
        assert r.status_code == 403

    def test_login_wrong_password_returns_401(self, verified_user):
        email, _ = verified_user
        r = requests.post(f"{API}/auth/login",
                         json={"email": email, "password": "WrongPass!!"},
                         timeout=15)
        assert r.status_code == 401

    def test_login_brute_force_returns_429(self):
        # fresh verified user to isolate counter
        email = _email()
        pw = "RealPass123"
        r = requests.post(f"{API}/auth/register",
                          json={"email": email, "password": pw}, timeout=15)
        token = r.json()["verification_link"].split("token=")[1]
        requests.get(f"{API}/auth/verify-email", params={"token": token}, timeout=15)
        # 5 wrong attempts
        for _ in range(5):
            requests.post(f"{API}/auth/login",
                         json={"email": email, "password": "Wrong!!"},
                         timeout=15)
        r6 = requests.post(f"{API}/auth/login",
                          json={"email": email, "password": "Wrong!!"},
                          timeout=15)
        assert r6.status_code == 429


# ---------------- ME / LOGOUT ----------------

class TestMeLogout:
    def test_me_returns_no_password_hash(self, verified_user):
        email, pw = verified_user
        s = requests.Session()
        s.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=15)
        r = s.get(f"{API}/auth/me", timeout=10)
        assert r.status_code == 200
        body = r.json()
        assert body["email"] == email
        assert "password_hash" not in body

    def test_me_with_bearer_token(self, verified_user):
        email, pw = verified_user
        r = requests.post(f"{API}/auth/login",
                          json={"email": email, "password": pw}, timeout=15)
        tok = r.json()["session_token"]
        r2 = requests.get(f"{API}/auth/me",
                          headers={"Authorization": f"Bearer {tok}"}, timeout=10)
        assert r2.status_code == 200
        assert r2.json()["email"] == email

    def test_logout_destroys_session(self, verified_user, db):
        email, pw = verified_user
        s = requests.Session()
        r = s.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=15)
        tok = r.json()["session_token"]
        r2 = s.post(f"{API}/auth/logout", timeout=10)
        assert r2.status_code == 200
        # session removed from db
        assert db.user_sessions.find_one({"session_token": tok}) is None


# ---------------- DEPRECATED ROUTES ----------------

class TestDeprecatedRoutes:
    def test_auth_session_removed(self):
        r = requests.post(f"{API}/auth/session",
                          json={"session_id": "x"}, timeout=10)
        assert r.status_code in (404, 405)

    def test_google_login_removed(self):
        r = requests.get(f"{API}/auth/google/login",
                         allow_redirects=False, timeout=10)
        assert r.status_code in (404, 405)

    def test_google_callback_removed(self):
        r = requests.get(f"{API}/auth/google/callback",
                         allow_redirects=False, timeout=10)
        assert r.status_code in (404, 405)


# ---------------- SMS STILL WORKS ----------------

class TestSMSStillFunctional:
    def test_sms_send_and_verify(self):
        phone = f"+33611{uuid.uuid4().int % 10**6:06d}"
        r = requests.post(f"{API}/auth/sms/send",
                          json={"phone_number": phone}, timeout=15)
        assert r.status_code == 200
        code = r.json()["code"]
        s = requests.Session()
        r2 = s.post(f"{API}/auth/sms/verify",
                    json={"phone_number": phone, "code": code}, timeout=15)
        assert r2.status_code == 200
        assert "session_token" in s.cookies


# ---------------- INDEXES ----------------

class TestMongoIndexes:
    def test_users_email_unique_index(self, db):
        idx = db.users.index_information()
        # at least one index covers 'email' uniquely
        has_unique_email = any(
            i.get("unique") and any(f[0] == "email" for f in i.get("key", []))
            for i in idx.values()
        )
        assert has_unique_email, f"no unique email index. indexes={idx}"

    def test_collections_exist(self, db):
        names = db.list_collection_names()
        # At least one of these should exist (created on first write)
        # We'll just verify the write path produces them
        assert "users" in names
