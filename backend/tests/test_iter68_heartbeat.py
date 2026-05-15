"""iter68 — explicit POST /api/auth/heartbeat endpoint + 60s threshold seeds.

Tests:
 1. POST /auth/heartbeat without Bearer → 401.
 2. POST /auth/heartbeat with valid Bearer → 200 {ok:true, now:iso} +
    user_sessions.last_seen_at refreshed (within 5s of now).
 3. Threshold-60s scenario with fresh (-30s) → 202.
 4. Threshold-60s scenario with stale (-90s) → 200; remove stale, login
    another device → 200.
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


def _hash(pw):
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def _ensure_user(db, email, password):
    existing = db.users.find_one({"email": email}, {"_id": 0, "user_id": 1})
    if existing:
        db.users.update_one({"email": email}, {"$set": {
            "password_hash": _hash(password), "verified": True, "active": True}})
        return existing["user_id"]
    uid = f"TEST_iter68_{int(time.time()*1000)}_{email.split('@')[0]}"
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
    if email:
        doc["email"] = email
    db.device_keys.insert_one(doc)


def _seed_session(db, uid, key_id, last_seen_offset_sec=0, token_prefix="TEST_iter68_sess_"):
    token = token_prefix + secrets.token_urlsafe(12)
    now = datetime.now(timezone.utc)
    seen = now + timedelta(seconds=last_seen_offset_sec)
    db.user_sessions.insert_one({
        "session_token": token, "user_id": uid,
        "device_key_id": key_id, "device_label": "iter68-test",
        "auth_type": "email",
        "created_at": now.isoformat(),
        "last_seen_at": seen.isoformat(),
        "expires_at": (now + timedelta(days=7)).isoformat(),
    })
    return token


# ---------------------------------------------------------------------------
# 1. Heartbeat endpoint
# ---------------------------------------------------------------------------
class TestHeartbeatEndpoint:
    def test_heartbeat_without_token_401(self):
        r = requests.post(f"{API}/auth/heartbeat", timeout=10)
        assert r.status_code == 401, f"expected 401 without token, got {r.status_code}: {r.text[:200]}"

    def test_heartbeat_with_invalid_token_401(self):
        r = requests.post(f"{API}/auth/heartbeat",
                          headers={"Authorization": "Bearer NOPE_NOT_A_TOKEN"},
                          timeout=10)
        assert r.status_code == 401

    def test_heartbeat_success_updates_last_seen(self, db):
        ts = int(time.time())
        email = f"test_iter68_hb_{ts}@gmail.com"
        pwd = "Pass1234"
        uid = _ensure_user(db, email, pwd)
        db.user_sessions.delete_many({"user_id": uid})
        # Seed a session with last_seen_at = -5 min (stale)
        token = _seed_session(db, uid, f"iter68_hb_{ts}", last_seen_offset_sec=-300)
        # Hit heartbeat
        r = requests.post(f"{API}/auth/heartbeat",
                          headers={"Authorization": f"Bearer {token}"}, timeout=10)
        assert r.status_code == 200, f"heartbeat failed: {r.status_code} {r.text[:200]}"
        body = r.json()
        assert body.get("ok") is True, f"missing ok=true: {body}"
        assert "now" in body and isinstance(body["now"], str)
        # Returned `now` should parse as ISO and be very close to current UTC
        srv_now = datetime.fromisoformat(body["now"].replace("Z", "+00:00"))
        delta = abs((datetime.now(timezone.utc) - srv_now).total_seconds())
        assert delta < 10, f"server `now` skewed by {delta}s"
        # DB last_seen_at must be updated to ~now
        doc = db.user_sessions.find_one({"session_token": token},
                                        {"_id": 0, "last_seen_at": 1})
        assert doc, "session disappeared"
        ls = datetime.fromisoformat(doc["last_seen_at"])
        age = (datetime.now(timezone.utc) - ls).total_seconds()
        assert 0 <= age < 5, f"last_seen_at not refreshed (age={age}s)"


# ---------------------------------------------------------------------------
# 2. 60s threshold seed scenario (request spec test case)
# ---------------------------------------------------------------------------
class TestThreshold60sSpecScenario:
    def test_sessionA_fresh_blocks_then_remove_then_sessionB_stale_allows(self, db):
        ts = int(time.time()) + 600
        email = f"iter68_{ts}@gmail.com"
        pwd = "Pass1234"
        uid = _ensure_user(db, email, pwd)
        db.user_sessions.delete_many({"user_id": uid})
        db.session_requests.delete_many({"user_id": uid})

        kA = f"iter68_specA_{ts}"
        kB = f"iter68_specB_{ts}"
        kC = f"iter68_specC_{ts}"
        kD = f"iter68_specD_{ts}"
        _seed_devkey(db, kA, email=email)
        _seed_devkey(db, kB)
        _seed_devkey(db, kC)
        _seed_devkey(db, kD)

        # sessionA fresh (-3s) — active (window iter76 = 8s)
        sessA = _seed_session(db, uid, kA, last_seen_offset_sec=-3)
        # sessionB stale (-30s) — outside iter76 8s window
        sessB = _seed_session(db, uid, kB, last_seen_offset_sec=-30)

        # Login from device C → should be blocked by sessionA (fresh) → 202
        rC = requests.post(f"{API}/auth/login", json={
            "email": email, "password": pwd,
            "device_key_id": kC, "device_label": "iter68-C"}, timeout=15)
        assert rC.status_code == 202, (
            f"device C login: sessionA fresh should block → 202, got {rC.status_code}: {rC.text[:200]}"
        )

        # Now remove sessionA → only stale sessionB remains
        db.user_sessions.delete_many({"session_token": sessA})
        db.session_requests.delete_many({"user_id": uid})

        # Login from device D → only stale sessionB remains → 200
        rD = requests.post(f"{API}/auth/login", json={
            "email": email, "password": pwd,
            "device_key_id": kD, "device_label": "iter68-D"}, timeout=15)
        assert rD.status_code == 200, (
            f"device D login: only stale sessionB → 200, got {rD.status_code}: {rD.text[:200]}"
        )
        assert rD.json().get("session_token")


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module", autouse=True)
def cleanup(db):
    yield
    db.users.delete_many({"user_id": {"$regex": "^TEST_iter68_"}})
    db.user_sessions.delete_many({"session_token": {"$regex": "^TEST_iter68_"}})
    db.session_requests.delete_many({"user_id": {"$regex": "^TEST_iter68_"}})
    db.device_keys.delete_many({"key_id": {"$regex": "^iter68_"}})
