"""
iter66 — last_seen_at heartbeat + pending-approval gating.

Scenarios:
 1. /auth/me heartbeat: GET /api/auth/me with Bearer → user_sessions.last_seen_at
    is updated to ~now.
 2. last_seen_at init on /auth/login (200) and on /auth/session-decide approve.
 3. Stale active session (last_seen_at = -15 min) → another device login
    returns 200 (NOT 202): the "abandoned" session must not trigger an
    approval prompt.
 4. Fresh active session (last_seen_at = now) → another device login
    returns 202 (the iter65 flow still works).
"""
from __future__ import annotations

import os
import time
import secrets
from datetime import datetime, timezone, timedelta

import bcrypt
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")
assert BASE_URL and MONGO_URL and DB_NAME, "Missing env config"


@pytest.fixture(scope="module")
def db():
    return MongoClient(MONGO_URL)[DB_NAME]


def _hash(pw): return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def _ensure_user(db, email, password):
    existing = db.users.find_one({"email": email}, {"_id": 0, "user_id": 1})
    if existing:
        db.users.update_one({"email": email}, {"$set": {
            "password_hash": _hash(password), "verified": True, "active": True}})
        return existing["user_id"]
    uid = f"TEST_iter66_{int(time.time()*1000)}_{email.split('@')[0]}"
    db.users.insert_one({
        "user_id": uid, "email": email, "password_hash": _hash(password),
        "pseudo": email.split("@")[0][:30], "verified": True, "active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return uid


def _seed_devkey(db, key_id, role="inactive", email=None):
    db.device_keys.delete_many({"key_id": key_id})
    doc = {"key_id": key_id,
           "public_key_jwk": {"kty": "EC", "crv": "P-256", "x": "X", "y": "Y"},
           "role": role, "created_at": datetime.now(timezone.utc).isoformat()}
    if email: doc["email"] = email
    db.device_keys.insert_one(doc)


def _seed_active_session(db, uid, key_id, last_seen_offset_min=0):
    """Insert an active session with last_seen_at = now + offset_min."""
    token = "TEST_iter66_sess_" + secrets.token_urlsafe(12)
    now = datetime.now(timezone.utc)
    seen = now + timedelta(minutes=last_seen_offset_min)
    db.user_sessions.insert_one({
        "session_token": token,
        "user_id": uid,
        "device_key_id": key_id,
        "device_label": "iter66-test",
        "auth_type": "email",
        "created_at": now.isoformat(),
        "last_seen_at": seen.isoformat(),
        "expires_at": (now + timedelta(days=7)).isoformat(),
    })
    return token


# ===========================================================================
# 1. /auth/me heartbeat
# ===========================================================================

class TestAuthMeHeartbeat:
    def test_me_updates_last_seen_at(self, db):
        ts = int(time.time())
        email = f"test_iter66_hb_{ts}@gmail.com"
        password = "Pass1234"
        uid = _ensure_user(db, email, password)
        db.user_sessions.delete_many({"user_id": uid})

        # Seed session w/ last_seen_at = -5 min
        token = "TEST_iter66_hb_" + secrets.token_urlsafe(8)
        now = datetime.now(timezone.utc)
        stale = (now - timedelta(minutes=5)).isoformat()
        db.user_sessions.insert_one({
            "session_token": token, "user_id": uid,
            "device_key_id": f"iter66_hb_dev_{ts}", "device_label": "hb",
            "auth_type": "email",
            "created_at": (now - timedelta(minutes=5)).isoformat(),
            "last_seen_at": stale,
            "expires_at": (now + timedelta(days=7)).isoformat(),
        })

        r = requests.get(f"{API}/auth/me",
                         headers={"Authorization": f"Bearer {token}"}, timeout=10)
        assert r.status_code == 200, f"/auth/me failed: {r.status_code} {r.text[:200]}"

        doc = db.user_sessions.find_one({"session_token": token},
                                        {"_id": 0, "last_seen_at": 1})
        assert doc is not None
        new_seen = datetime.fromisoformat(doc["last_seen_at"])
        # Must be within last 30s
        delta = (datetime.now(timezone.utc) - new_seen).total_seconds()
        assert 0 <= delta < 30, f"last_seen_at not refreshed: {doc['last_seen_at']} ({delta}s old)"


# ===========================================================================
# 2. last_seen_at init at login (200)
# ===========================================================================

class TestLoginInitLastSeen:
    def test_login_inits_last_seen_at(self, db):
        ts = int(time.time()) + 50
        email = f"test_iter66_init_{ts}@gmail.com"
        password = "Pass1234"
        uid = _ensure_user(db, email, password)
        db.user_sessions.delete_many({"user_id": uid})
        key = f"iter66_init_dev_{ts}"
        _seed_devkey(db, key, role="inactive")

        r = requests.post(f"{API}/auth/login", json={
            "email": email, "password": password,
            "device_key_id": key, "device_label": "init-test",
        }, timeout=15)
        assert r.status_code == 200, f"Login failed: {r.status_code} {r.text[:200]}"
        tok = r.json().get("session_token")
        assert tok

        doc = db.user_sessions.find_one({"session_token": tok},
                                        {"_id": 0, "last_seen_at": 1, "created_at": 1})
        assert doc.get("last_seen_at"), f"last_seen_at missing: {doc}"
        # last_seen_at should equal created_at (or be within 1s)
        ls = datetime.fromisoformat(doc["last_seen_at"])
        cr = datetime.fromisoformat(doc["created_at"])
        assert abs((ls - cr).total_seconds()) < 2, f"last_seen_at != created_at: {doc}"


# ===========================================================================
# 3. Stale session → no 202 (active_other gating with last_seen_at>now-10m)
# ===========================================================================

class TestStaleSessionNoApprovalPrompt:
    """If the user's only other active session has been silent for >10 min,
    a new device login must NOT raise 202 — it should succeed straight away."""

    def test_stale_session_returns_200(self, db):
        ts = int(time.time()) + 100
        email = f"test_iter66_stale_{ts}@gmail.com"
        password = "Pass1234"
        uid = _ensure_user(db, email, password)
        db.user_sessions.delete_many({"user_id": uid})
        db.session_requests.delete_many({"user_id": uid})

        key_a = f"iter66_stale_A_{ts}"
        key_b = f"iter66_stale_B_{ts}"
        _seed_devkey(db, key_a, role="inactive", email=email)
        _seed_devkey(db, key_b, role="inactive")
        # Seed an active session on A with last_seen_at = -15 min (stale)
        _seed_active_session(db, uid, key_a, last_seen_offset_min=-15)

        r = requests.post(f"{API}/auth/login", json={
            "email": email, "password": password,
            "device_key_id": key_b, "device_label": "stale-B",
        }, timeout=15)
        assert r.status_code == 200, (
            f"Stale session should NOT block login. Got {r.status_code}: {r.text[:200]}"
        )
        assert r.json().get("session_token")


# ===========================================================================
# 4. Fresh session → 202 (iter65 flow still works post-iter66)
# ===========================================================================

class TestFreshSessionTriggers202:
    def test_fresh_session_returns_202(self, db):
        ts = int(time.time()) + 200
        email = f"test_iter66_fresh_{ts}@gmail.com"
        password = "Pass1234"
        uid = _ensure_user(db, email, password)
        db.user_sessions.delete_many({"user_id": uid})
        db.session_requests.delete_many({"user_id": uid})

        key_a = f"iter66_fresh_A_{ts}"
        key_b = f"iter66_fresh_B_{ts}"
        _seed_devkey(db, key_a, role="inactive", email=email)
        _seed_devkey(db, key_b, role="inactive")
        # Active session on A, last_seen_at = NOW (fresh)
        _seed_active_session(db, uid, key_a, last_seen_offset_min=0)

        r = requests.post(f"{API}/auth/login", json={
            "email": email, "password": password,
            "device_key_id": key_b, "device_label": "fresh-B",
        }, timeout=15)
        assert r.status_code == 202, (
            f"Fresh session should trigger 202, got {r.status_code}: {r.text[:200]}"
        )
        assert r.json().get("detail", {}).get("request_id")


# ===========================================================================
# 5. last_seen_at init on /auth/session-decide approve
# ===========================================================================

class TestApproveInitLastSeen:
    def test_approve_inits_last_seen_at(self, db):
        ts = int(time.time()) + 300
        email = f"test_iter66_appr_{ts}@gmail.com"
        password = "Pass1234"
        uid = _ensure_user(db, email, password)
        db.user_sessions.delete_many({"user_id": uid})
        db.session_requests.delete_many({"user_id": uid})

        key_a = f"iter66_appr_A_{ts}"
        key_b = f"iter66_appr_B_{ts}"
        _seed_devkey(db, key_a, role="inactive", email=email)
        _seed_devkey(db, key_b, role="inactive")
        pc_token = _seed_active_session(db, uid, key_a, last_seen_offset_min=0)

        r = requests.post(f"{API}/auth/login", json={
            "email": email, "password": password,
            "device_key_id": key_b, "device_label": "appr-B",
        }, timeout=15)
        assert r.status_code == 202
        request_id = r.json()["detail"]["request_id"]

        # Approve
        r2 = requests.post(f"{API}/auth/session-decide",
                           json={"request_id": request_id, "decision": "approve"},
                           headers={"Authorization": f"Bearer {pc_token}"}, timeout=15)
        assert r2.status_code == 200

        r3 = requests.post(f"{API}/auth/session-request-status",
                           json={"request_id": request_id}, timeout=10)
        assert r3.status_code == 200
        new_tok = r3.json().get("session_token")
        assert new_tok

        # The newly-issued session for B must have last_seen_at set
        doc = db.user_sessions.find_one({"session_token": new_tok},
                                        {"_id": 0, "last_seen_at": 1, "created_at": 1})
        assert doc and doc.get("last_seen_at"), f"approve-session missing last_seen_at: {doc}"
        ls = datetime.fromisoformat(doc["last_seen_at"])
        cr = datetime.fromisoformat(doc["created_at"])
        assert abs((ls - cr).total_seconds()) < 2


# ===========================================================================
# Cleanup
# ===========================================================================

@pytest.fixture(scope="module", autouse=True)
def cleanup(db):
    yield
    db.users.delete_many({"user_id": {"$regex": "^TEST_iter66_"}})
    db.user_sessions.delete_many({"session_token": {"$regex": "^TEST_iter66_"}})
    db.session_requests.delete_many({"user_id": {"$regex": "^TEST_iter66_"}})
    db.device_keys.delete_many({"key_id": {"$regex": "^iter66_"}})
