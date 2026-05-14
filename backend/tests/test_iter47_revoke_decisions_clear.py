"""Iter47 — backend tests for:

(1) POST /api/devices/revoke is now IDEMPOTENT:
    - Unknown target_key_id returns 200 {success: true, existed: false}
    - A 'revoke' decision is still logged in device_decisions
    - 403 without a valid creator signature

(2) NEW: POST /api/devices/decisions/clear (creator-only):
    - Wipes ALL rows of device_decisions, returns {deleted: N}
    - The kept creator device row in device_keys remains intact
    - The other live device states (creator/approved/pending) are untouched
    - 403 without a valid creator signature

(3) Regression iter46:
    - /api/auth/session-request-status remains idempotent (same token on
      repeat polls; unknown id -> {status:'expired'} HTTP 200)
    - /api/auth/login back-compat (no device_key_id)

The KEPT creator key 'dev_a797438afc28c67923881d46ae2971c1' must NEVER be
revoked, disconnected or deleted.
"""
from __future__ import annotations

import base64
import os
import secrets
from typing import Tuple

import pytest
import requests
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives import hashes
from pymongo import MongoClient


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # last-resort fallback to the public preview URL declared in test_credentials.md
    BASE_URL = "https://no-code-builder-25.preview.emergentagent.com"
API = f"{BASE_URL}/api"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

KEPT_CREATOR_KEY_ID = "dev_a797438afc28c67923881d46ae2971c1"

USER_EMAIL = "test_dash_1777658375@gmail.com"
USER_PASS = "Pass1234"


# ----- helpers ----------------------------------------------------------------


def _b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("ascii").rstrip("=")


def _b64url_int(n: int, length: int = 32) -> str:
    return _b64url(n.to_bytes(length, "big"))


def _b64url_decode(s: str) -> bytes:
    pad = "=" * ((4 - len(s) % 4) % 4)
    return base64.urlsafe_b64decode(s + pad)


def gen_keypair() -> Tuple[ec.EllipticCurvePrivateKey, dict]:
    priv = ec.generate_private_key(ec.SECP256R1())
    pub = priv.public_key().public_numbers()
    jwk = {
        "kty": "EC",
        "crv": "P-256",
        "x": _b64url_int(pub.x),
        "y": _b64url_int(pub.y),
    }
    return priv, jwk


