"""Iteration 24 — exhaustive tests for forgot/reset-password + /health + non-regression."""
import os
import time
import uuid
from datetime import datetime, timezone, timedelta

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")


def _api(path: str) -> str:
    return f"{BASE_URL}/api{path}"


def _norm(e: str) -> str:
    return e.strip().lower()


@pytest.fixture(scope="module")
def db():
    c = MongoClient(MONGO_URL)
    yield c[DB_NAME]
    c.close()


def _register_and_verify(email: str, password: str = "Pass1234") -> str:
    """Register + auto-verify a user. Returns user_id."""
    r = requests.post(_api("/auth/register"), json={
        "email": email, "password": password, "frontend_url": BASE_URL,
    }, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    # In RESEND mode, no demo link returned. Pull token from /auth/verification-status flow
    # via direct DB or use the verification_token + GET /auth/verify-email.
    token = data.get("verification_token")
    assert token
    rv = requests.get(_api("/auth/verify-email"), params={"token": token}, timeout=15)
    assert rv.status_code == 200, rv.text
    return data


# ==================== /api/health ====================

class TestHealth:
    def test_health_returns_200_and_checks(self):
        r = requests.get(_api("/health"), timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert "checks" in d
        assert "mongo" in d["checks"]
        # status healthy if mongo OK
        if d["checks"].get("mongo"):
            assert d.get("status") == "healthy"


# ==================== Forgot password ====================

class TestForgotPassword:
    def test_unknown_email_neutral(self):
        email = f"TEST_unknown_{uuid.uuid4().hex[:8]}@gmail.com"
        r = requests.post(_api("/auth/forgot-password"), json={"email": email}, timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert "message" in d
        assert "reset_link" not in d  # no enumeration

    def test_unverified_email_neutral(self, db):
        email = f"TEST_unverif_{uuid.uuid4().hex[:8]}@gmail.com"
        # Register only (no verify)
        rr = requests.post(_api("/auth/register"), json={"email": email, "password": "Pass1234"}, timeout=10)
        assert rr.status_code == 200
        r = requests.post(_api("/auth/forgot-password"), json={"email": email}, timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert "reset_link" not in d
        # cleanup
        db.users.delete_many({"email": _norm(email)})

    def test_verified_email_returns_email_sent_field(self, db):
        email = f"TEST_verif_{uuid.uuid4().hex[:8]}@gmail.com"
        _register_and_verify(email)
        r = requests.post(_api("/auth/forgot-password"), json={
            "email": email, "frontend_url": BASE_URL,
        }, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "message" in d
        assert "email_sent" in d
        assert isinstance(d["email_sent"], bool)
        # Token must be in DB
        tk = db.password_reset_tokens.find_one({"email": _norm(email)})
        assert tk is not None
        assert tk.get("consumed_at") is None
        # cleanup
        db.users.delete_many({"email": _norm(email)})
        db.password_reset_tokens.delete_many({"email": _norm(email)})
        db.password_resets.delete_many({"email": _norm(email)})

    def test_invalid_email_format_400(self):
        r = requests.post(_api("/auth/forgot-password"), json={"email": "notanemail"}, timeout=10)
        assert r.status_code == 400

    def test_rate_limit_4th_call_429(self, db):
        email = f"TEST_rate_{uuid.uuid4().hex[:8]}@gmail.com"
        for i in range(3):
            r = requests.post(_api("/auth/forgot-password"), json={"email": email}, timeout=10)
            assert r.status_code == 200, f"call {i+1}: {r.text}"
        r4 = requests.post(_api("/auth/forgot-password"), json={"email": email}, timeout=10)
        assert r4.status_code == 429
        db.password_resets.delete_many({"email": _norm(email)})


# ==================== Reset password ====================

class TestResetPassword:
    def _gen_reset_token(self, email: str, db) -> str:
        """Create user verified + reset token directly via API (uses Resend so no link)."""
        _register_and_verify(email)
        requests.post(_api("/auth/forgot-password"), json={
            "email": email, "frontend_url": BASE_URL,
        }, timeout=15)
        tk = db.password_reset_tokens.find_one({"email": _norm(email)})
        assert tk, "token missing"
        return tk["token"]

    def test_reset_with_valid_token_old_pwd_fails_new_works(self, db):
        email = f"TEST_reset1_{uuid.uuid4().hex[:8]}@gmail.com"
        token = self._gen_reset_token(email, db)
        # Reset
        r = requests.post(_api("/auth/reset-password"), json={
            "token": token, "password": "NewPass9999",
        }, timeout=15)
        assert r.status_code == 200, r.text
        # Old password must NOT work
        old = requests.post(_api("/auth/login"), json={"email": email, "password": "Pass1234"}, timeout=10)
        assert old.status_code == 401
        # New password works
        new = requests.post(_api("/auth/login"), json={"email": email, "password": "NewPass9999"}, timeout=10)
        assert new.status_code == 200, new.text
        assert "session_token" in new.json()
        db.users.delete_many({"email": _norm(email)})
        db.password_reset_tokens.delete_many({"email": _norm(email)})
        db.password_resets.delete_many({"email": _norm(email)})
        db.user_sessions.delete_many({"user_id": new.json().get("user_id")})

    def test_reset_invalid_token_400(self):
        r = requests.post(_api("/auth/reset-password"), json={
            "token": "bogus_xxx", "password": "Pass1234",
        }, timeout=10)
        assert r.status_code == 400

    def test_reset_short_password_400(self, db):
        email = f"TEST_short_{uuid.uuid4().hex[:8]}@gmail.com"
        token = self._gen_reset_token(email, db)
        r = requests.post(_api("/auth/reset-password"), json={
            "token": token, "password": "abc",
        }, timeout=10)
        assert r.status_code == 400
        db.users.delete_many({"email": _norm(email)})
        db.password_reset_tokens.delete_many({"email": _norm(email)})
        db.password_resets.delete_many({"email": _norm(email)})

    def test_reset_expired_token_400(self, db):
        email = f"TEST_exp_{uuid.uuid4().hex[:8]}@gmail.com"
        token = self._gen_reset_token(email, db)
        # Force expiry
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        db.password_reset_tokens.update_one({"token": token}, {"$set": {"expires_at": past}})
        r = requests.post(_api("/auth/reset-password"), json={
            "token": token, "password": "NewPass8888",
        }, timeout=10)
        assert r.status_code == 400
        assert "expir" in r.json().get("detail", "").lower()
        db.users.delete_many({"email": _norm(email)})
        db.password_reset_tokens.delete_many({"email": _norm(email)})
        db.password_resets.delete_many({"email": _norm(email)})

    def test_reset_token_single_use(self, db):
        email = f"TEST_single_{uuid.uuid4().hex[:8]}@gmail.com"
        token = self._gen_reset_token(email, db)
        r1 = requests.post(_api("/auth/reset-password"), json={
            "token": token, "password": "NewPass7777",
        }, timeout=15)
        assert r1.status_code == 200
        r2 = requests.post(_api("/auth/reset-password"), json={
            "token": token, "password": "AnotherPass8888",
        }, timeout=15)
        assert r2.status_code == 400
        db.users.delete_many({"email": _norm(email)})
        db.password_reset_tokens.delete_many({"email": _norm(email)})
        db.password_resets.delete_many({"email": _norm(email)})

    def test_existing_session_invalidated_after_reset(self, db):
        email = f"TEST_sessinv_{uuid.uuid4().hex[:8]}@gmail.com"
        _register_and_verify(email)
        # login to get session
        lg = requests.post(_api("/auth/login"), json={"email": email, "password": "Pass1234"}, timeout=10)
        assert lg.status_code == 200
        sess = lg.json()["session_token"]
        # /auth/me works
        me1 = requests.get(_api("/auth/me"), headers={"Authorization": f"Bearer {sess}"}, timeout=10)
        assert me1.status_code == 200
        # request reset
        requests.post(_api("/auth/forgot-password"), json={"email": email, "frontend_url": BASE_URL}, timeout=15)
        tk = db.password_reset_tokens.find_one({"email": _norm(email)})
        # do reset
        rr = requests.post(_api("/auth/reset-password"), json={
            "token": tk["token"], "password": "BrandNew9999",
        }, timeout=15)
        assert rr.status_code == 200
        # Old session must be 401 now
        me2 = requests.get(_api("/auth/me"), headers={"Authorization": f"Bearer {sess}"}, timeout=10)
        assert me2.status_code == 401
        db.users.delete_many({"email": _norm(email)})
        db.password_reset_tokens.delete_many({"email": _norm(email)})
        db.password_resets.delete_many({"email": _norm(email)})


# ==================== Non-regression ====================

class TestNonRegression:
    def test_full_email_auth_flow(self, db):
        email = f"TEST_e2e_{uuid.uuid4().hex[:8]}@gmail.com"
        rr = requests.post(_api("/auth/register"), json={"email": email, "password": "Pass1234"}, timeout=10)
        assert rr.status_code == 200
        token = rr.json()["verification_token"]
        rv = requests.get(_api("/auth/verify-email"), params={"token": token}, timeout=10)
        assert rv.status_code == 200
        # poll
        ps = requests.get(_api("/auth/verification-status"), params={"token": token}, timeout=10)
        assert ps.status_code == 200
        # login
        lg = requests.post(_api("/auth/login"), json={"email": email, "password": "Pass1234"}, timeout=10)
        assert lg.status_code == 200
        sess = lg.json()["session_token"]
        me = requests.get(_api("/auth/me"), headers={"Authorization": f"Bearer {sess}"}, timeout=10)
        assert me.status_code == 200
        lo = requests.post(_api("/auth/logout"), headers={"Authorization": f"Bearer {sess}"}, timeout=10)
        assert lo.status_code == 200
        db.users.delete_many({"email": _norm(email)})

    def test_metrics_ok(self):
        r = requests.get(_api("/metrics"), timeout=10)
        assert r.status_code == 200
        assert "total_users" in r.json()

    def test_guide_ok(self):
        r = requests.get(_api("/guide"), timeout=10)
        assert r.status_code == 200

    def test_sms_send_ok(self):
        r = requests.post(_api("/auth/sms/send"), json={"phone_number": "+33611111111"}, timeout=10)
        assert r.status_code == 200

    def test_removed_routes_404(self):
        for path in ["/auth/session", "/auth/google/login", "/auth/google/callback"]:
            r = requests.get(_api(path), timeout=10)
            assert r.status_code in (404, 405), f"{path}: {r.status_code}"

    def test_password_hash_not_leaked_on_login(self, db):
        email = f"TEST_leak_{uuid.uuid4().hex[:8]}@gmail.com"
        _register_and_verify(email)
        lg = requests.post(_api("/auth/login"), json={"email": email, "password": "Pass1234"}, timeout=10)
        assert lg.status_code == 200
        body = lg.json()
        assert "password_hash" not in body
        # /auth/me also clean
        me = requests.get(_api("/auth/me"), headers={"Authorization": f"Bearer {body['session_token']}"}, timeout=10)
        assert me.status_code == 200
        assert "password_hash" not in me.json()
        db.users.delete_many({"email": _norm(email)})
