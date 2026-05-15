"""iter67 — last_seen_at threshold (tightened to 60s in iter68).

Tests (patched for iter68 — seconds-based offsets):
 1. Session active at -30s (within 60s window) → another device login → 202 pending.
 2. Session active at -120s (>60s, stale) → another device login → 200 (no approval needed).
 3. Boundary check: session at -90s must be considered stale (200, not 202).
"""
from __future__ import annotations
import os, time, secrets
from datetime import datetime, timezone, timedelta
import bcrypt, pytest, requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")
assert BASE_URL and MONGO_URL and DB_NAME


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
    uid = f"TEST_iter67_{int(time.time()*1000)}_{email.split('@')[0]}"
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


def _seed_session(db, uid, key_id, last_seen_offset_sec=0):
    token = "TEST_iter67_sess_" + secrets.token_urlsafe(12)
    now = datetime.now(timezone.utc)
    seen = now + timedelta(seconds=last_seen_offset_sec)
    db.user_sessions.insert_one({
        "session_token": token, "user_id": uid,
        "device_key_id": key_id, "device_label": "iter67-test",
        "auth_type": "email",
        "created_at": now.isoformat(),
        "last_seen_at": seen.isoformat(),
        "expires_at": (now + timedelta(days=7)).isoformat(),
    })
    return token


class TestThreshold60Sec:
    def test_session_30s_old_triggers_202(self, db):
        """Session with last_seen_at = -30s (fresh, within 60s) → 202."""
        ts = int(time.time())
        email = f"test_iter67_30s_{ts}@gmail.com"
        pwd = "Pass1234"
        uid = _ensure_user(db, email, pwd)
        db.user_sessions.delete_many({"user_id": uid})
        db.session_requests.delete_many({"user_id": uid})
        ka, kb = f"iter67_30s_A_{ts}", f"iter67_30s_B_{ts}"
        _seed_devkey(db, ka, email=email)
        _seed_devkey(db, kb)
        _seed_session(db, uid, ka, last_seen_offset_sec=-30)
        r = requests.post(f"{API}/auth/login", json={
            "email": email, "password": pwd,
            "device_key_id": kb, "device_label": "30s-B"}, timeout=15)
        assert r.status_code == 202, f"-30s session should trigger 202, got {r.status_code}: {r.text[:200]}"

    def test_session_120s_old_returns_200(self, db):
        """Session at -120s (>60s, stale) → 200 OK."""
        ts = int(time.time()) + 50
        email = f"test_iter67_120s_{ts}@gmail.com"
        pwd = "Pass1234"
        uid = _ensure_user(db, email, pwd)
        db.user_sessions.delete_many({"user_id": uid})
        db.session_requests.delete_many({"user_id": uid})
        ka, kb = f"iter67_120s_A_{ts}", f"iter67_120s_B_{ts}"
        _seed_devkey(db, ka, email=email)
        _seed_devkey(db, kb)
        _seed_session(db, uid, ka, last_seen_offset_sec=-120)
        r = requests.post(f"{API}/auth/login", json={
            "email": email, "password": pwd,
            "device_key_id": kb, "device_label": "120s-B"}, timeout=15)
        assert r.status_code == 200, f"-120s stale session should return 200, got {r.status_code}: {r.text[:200]}"

    def test_session_90s_old_returns_200(self, db):
        """Boundary: session at -90s must be stale → 200."""
        ts = int(time.time()) + 150
        email = f"test_iter67_90s_{ts}@gmail.com"
        pwd = "Pass1234"
        uid = _ensure_user(db, email, pwd)
        db.user_sessions.delete_many({"user_id": uid})
        db.session_requests.delete_many({"user_id": uid})
        ka, kb = f"iter67_90s_A_{ts}", f"iter67_90s_B_{ts}"
        _seed_devkey(db, ka, email=email)
        _seed_devkey(db, kb)
        _seed_session(db, uid, ka, last_seen_offset_sec=-90)
        r = requests.post(f"{API}/auth/login", json={
            "email": email, "password": pwd,
            "device_key_id": kb, "device_label": "90s-B"}, timeout=15)
        assert r.status_code == 200, f"-90s session should be stale → 200, got {r.status_code}: {r.text[:200]}"


@pytest.fixture(scope="module", autouse=True)
def cleanup(db):
    yield
    db.users.delete_many({"user_id": {"$regex": "^TEST_iter67_"}})
    db.user_sessions.delete_many({"session_token": {"$regex": "^TEST_iter67_"}})
    db.session_requests.delete_many({"user_id": {"$regex": "^TEST_iter67_"}})
    db.device_keys.delete_many({"key_id": {"$regex": "^iter67_"}})