def sign_nonce(priv: ec.EllipticCurvePrivateKey, nonce_b64url: str) -> str:
    nonce_bytes = _b64url_decode(nonce_b64url)
    der = priv.sign(nonce_bytes, ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    raw = r.to_bytes(32, "big") + s.to_bytes(32, "big")
    return _b64url(raw)


def register_device(label: str = "TEST_iter47") -> Tuple[ec.EllipticCurvePrivateKey, str, dict]:
    priv, jwk = gen_keypair()
    r = requests.post(f"{API}/devices/register", json={"public_key_jwk": jwk, "label": label}, timeout=15)
    r.raise_for_status()
    return priv, r.json()["key_id"], jwk


def get_nonce(key_id: str) -> str:
    r = requests.post(f"{API}/devices/challenge", json={"key_id": key_id}, timeout=15)
    r.raise_for_status()
    return r.json()["nonce"]


def creator_signed(priv: ec.EllipticCurvePrivateKey, key_id: str, extra: dict | None = None) -> dict:
    nonce = get_nonce(key_id)
    sig = sign_nonce(priv, nonce)
    payload = {"key_id": key_id, "nonce": nonce, "signature": sig}
    if extra:
        payload.update(extra)
    return payload


# ----- fixtures ---------------------------------------------------------------


@pytest.fixture(scope="module")
def mongo():
    cli = MongoClient(MONGO_URL, serverSelectionTimeoutMS=3000)
    db = cli[DB_NAME]
    yield db
    cli.close()


@pytest.fixture(scope="module")
def cleanup(mongo):
    """Track and clean up ephemeral keys we create. Never touches the kept creator."""
    created_keys: list[str] = []
    yield {"keys": created_keys}
    safe = [k for k in created_keys if k != KEPT_CREATOR_KEY_ID]
    if safe:
        mongo.device_keys.delete_many({"key_id": {"$in": safe}})
        mongo.device_nonces.delete_many({"key_id": {"$in": safe}})
        mongo.user_sessions.delete_many({"device_key_id": {"$in": safe}})
    # Belt and braces: nuke any TEST_iter47 leftovers
    mongo.device_keys.delete_many({"label": {"$regex": "^TEST_iter47"}})


@pytest.fixture(scope="module")
def temp_creator(mongo, cleanup):
    """Spin up a throwaway key, promote to 'creator' role via DB write so we
    can sign creator-only endpoints. NEVER touches the kept creator."""
    priv, key_id, _ = register_device("TEST_iter47_tmpcreator")
    cleanup["keys"].append(key_id)
    mongo.device_keys.update_one({"key_id": key_id}, {"$set": {"role": "creator"}})
    yield {"priv": priv, "key_id": key_id}
    mongo.device_keys.delete_one({"key_id": key_id})


# ============================================================================
# (1) /devices/revoke idempotent
# ============================================================================


def test_revoke_unknown_key_returns_200_existed_false(mongo, temp_creator):
    """The headline iter47 change: revoke of an already-gone key still 200s,
    returns existed=false, and writes the audit entry."""
    fake_key = "dev_" + secrets.token_hex(16)
    # Sanity: ensure key really doesn't exist
    assert mongo.device_keys.find_one({"key_id": fake_key}) is None

    # Count revoke decisions for this fake_key before (should be 0)
    pre = mongo.device_decisions.count_documents({"action": "revoke", "target_key_id": fake_key})
    assert pre == 0

    payload = creator_signed(temp_creator["priv"], temp_creator["key_id"],
                             {"target_key_id": fake_key})
    r = requests.post(f"{API}/devices/revoke", json=payload, timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("success") is True
    assert body.get("existed") is False, f"expected existed=False, got {body}"

    # Audit entry must be present
    audit = mongo.device_decisions.find_one({"action": "revoke", "target_key_id": fake_key})
    assert audit is not None, "revoke decision was NOT logged for unknown key"
    assert audit.get("by_key_id") == temp_creator["key_id"]


def test_revoke_existing_key_returns_existed_true(mongo, temp_creator, cleanup):
    """Sanity: pre-existing target still returns existed=True (regression of iter46 behaviour)."""
    _, victim_key, _ = register_device("TEST_iter47_revoke_existing")
    cleanup["keys"].append(victim_key)
    assert mongo.device_keys.find_one({"key_id": victim_key}) is not None

    payload = creator_signed(temp_creator["priv"], temp_creator["key_id"],
                             {"target_key_id": victim_key})
    r = requests.post(f"{API}/devices/revoke", json=payload, timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("success") is True
    assert body.get("existed") is True

    # And it really got deleted
    assert mongo.device_keys.find_one({"key_id": victim_key}) is None


def test_revoke_idempotent_call_twice_same_key(mongo, temp_creator, cleanup):
    """Call revoke on the same target twice — both succeed; second one shows existed=false."""
    _, victim_key, _ = register_device("TEST_iter47_revoke_twice")
    cleanup["keys"].append(victim_key)

    # 1st revoke
    p1 = creator_signed(temp_creator["priv"], temp_creator["key_id"],
                       {"target_key_id": victim_key})
    r1 = requests.post(f"{API}/devices/revoke", json=p1, timeout=15)
    assert r1.status_code == 200, r1.text
    assert r1.json().get("existed") is True

    # 2nd revoke (same key) — must be idempotent
    p2 = creator_signed(temp_creator["priv"], temp_creator["key_id"],
                       {"target_key_id": victim_key})
    r2 = requests.post(f"{API}/devices/revoke", json=p2, timeout=15)
    assert r2.status_code == 200, r2.text
    body2 = r2.json()
    assert body2.get("success") is True
    assert body2.get("existed") is False

    # Audit should have 2 revoke entries for this target
    cnt = mongo.device_decisions.count_documents({"action": "revoke", "target_key_id": victim_key})
    assert cnt >= 2, f"expected >=2 revoke audit entries, got {cnt}"


def test_revoke_without_valid_signature_returns_403(cleanup):
    """Wrong key / wrong sig → 403."""
    priv, key_id, _ = register_device("TEST_iter47_nosig")
    cleanup["keys"].append(key_id)
    # This key is just 'pending' — not creator — should be rejected
    nonce = get_nonce(key_id)
    sig = sign_nonce(priv, nonce)
    r = requests.post(f"{API}/devices/revoke",
                      json={"key_id": key_id, "nonce": nonce, "signature": sig,
                            "target_key_id": "dev_" + secrets.token_hex(16)},
                      timeout=15)
    assert r.status_code == 403, r.text


def test_revoke_with_bad_signature_returns_403(temp_creator):
    """Creator key but signature from a DIFFERENT private key → 403."""
    nonce = get_nonce(temp_creator["key_id"])
    other_priv, _ = gen_keypair()
    bad_sig = sign_nonce(other_priv, nonce)
    r = requests.post(f"{API}/devices/revoke",
                      json={"key_id": temp_creator["key_id"], "nonce": nonce,
                            "signature": bad_sig,
                            "target_key_id": "dev_" + secrets.token_hex(16)},
                      timeout=15)
    assert r.status_code == 403, r.text


# ============================================================================
# (2) /devices/decisions/clear
# ============================================================================


def test_decisions_clear_without_signature_returns_403():
    """No signature at all → 403."""
    r = requests.post(f"{API}/devices/decisions/clear",
                      json={"key_id": "dev_" + secrets.token_hex(16),
                            "nonce": "abc", "signature": "abc"},
                      timeout=15)
    assert r.status_code == 403, r.text


def test_decisions_clear_non_creator_returns_403(cleanup):
    """A pending-role key cannot wipe history."""
    priv, key_id, _ = register_device("TEST_iter47_clear_nopriv")
    cleanup["keys"].append(key_id)
    payload = creator_signed(priv, key_id)
    r = requests.post(f"{API}/devices/decisions/clear", json=payload, timeout=15)
    assert r.status_code == 403, r.text


def test_decisions_clear_wipes_collection_but_keeps_device_states(mongo, temp_creator, cleanup):
    """The critical iter47 invariant:
       - device_decisions becomes empty after clear
       - device_keys roles (creator/approved/pending) are UNCHANGED
       - kept creator key remains untouched
    """
    # 1. Seed a few decisions by registering & revoking ephemeral devices
    for i in range(3):
        _, v, _ = register_device(f"TEST_iter47_seed_dec_{i}")
        cleanup["keys"].append(v)
        p = creator_signed(temp_creator["priv"], temp_creator["key_id"],
                          {"target_key_id": v})
        requests.post(f"{API}/devices/revoke", json=p, timeout=15)

    # Confirm decisions table has rows
    pre_count = mongo.device_decisions.count_documents({})
    assert pre_count > 0, "expected device_decisions to have some rows before clear"

    # Snapshot device_keys (roles + key_ids) BEFORE clear
    before_keys = {d["key_id"]: d.get("role") for d in mongo.device_keys.find({}, {"key_id": 1, "role": 1})}
    assert KEPT_CREATOR_KEY_ID in before_keys, "kept creator missing pre-clear"
    assert before_keys[KEPT_CREATOR_KEY_ID] == "creator"
    assert temp_creator["key_id"] in before_keys
    assert before_keys[temp_creator["key_id"]] == "creator"

    # 2. Call /decisions/clear
    payload = creator_signed(temp_creator["priv"], temp_creator["key_id"])
    r = requests.post(f"{API}/devices/decisions/clear", json=payload, timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "deleted" in body
    assert isinstance(body["deleted"], int)
    assert body["deleted"] == pre_count, f"deleted={body['deleted']} but pre_count={pre_count}"

    # 3. device_decisions should now be empty
    post_count = mongo.device_decisions.count_documents({})
    assert post_count == 0, f"device_decisions not empty post-clear: {post_count}"

    # 4. device_keys roles untouched
    after_keys = {d["key_id"]: d.get("role") for d in mongo.device_keys.find({}, {"key_id": 1, "role": 1})}
    # Kept creator unchanged
    assert KEPT_CREATOR_KEY_ID in after_keys
    assert after_keys[KEPT_CREATOR_KEY_ID] == "creator"
    # Temp creator unchanged
    assert temp_creator["key_id"] in after_keys
    assert after_keys[temp_creator["key_id"]] == "creator"
    # Same set of keys with same roles
    assert after_keys == before_keys, (
        f"device_keys state changed by /decisions/clear!\n"
        f"  removed: {set(before_keys) - set(after_keys)}\n"
        f"  added:   {set(after_keys) - set(before_keys)}\n"
        f"  role-changed: {[k for k in before_keys if k in after_keys and before_keys[k] != after_keys[k]]}"
    )


def test_decisions_clear_when_empty_returns_zero(mongo, temp_creator):
    """Calling clear on an already-empty table returns {deleted: 0}."""
    # Wipe first (already done by previous test, but be safe)
    mongo.device_decisions.delete_many({})
    payload = creator_signed(temp_creator["priv"], temp_creator["key_id"])
    r = requests.post(f"{API}/devices/decisions/clear", json=payload, timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("deleted") == 0


# ============================================================================
# (3) Regression: session-request-status idempotency + login back-compat
# ============================================================================


def test_session_status_unknown_id_returns_expired_not_404():
    r = requests.post(f"{API}/auth/session-request-status",
                      json={"request_id": "nonexistent_iter47_" + secrets.token_hex(4)},
                      timeout=15)
    assert r.status_code == 200, r.text
    assert r.json().get("status") == "expired"


def test_login_back_compat_no_device_key_id(mongo):
    """Login still works without device_key_id (regression)."""
    # Ensure no leftover blocker sessions
    user = mongo.users.find_one({"email": USER_EMAIL}, {"user_id": 1})
    if user:
        mongo.user_sessions.delete_many({"user_id": user["user_id"]})
        mongo.session_requests.delete_many({"user_id": user["user_id"], "status": "pending"})

    r = requests.post(f"{API}/auth/login",
                      json={"email": USER_EMAIL, "password": USER_PASS},
                      timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "session_token" in body
    # cleanup
    mongo.user_sessions.delete_one({"session_token": body["session_token"]})


# ----- Final safety: kept creator never touched ------------------------------


def test_kept_creator_key_intact(mongo):
    creator = mongo.device_keys.find_one({"key_id": KEPT_CREATOR_KEY_ID})
    assert creator is not None, "Kept creator key was deleted by a test!"
    assert creator.get("role") == "creator"
