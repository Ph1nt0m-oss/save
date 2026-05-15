"""
iter65 — End-to-end multi-device login approval flow.

Scenarios:
 1. Pending: PC (devA) connected → mobile (devB) login → 202 + request_id
    + session_requests doc with status=pending, requesting_key_id=devB,
    expires_at = created_at + 15 min.
 2. Approve: PC posts /auth/session-decide (with valid session_token) →
    status=approved. Mobile then polls /auth/session-request-status →
    200 + status='approved' + session_token + user data. New
    user_sessions doc exists for devB.
 3. Deny: same setup, decision='deny' → polling returns status='denied'.
 4. Expired: pre-create a session_request with expires_at = -1 min →
    polling auto-flips status to 'expired'.
 5. device_keys.email binding refreshed on successful (200) login.
 6. 409 mismatch when same device_key_id logs in with another email.
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
    client = MongoClient(MONGO_URL)
    return client[DB_NAME]


def _hash(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _ensure_user(db, email: str, password: str) -> str:
    existing = db.users.find_one({"email": email}, {"_id": 0, "user_id": 1})
    if existing:
        db.users.update_one({"email": email}, {"$set": {
            "password_hash": _hash(password),
            "verified": True, "active": True,
        }})
        return existing["user_id"]
    uid = f"TEST_iter65_{int(time.time()*1000)}_{email.split('@')[0]}"
    db.users.insert_one({
        "user_id": uid, "email": email,
        "password_hash": _hash(password),
        "pseudo": email.split("@")[0][:30],
        "verified": True, "active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return uid


def _seed_devkey(db, key_id: str, role: str = "inactive", email: str | None = None):
    db.device_keys.delete_many({"key_id": key_id})
    doc = {
        "key_id": key_id,
        "public_key_jwk": {"kty": "EC", "crv": "P-256", "x": "X", "y": "Y"},
        "role": role,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if email:
        doc["email"] = email
    db.device_keys.insert_one(doc)


def _seed_active_session(db, user_id: str, key_id: str, label: str = "PC test"):
    token = "TEST_iter65_pc_" + secrets.token_urlsafe(12)
    now = datetime.now(timezone.utc)
    db.user_sessions.insert_one({
        "session_token": token,
        "user_id": user_id,
        "device_key_id": key_id,
        "device_label": label,
        "auth_type": "email",
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(days=7)).isoformat(),
    })
    return token


# ===========================================================================
# Scenario 1+2 — Pending + Approve full E2E
# ===========================================================================

class TestMultiDeviceApproveE2E:
    """PC connected → mobile login pending → PC approves → mobile gets token."""

    def test_full_approve_flow(self, db):
        ts = int(time.time())
        email = f"test_iter65_appr_{ts}@gmail.com"
        password = "Pass1234"
        uid = _ensure_user(db, email, password)
        # clean any prior state
        db.user_sessions.delete_many({"user_id": uid})
        db.session_requests.delete_many({"user_id": uid})

        key_a = f"iter65_devA_{ts}"
        key_b = f"iter65_devB_{ts}"
        _seed_devkey(db, key_a, role="inactive", email=email)
        _seed_devkey(db, key_b, role="inactive")

        # PC active session
        pc_token = _seed_active_session(db, uid, key_a, "PC test")

        # Mobile (devB) tries login → 202
        r = requests.post(f"{API}/auth/login", json={
            "email": email, "password": password,
            "device_key_id": key_b, "device_label": "Galaxy test",
        }, timeout=15)
        assert r.status_code == 202, f"Expected 202 pending, got {r.status_code}: {r.text[:200]}"
        body = r.json()
        request_id = body.get("detail", {}).get("request_id")
        assert request_id, f"Missing request_id in body: {body}"

        # Verify session_requests doc
        req = db.session_requests.find_one({"request_id": request_id}, {"_id": 0})
        assert req is not None, "Request not in mongo"
        assert req["status"] == "pending"
        assert req["requesting_key_id"] == key_b
        assert req["user_id"] == uid
        assert req["email"] == email
        created = datetime.fromisoformat(req["created_at"])
        expires = datetime.fromisoformat(req["expires_at"])
        delta = (expires - created).total_seconds()
        assert 890 <= delta <= 910, f"TTL not ~15min (got {delta}s)"

        # PC approves via /auth/session-decide (Bearer header with pc_token)
        r2 = requests.post(
            f"{API}/auth/session-decide",
            json={"request_id": request_id, "decision": "approve"},
            headers={"Authorization": f"Bearer {pc_token}"},
            timeout=15,
        )
        assert r2.status_code == 200, f"Decide failed: {r2.status_code} {r2.text[:200]}"
        assert r2.json().get("status") == "approved"

        # Mobile polls status → approved + session_token + user data
        r3 = requests.post(
            f"{API}/auth/session-request-status",
            json={"request_id": request_id},
            timeout=15,
        )
        assert r3.status_code == 200, f"Poll failed: {r3.status_code} {r3.text[:200]}"
        j = r3.json()
        assert j.get("status") == "approved", f"Wrong status: {j}"
        assert j.get("session_token"), f"No session_token: {j}"
        assert j.get("email") == email, f"User data missing email: {j}"
        assert j.get("user_id") == uid

        # Verify user_sessions doc was created for devB
        new_sess = db.user_sessions.find_one(
            {"session_token": j["session_token"]},
            {"_id": 0},
        )
        assert new_sess is not None, "New session not persisted in user_sessions"
        assert new_sess["device_key_id"] == key_b
        assert new_sess["user_id"] == uid

        # Idempotency — second poll should return same token (not 404).
        r4 = requests.post(
            f"{API}/auth/session-request-status",
            json={"request_id": request_id}, timeout=10,
        )
        assert r4.status_code == 200
        assert r4.json().get("session_token") == j["session_token"], "Token must be idempotent"


# ===========================================================================
# Scenario 3 — Deny
# ===========================================================================

class TestMultiDeviceDenyE2E:
    def test_full_deny_flow(self, db):
        ts = int(time.time()) + 100
        email = f"test_iter65_deny_{ts}@gmail.com"
        password = "Pass1234"
        uid = _ensure_user(db, email, password)
        db.user_sessions.delete_many({"user_id": uid})
        db.session_requests.delete_many({"user_id": uid})

        key_a = f"iter65_devA_deny_{ts}"
        key_b = f"iter65_devB_deny_{ts}"
        _seed_devkey(db, key_a, role="inactive", email=email)
        _seed_devkey(db, key_b, role="inactive")
        pc_token = _seed_active_session(db, uid, key_a, "PC deny")

        r = requests.post(f"{API}/auth/login", json={
            "email": email, "password": password,
            "device_key_id": key_b, "device_label": "Galaxy deny",
        }, timeout=15)
        assert r.status_code == 202
        request_id = r.json()["detail"]["request_id"]

        r2 = requests.post(
            f"{API}/auth/session-decide",
            json={"request_id": request_id, "decision": "deny"},
            headers={"Authorization": f"Bearer {pc_token}"},
            timeout=15,
        )
        assert r2.status_code == 200
        assert r2.json().get("status") == "denied"

        r3 = requests.post(
            f"{API}/auth/session-request-status",
            json={"request_id": request_id}, timeout=10,
        )
        assert r3.status_code == 200
        assert r3.json().get("status") == "denied"
        # No session_token should be returned for denied
        assert "session_token" not in r3.json()


# ===========================================================================
# Scenario 4 — Expiration auto-flip on poll
# ===========================================================================

class TestSessionRequestExpiration:
    def test_polling_auto_expires(self, db):
        ts = int(time.time()) + 200
        email = f"test_iter65_exp_{ts}@gmail.com"
        password = "Pass1234"
        uid = _ensure_user(db, email, password)
        db.session_requests.delete_many({"user_id": uid})

        # Pre-insert an already-expired request directly in Mongo.
        request_id = "TEST_iter65_expired_" + secrets.token_urlsafe(8)
        now = datetime.now(timezone.utc)
        db.session_requests.insert_one({
            "request_id": request_id,
            "user_id": uid,
            "email": email,
            "requesting_key_id": f"iter65_dev_expired_{ts}",
            "requesting_label": "expired-mobile",
            "status": "pending",
            "created_at": (now - timedelta(minutes=20)).isoformat(),
            "expires_at": (now - timedelta(minutes=1)).isoformat(),  # already past
        })

        r = requests.post(
            f"{API}/auth/session-request-status",
            json={"request_id": request_id}, timeout=10,
        )
        assert r.status_code == 200
        assert r.json().get("status") == "expired", f"Expected expired, got {r.json()}"

        # And verify Mongo was updated.
        doc = db.session_requests.find_one({"request_id": request_id}, {"_id": 0, "status": 1})
        assert doc["status"] == "expired", f"DB not flipped to expired: {doc}"


# ===========================================================================
# Scenario 5+6 — device_keys.email binding
# ===========================================================================

class TestDeviceEmailBinding:
    def test_email_set_on_successful_login(self, db):
        ts = int(time.time()) + 300
        email = f"test_iter65_bind_{ts}@gmail.com"
        password = "Pass1234"
        _ensure_user(db, email, password)
        key_id = f"iter65_bind_dev_{ts}"
        # Seed devkey with NO email
        _seed_devkey(db, key_id, role="inactive")
        # Ensure no active session on a different device for this user
        user = db.users.find_one({"email": email}, {"_id": 0, "user_id": 1})
        db.user_sessions.delete_many({"user_id": user["user_id"]})

        r = requests.post(f"{API}/auth/login", json={
            "email": email, "password": password,
            "device_key_id": key_id, "device_label": "bind-test",
        }, timeout=15)
        assert r.status_code == 200, f"Login failed: {r.status_code} {r.text[:200]}"

        doc = db.device_keys.find_one({"key_id": key_id}, {"_id": 0, "email": 1})
        assert doc and doc.get("email") == email, f"Binding not set: {doc}"

    def test_409_on_email_mismatch(self, db):
        ts = int(time.time()) + 400
        email_a = f"test_iter65_a_{ts}@gmail.com"
        email_b = f"test_iter65_b_{ts}@gmail.com"
        password = "Pass1234"
        _ensure_user(db, email_a, password)
        _ensure_user(db, email_b, password)
        key_id = f"iter65_mismatch_{ts}"
        _seed_devkey(db, key_id, role="inactive", email=email_a)

        r = requests.post(f"{API}/auth/login", json={
            "email": email_b, "password": password,
            "device_key_id": key_id, "device_label": "mismatch",
        }, timeout=15)
        assert r.status_code == 409, f"Expected 409, got {r.status_code}: {r.text[:200]}"
        detail = r.json().get("detail", "")
        assert "déjà lié à un autre compte" in detail
        assert email_a in detail


# ===========================================================================
# Cleanup teardown
# ===========================================================================

@pytest.fixture(scope="module", autouse=True)
def cleanup(db):
    yield
    # Delete TEST_iter65_* artefacts
    db.users.delete_many({"user_id": {"$regex": "^TEST_iter65_"}})
    db.user_sessions.delete_many({"session_token": {"$regex": "^TEST_iter65_"}})
    db.session_requests.delete_many({"request_id": {"$regex": "^TEST_iter65_"}})
    db.device_keys.delete_many({"key_id": {"$regex": "^iter65_"}})
