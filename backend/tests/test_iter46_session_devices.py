"""Iter46 — backend tests for:
- /api/auth/login back-compat (no device_key_id) and with device_key_id
- /api/auth/login with different device_key_id -> 202 pending approval
- /api/auth/session-request-status idempotency (same token on repeat polls,
  unknown id returns {status:'expired'} NOT 404)
- /api/devices/send-to-creator (valid / invalid sig / unknown key)
- /api/devices/revoke and /api/devices/disconnect hard-delete from device_keys

Read-only/destructive guard: the kept-creator key
'dev_a797438afc28c67923881d46ae2971c1' is NEVER touched.
"""
from __future__ import annotations

import base64
import json
import os
import secrets
import time
from typing import Tuple

import pytest
import requests
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives import hashes, serialization
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://no-code-builder-25.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

# Local backend env is loaded only for direct DB verification (kubernetes-internal
# mongo at localhost:27017 — same DB the backend writes to).
MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "test_database"

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


def register_device(label: str = "TEST_iter46") -> Tuple[ec.EllipticCurvePrivateKey, str, dict]:
    priv, jwk = gen_keypair()
    r = requests.post(f"{API}/devices/register", json={"public_key_jwk": jwk, "label": label}, timeout=15)
    r.raise_for_status()
    return priv, r.json()["key_id"], jwk


def get_nonce(key_id: str) -> str:
    r = requests.post(f"{API}/devices/challenge", json={"key_id": key_id}, timeout=15)
    r.raise_for_status()
    return r.json()["nonce"]


# ----- fixtures ---------------------------------------------------------------


@pytest.fixture(scope="module")
def mongo():
    cli = MongoClient(MONGO_URL, serverSelectionTimeoutMS=3000)
    db = cli[DB_NAME]
    yield db
    cli.close()


@pytest.fixture(scope="module")
def cleanup(mongo):
    """Track and clean up all device keys we create — never touch kept creator."""
    created_keys: list[str] = []
    created_requests: list[str] = []
    yield {"keys": created_keys, "requests": created_requests}
    if created_keys:
        # Safety: never delete the kept creator
        safe_keys = [k for k in created_keys if k != KEPT_CREATOR_KEY_ID]
        mongo.device_keys.delete_many({"key_id": {"$in": safe_keys}})
        mongo.device_nonces.delete_many({"key_id": {"$in": safe_keys}})
        mongo.user_sessions.delete_many({"device_key_id": {"$in": safe_keys}})
    if created_requests:
        mongo.session_requests.delete_many({"request_id": {"$in": created_requests}})
    # Clean any leftover user_sessions from this user that we created in tests
    mongo.user_sessions.delete_many({"device_label": {"$regex": "^TEST_iter46"}})


# ----- 1) back-compat: login without device_key_id ---------------------------


