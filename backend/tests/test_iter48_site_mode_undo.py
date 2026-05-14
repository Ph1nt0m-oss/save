"""Iter48 — backend tests:

(1) /auth/login site_mode gating:
    - public  → 2nd device on same email logs in 200 (NO 202)
    - guest   → same as public (200)
    - private → 2nd device must return 202 session_pending_approval
    - creator → 2nd device must return 202 (regression)

(2) /devices/revoke now SNAPSHOTs the device row on the decision so undo
    can recreate the device (public_key_jwk + label present).

(3) NEW /devices/decisions/undo:
    - revoke entry → recreates device_keys row (role=pending) using snapshot
    - approve entry → flips role back to pending
    - unknown decision → 404
    - missing/invalid signature → 403
    - logs a fresh 'undo' decision row

Always restore site_mode to 'public' on teardown.
Kept creator key dev_a797438afc28c67923881d46ae2971c1 must never be touched.
"""
from __future__ import annotations

import base64
import os
import secrets
import time
from typing import Tuple

import pytest
import requests
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives import hashes
from pymongo import MongoClient


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
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
    jwk = {"kty": "EC", "crv": "P-256",
           "x": _b64url_int(pub.x), "y": _b64url_int(pub.y)}
    return priv, jwk


def sign_nonce(priv: ec.EllipticCurvePrivateKey, nonce_b64url: str) -> str:
    nonce_bytes = _b64url_decode(nonce_b64url)
    der = priv.sign(nonce_bytes, ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    raw = r.to_bytes(32, "big") + s.to_bytes(32, "big")
    return _b64url(raw)


def register_device(label: str = "TEST_iter48") -> Tuple[ec.EllipticCurvePrivateKey, str, dict]:
    priv, jwk = gen_keypair()
    r = requests.post(f"{API}/devices/register",
                      json={"public_key_jwk": jwk, "label": label}, timeout=15)
    r.raise_for_status()
    return priv, r.json()["key_id"], jwk


def get_nonce(key_id: str) -> str:
    r = requests.post(f"{API}/devices/challenge",
                      json={"key_id": key_id}, timeout=15)
    r.raise_for_status()
    return r.json()["nonce"]


def creator_signed(priv: ec.EllipticCurvePrivateKey, key_id: str,
                   extra: dict | None = None) -> dict:
    nonce = get_nonce(key_id)
    sig = sign_nonce(priv, nonce)
    payload = {"key_id": key_id, "nonce": nonce, "signature": sig}
    if extra:
        payload.update(extra)
    return payload


def set_site_mode(mongo, mode: str):
    mongo.site_config.update_one({"_id": "site_mode"},
                                 {"$set": {"mode": mode}}, upsert=True)


def clear_user_sessions(mongo):
    user = mongo.users.find_one({"email": USER_EMAIL}, {"user_id": 1})
    if user:
        mongo.user_sessions.delete_many({"user_id": user["user_id"]})
        mongo.session_requests.delete_many({"user_id": user["user_id"]})


# ----- fixtures ---------------------------------------------------------------


@pytest.fixture(scope="module")
def mongo():
    cli = MongoClient(MONGO_URL, serverSelectionTimeoutMS=3000)
    db = cli[DB_NAME]
    yield db
    # ALWAYS restore site_mode to public at the very end.
    set_site_mode(db, "public")
    cli.close()


@pytest.fixture(scope="module")
def cleanup(mongo):
    created_keys: list[str] = []
    yield {"keys": created_keys}
    safe = [k for k in created_keys if k != KEPT_CREATOR_KEY_ID]
    if safe:
        mongo.device_keys.delete_many({"key_id": {"$in": safe}})
        mongo.device_nonces.delete_many({"key_id": {"$in": safe}})
        mongo.user_sessions.delete_many({"device_key_id": {"$in": safe}})
    mongo.device_keys.delete_many({"label": {"$regex": "^TEST_iter48"}})
    # Restore site_mode to public.
    set_site_mode(mongo, "public")


@pytest.fixture(scope="module")
def temp_creator(mongo, cleanup):
    priv, key_id, _ = register_device("TEST_iter48_tmpcreator")
    cleanup["keys"].append(key_id)
    mongo.device_keys.update_one({"key_id": key_id},
                                 {"$set": {"role": "creator"}})
    yield {"priv": priv, "key_id": key_id}


# ============================================================================
# (1) site_mode gating on /auth/login
# ============================================================================


def _login(email: str, password: str, device_key_id: str | None = None):
    body = {"email": email, "password": password}
    if device_key_id:
        body["device_key_id"] = device_key_id
    return requests.post(f"{API}/auth/login", json=body, timeout=15)


def test_public_mode_second_device_logs_in_200(mongo, cleanup):
    """In public mode the second device on the SAME email logs in immediately."""
    set_site_mode(mongo, "public")
    clear_user_sessions(mongo)

    _, key_a, _ = register_device("TEST_iter48_pub_devA")
    _, key_b, _ = register_device("TEST_iter48_pub_devB")
    cleanup["keys"].extend([key_a, key_b])

    # 1st device — logs in normally.
    r1 = _login(USER_EMAIL, USER_PASS, key_a)
    assert r1.status_code == 200, r1.text
    assert "session_token" in r1.json(), r1.text

    # 2nd device on SAME email — must ALSO be 200 in public mode.
    r2 = _login(USER_EMAIL, USER_PASS, key_b)
    assert r2.status_code == 200, f"Expected 200 in public mode, got {r2.status_code}: {r2.text}"
    body2 = r2.json()
    assert "session_token" in body2, body2

    # Both sessions co-exist.
    user = mongo.users.find_one({"email": USER_EMAIL}, {"user_id": 1})
    sessions = list(mongo.user_sessions.find({"user_id": user["user_id"]}))
    device_ids = {s.get("device_key_id") for s in sessions}
    assert key_a in device_ids and key_b in device_ids, device_ids


def test_guest_mode_second_device_logs_in_200(mongo, cleanup):
    """In guest mode the second device also gets 200 (no approval gate)."""
    set_site_mode(mongo, "guest")
    clear_user_sessions(mongo)

    _, key_a, _ = register_device("TEST_iter48_guest_devA")
    _, key_b, _ = register_device("TEST_iter48_guest_devB")
    cleanup["keys"].extend([key_a, key_b])

    r1 = _login(USER_EMAIL, USER_PASS, key_a)
    assert r1.status_code == 200, r1.text
    r2 = _login(USER_EMAIL, USER_PASS, key_b)
    assert r2.status_code == 200, f"guest mode should not gate; got {r2.status_code}: {r2.text}"
    assert "session_token" in r2.json()

    # cleanup mode
    set_site_mode(mongo, "public")


def test_private_mode_second_device_returns_202(mongo, cleanup):
    """In private mode the regression behaviour stays: 202 session_pending_approval."""
    set_site_mode(mongo, "private")
    clear_user_sessions(mongo)

    _, key_a, _ = register_device("TEST_iter48_priv_devA")
    _, key_b, _ = register_device("TEST_iter48_priv_devB")
    cleanup["keys"].extend([key_a, key_b])

    r1 = _login(USER_EMAIL, USER_PASS, key_a)
    assert r1.status_code == 200, r1.text

    r2 = _login(USER_EMAIL, USER_PASS, key_b)
    assert r2.status_code == 202, f"private mode should gate; got {r2.status_code}: {r2.text}"
    body2 = r2.json()
    # FastAPI HTTPException wraps in {"detail": {...}}
    payload = body2.get("detail", body2)
    code = payload.get("code") if isinstance(payload, dict) else None
    assert code == "session_pending_approval", body2

    set_site_mode(mongo, "public")


def test_creator_mode_second_device_returns_202(mongo, cleanup):
    """In creator mode the approval gate also applies."""
    set_site_mode(mongo, "creator")
    clear_user_sessions(mongo)

    _, key_a, _ = register_device("TEST_iter48_cre_devA")
    _, key_b, _ = register_device("TEST_iter48_cre_devB")
    cleanup["keys"].extend([key_a, key_b])

    r1 = _login(USER_EMAIL, USER_PASS, key_a)
    assert r1.status_code == 200, r1.text

    r2 = _login(USER_EMAIL, USER_PASS, key_b)
    assert r2.status_code == 202, f"creator mode should gate; got {r2.status_code}: {r2.text}"

    set_site_mode(mongo, "public")


# ============================================================================
# (2) /devices/revoke snapshot
# ============================================================================


def test_revoke_writes_snapshot_on_decision_row(mongo, temp_creator, cleanup):
    """After revoke, device_decisions row contains snapshot.public_key_jwk + label."""
    priv, victim_key, jwk = register_device("TEST_iter48_snap_target")
    cleanup["keys"].append(victim_key)

    payload = creator_signed(temp_creator["priv"], temp_creator["key_id"],
                             {"target_key_id": victim_key})
    r = requests.post(f"{API}/devices/revoke", json=payload, timeout=15)
    assert r.status_code == 200, r.text
    assert r.json().get("existed") is True

    audit = mongo.device_decisions.find_one(
        {"action": "revoke", "target_key_id": victim_key})
    assert audit is not None
    snap = audit.get("snapshot")
    assert snap is not None, f"expected snapshot on revoke decision, got: {audit}"
    assert snap.get("public_key_jwk") == jwk, snap
    assert snap.get("label") == "TEST_iter48_snap_target"
    # _id must NOT be in snapshot (mongo internal stripped)
    assert "_id" not in snap


# ============================================================================
# (3) /devices/decisions/undo
# ============================================================================


def test_undo_revoke_recreates_device_as_pending(mongo, temp_creator, cleanup):
    """undo of a revoke decision recreates the device_keys row with role=pending,
    using the snapshot's public_key_jwk."""
    priv, victim_key, jwk = register_device("TEST_iter48_undo_revoke_target")
    cleanup["keys"].append(victim_key)

    # Revoke
    p = creator_signed(temp_creator["priv"], temp_creator["key_id"],
                       {"target_key_id": victim_key})
    r = requests.post(f"{API}/devices/revoke", json=p, timeout=15)
    assert r.status_code == 200, r.text
    assert mongo.device_keys.find_one({"key_id": victim_key}) is None

    # Fetch the decision row to get the ts
    dec = mongo.device_decisions.find_one(
        {"action": "revoke", "target_key_id": victim_key})
    assert dec is not None
    decision_ts = dec["ts"]

    # Undo
    p2 = creator_signed(temp_creator["priv"], temp_creator["key_id"],
                        {"target_key_id": victim_key, "decision_ts": decision_ts})
    r2 = requests.post(f"{API}/devices/decisions/undo", json=p2, timeout=15)
    assert r2.status_code == 200, r2.text
    assert r2.json().get("success") is True

    # device_keys row is back, role=pending, jwk matches snapshot
    recreated = mongo.device_keys.find_one({"key_id": victim_key})
    assert recreated is not None, "device row should be recreated after undo"
    assert recreated.get("role") == "pending", recreated
    assert recreated.get("public_key_jwk") == jwk
    assert recreated.get("label") == "TEST_iter48_undo_revoke_target"


def test_undo_approve_flips_role_back_to_pending(mongo, temp_creator, cleanup):
    """undo of an 'approve' decision sets the device's role back to pending."""
    priv, victim_key, _ = register_device("TEST_iter48_undo_approve_target")
    cleanup["keys"].append(victim_key)

    # Approve
    p = creator_signed(temp_creator["priv"], temp_creator["key_id"],
                       {"target_key_id": victim_key})
    r = requests.post(f"{API}/devices/approve", json=p, timeout=15)
    assert r.status_code == 200, r.text
    assert mongo.device_keys.find_one({"key_id": victim_key}).get("role") == "approved"

    dec = mongo.device_decisions.find_one(
        {"action": "approve", "target_key_id": victim_key})
    assert dec is not None
    decision_ts = dec["ts"]

    # Undo
    p2 = creator_signed(temp_creator["priv"], temp_creator["key_id"],
                        {"target_key_id": victim_key, "decision_ts": decision_ts})
    r2 = requests.post(f"{API}/devices/decisions/undo", json=p2, timeout=15)
    assert r2.status_code == 200, r2.text

    # role flipped back
    assert mongo.device_keys.find_one({"key_id": victim_key}).get("role") == "pending"


def test_undo_unknown_decision_returns_404(temp_creator):
    """No matching (target_key_id, decision_ts) → 404."""
    p = creator_signed(temp_creator["priv"], temp_creator["key_id"],
                       {"target_key_id": "dev_" + secrets.token_hex(16),
                        "decision_ts": "2099-01-01T00:00:00+00:00"})
    r = requests.post(f"{API}/devices/decisions/undo", json=p, timeout=15)
    assert r.status_code == 404, r.text


def test_undo_without_creator_sig_returns_403(cleanup):
    """A non-creator key signing the request → 403."""
    priv, key_id, _ = register_device("TEST_iter48_undo_nopriv")
    cleanup["keys"].append(key_id)
    p = creator_signed(priv, key_id,
                       {"target_key_id": "dev_" + secrets.token_hex(16),
                        "decision_ts": "2099-01-01T00:00:00+00:00"})
    r = requests.post(f"{API}/devices/decisions/undo", json=p, timeout=15)
    assert r.status_code == 403, r.text


def test_undo_logs_fresh_undo_decision(mongo, temp_creator, cleanup):
    """After undo runs successfully, a new 'undo' row is logged in device_decisions."""
    priv, victim_key, _ = register_device("TEST_iter48_undo_log_target")
    cleanup["keys"].append(victim_key)

    # Approve, undo it.
    p = creator_signed(temp_creator["priv"], temp_creator["key_id"],
                       {"target_key_id": victim_key})
    r = requests.post(f"{API}/devices/approve", json=p, timeout=15)
    assert r.status_code == 200, r.text
    dec = mongo.device_decisions.find_one(
        {"action": "approve", "target_key_id": victim_key})
    pre = mongo.device_decisions.count_documents(
        {"action": "undo", "target_key_id": victim_key})

    p2 = creator_signed(temp_creator["priv"], temp_creator["key_id"],
                        {"target_key_id": victim_key, "decision_ts": dec["ts"]})
    r2 = requests.post(f"{API}/devices/decisions/undo", json=p2, timeout=15)
    assert r2.status_code == 200, r2.text

    post = mongo.device_decisions.count_documents(
        {"action": "undo", "target_key_id": victim_key})
    assert post == pre + 1, f"expected exactly 1 new undo decision, pre={pre} post={post}"


# ----- Final safety ----------------------------------------------------------


def test_kept_creator_key_intact(mongo):
    creator = mongo.device_keys.find_one({"key_id": KEPT_CREATOR_KEY_ID})
    assert creator is not None
    assert creator.get("role") == "creator"


def test_site_mode_restored_to_public_at_end(mongo):
    """Final test: ensure site_mode is public (restored)."""
    set_site_mode(mongo, "public")
    doc = mongo.site_config.find_one({"_id": "site_mode"})
    assert doc.get("mode") == "public"