def test_login_back_compat_no_device_key(mongo, cleanup):
    r = requests.post(f"{API}/auth/login",
                      json={"email": USER_EMAIL, "password": USER_PASS},
                      timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "session_token" in body
    # No device_key_id should be persisted on this session
    sess = mongo.user_sessions.find_one({"session_token": body["session_token"]})
    assert sess is not None
    assert sess.get("device_key_id") in (None, "")
    # Cleanup this session
    mongo.user_sessions.delete_one({"session_token": body["session_token"]})


# ----- 2) login with device_key_id ------------------------------------------


def test_login_with_device_key_persists_id(mongo, cleanup):
    priv, key_id, _ = register_device("TEST_iter46_login")
    cleanup["keys"].append(key_id)

    # Clear any other active sessions so this is the only device
    mongo.user_sessions.delete_many({"device_label": {"$regex": "^TEST_iter46"}})

    r = requests.post(f"{API}/auth/login",
                      json={
                          "email": USER_EMAIL,
                          "password": USER_PASS,
                          "device_key_id": key_id,
                          "device_label": "TEST_iter46_DeviceA",
                      }, timeout=15)
    assert r.status_code == 200, r.text
    token = r.json()["session_token"]
    sess = mongo.user_sessions.find_one({"session_token": token})
    assert sess is not None
    assert sess.get("device_key_id") == key_id
    assert sess.get("device_label") == "TEST_iter46_DeviceA"
    return token, key_id


# ----- 3) login from different device_key_id → 202 pending --------------------


@pytest.fixture(scope="module")
def two_device_pending(mongo, cleanup):
    """Sets up the scenario: deviceA logged-in successfully, deviceB attempts
    login and is parked in pending. Yields (deviceA_session_token, deviceA_keyid,
    deviceB_privkey, deviceB_keyid, request_id)."""
    # Clean any leftover sessions to avoid surprise 202 from earlier runs
    user = mongo.users.find_one({"email": USER_EMAIL}, {"user_id": 1})
    assert user, "Test user must exist"
    mongo.user_sessions.delete_many({"user_id": user["user_id"]})
    mongo.session_requests.delete_many({"user_id": user["user_id"], "status": "pending"})

    # Register Device A and log it in
    privA, key_a, _ = register_device("TEST_iter46_A")
    cleanup["keys"].append(key_a)
    rA = requests.post(f"{API}/auth/login", json={
        "email": USER_EMAIL, "password": USER_PASS,
        "device_key_id": key_a, "device_label": "TEST_iter46_A",
    }, timeout=15)
    assert rA.status_code == 200, rA.text
    token_a = rA.json()["session_token"]

    # Register Device B and try to log in
    privB, key_b, _ = register_device("TEST_iter46_B")
    cleanup["keys"].append(key_b)
    rB = requests.post(f"{API}/auth/login", json={
        "email": USER_EMAIL, "password": USER_PASS,
        "device_key_id": key_b, "device_label": "TEST_iter46_B",
    }, timeout=15)
    assert rB.status_code == 202, rB.text
    detail = rB.json()["detail"]
    assert detail["code"] == "session_pending_approval"
    request_id = detail["request_id"]
    cleanup["requests"].append(request_id)
    yield {
        "token_a": token_a, "key_a": key_a,
        "priv_b": privB, "key_b": key_b,
        "request_id": request_id,
    }


def test_pending_login_returns_202_with_request_id(two_device_pending):
    assert two_device_pending["request_id"]
    assert two_device_pending["request_id"].strip() != ""


# ----- 4) session-request-status: unknown id → expired (NOT 404) -------------


def test_status_unknown_id_returns_expired_not_404():
    r = requests.post(f"{API}/auth/session-request-status",
                      json={"request_id": "nonexistent_request_xyz_" + secrets.token_hex(4)},
                      timeout=15)
    assert r.status_code == 200, f"expected 200 got {r.status_code}: {r.text}"
    body = r.json()
    assert body.get("status") == "expired"


# ----- 5) idempotent approved poll -------------------------------------------


def test_status_pending_then_approve_then_idempotent(two_device_pending):
    rid = two_device_pending["request_id"]
    token_a = two_device_pending["token_a"]

    # First poll: still pending
    r1 = requests.post(f"{API}/auth/session-request-status",
                       json={"request_id": rid}, timeout=15)
    assert r1.status_code == 200
    assert r1.json()["status"] == "pending"

    # Device A approves
    r_dec = requests.post(f"{API}/auth/session-decide",
                          json={"request_id": rid, "decision": "approve"},
                          headers={"Authorization": f"Bearer {token_a}"},
                          timeout=15)
    assert r_dec.status_code == 200, r_dec.text
    assert r_dec.json()["status"] == "approved"

    # First post-approval poll: returns approved + session_token
    r2 = requests.post(f"{API}/auth/session-request-status",
                       json={"request_id": rid}, timeout=15)
    assert r2.status_code == 200, r2.text
    body2 = r2.json()
    assert body2["status"] == "approved"
    assert "session_token" in body2
    first_token = body2["session_token"]

    # Second post-approval poll: must return SAME token (idempotent)
    r3 = requests.post(f"{API}/auth/session-request-status",
                       json={"request_id": rid}, timeout=15)
    assert r3.status_code == 200, r3.text
    body3 = r3.json()
    assert body3["status"] == "approved"
    assert body3.get("session_token") == first_token, (
        f"Idempotency violated: got {body3.get('session_token')} vs {first_token}"
    )

    # Third poll for good measure — still same
    r4 = requests.post(f"{API}/auth/session-request-status",
                       json={"request_id": rid}, timeout=15)
    assert r4.status_code == 200
    assert r4.json().get("session_token") == first_token


# ----- 6) /devices/send-to-creator -------------------------------------------


def test_send_to_creator_unknown_key_returns_404():
    fake_key = "dev_" + secrets.token_hex(16)
    r = requests.post(f"{API}/devices/send-to-creator",
                      json={"key_id": fake_key, "nonce": "abc", "signature": "abc"},
                      timeout=15)
    assert r.status_code == 404, r.text


def test_send_to_creator_invalid_signature_returns_403(cleanup):
    priv, key_id, _ = register_device("TEST_iter46_badsig")
    cleanup["keys"].append(key_id)
    nonce = get_nonce(key_id)
    # Use a sig from a DIFFERENT key — will fail verification
    other_priv, _ = gen_keypair()
    bad_sig = sign_nonce(other_priv, nonce)
    r = requests.post(f"{API}/devices/send-to-creator",
                      json={"key_id": key_id, "nonce": nonce, "signature": bad_sig},
                      timeout=15)
    assert r.status_code == 403, r.text


def test_send_to_creator_valid_signature_logs_request(mongo, cleanup):
    priv, key_id, _ = register_device("TEST_iter46_send")
    cleanup["keys"].append(key_id)
    # Force a 'revoked' role to test the pending-restoration branch
    mongo.device_keys.update_one({"key_id": key_id}, {"$set": {"role": "revoked"}})

    nonce = get_nonce(key_id)
    sig = sign_nonce(priv, nonce)
    r = requests.post(f"{API}/devices/send-to-creator",
                      json={"key_id": key_id, "nonce": nonce, "signature": sig},
                      timeout=15)
    assert r.status_code == 200, r.text
    assert r.json().get("sent") is True

    # Role should now be 'pending' (was 'revoked' before)
    dev = mongo.device_keys.find_one({"key_id": key_id})
    assert dev is not None
    assert dev.get("role") == "pending"

    # A 'request_access' decision should have been logged
    decision = mongo.device_decisions.find_one(
        {"action": "request_access", "target_key_id": key_id}
    )
    assert decision is not None, "request_access decision not logged"


# ----- 7) revoke / disconnect HARD-DELETE from device_keys -------------------
# We can't sign as the real creator (private key unknown), so we promote a
# throwaway test key to 'creator' role temporarily via direct DB write. We
# never touch the kept creator key.


@pytest.fixture(scope="module")
def temp_creator(mongo, cleanup):
    priv, key_id, jwk = register_device("TEST_iter46_tmpcreator")
    cleanup["keys"].append(key_id)
    mongo.device_keys.update_one({"key_id": key_id}, {"$set": {"role": "creator"}})
    yield {"priv": priv, "key_id": key_id}
    # Demote back so we don't leave a stray creator
    mongo.device_keys.delete_one({"key_id": key_id})


def _creator_signed_payload(priv, key_id: str, extra: dict) -> dict:
    nonce = get_nonce(key_id)
    sig = sign_nonce(priv, nonce)
    return {"key_id": key_id, "nonce": nonce, "signature": sig, **extra}


def test_devices_revoke_hard_deletes_row(mongo, temp_creator, cleanup):
    # Register a victim device
    _, victim_key, _ = register_device("TEST_iter46_revoke_target")
    cleanup["keys"].append(victim_key)
    assert mongo.device_keys.find_one({"key_id": victim_key}) is not None

    payload = _creator_signed_payload(temp_creator["priv"], temp_creator["key_id"],
                                      {"target_key_id": victim_key})
    # Sanity: not revoking kept creator nor self
    assert payload["key_id"] != KEPT_CREATOR_KEY_ID
    assert victim_key != KEPT_CREATOR_KEY_ID

    r = requests.post(f"{API}/devices/revoke", json=payload, timeout=15)
    assert r.status_code == 200, r.text

    # Hard delete
    assert mongo.device_keys.find_one({"key_id": victim_key}) is None
    # Audit trail in device_decisions remains
    audit = mongo.device_decisions.find_one({"action": "revoke", "target_key_id": victim_key})
    assert audit is not None


def test_devices_disconnect_hard_deletes_row(mongo, temp_creator, cleanup):
    _, victim_key, _ = register_device("TEST_iter46_disconnect_target")
    cleanup["keys"].append(victim_key)
    assert mongo.device_keys.find_one({"key_id": victim_key}) is not None

    payload = _creator_signed_payload(temp_creator["priv"], temp_creator["key_id"],
                                      {"target_key_id": victim_key})
    assert victim_key != KEPT_CREATOR_KEY_ID

    r = requests.post(f"{API}/devices/disconnect", json=payload, timeout=15)
    assert r.status_code == 200, r.text

    assert mongo.device_keys.find_one({"key_id": victim_key}) is None
    audit = mongo.device_decisions.find_one({"action": "disconnect", "target_key_id": victim_key})
    assert audit is not None


# ----- 8) Final safety check: kept creator key is still intact ---------------


def test_kept_creator_key_intact(mongo):
    creator = mongo.device_keys.find_one({"key_id": KEPT_CREATOR_KEY_ID})
    assert creator is not None, "Kept creator key was deleted by a test!"
    assert creator.get("role") == "creator"
