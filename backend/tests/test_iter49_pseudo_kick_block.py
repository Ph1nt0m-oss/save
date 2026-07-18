"""Iter49 — backend tests:

(1) /auth/login one-device-at-a-time approval RESTORED for ALL site_modes
    (including public/guest). 2nd device on same email → 202.
(2) PUT /system/site-mode now accepts optional `guest_view`, and on switch
    to 'creator' deletes ALL non-creator user_sessions, on switch to
    'private' deletes non-(creator|approved) user_sessions.
(3) /devices/verify returns `kick_reason`.
(4) NEW role 'blocked' + /devices/block + /devices/unblock.
(5) /devices/send-to-creator returns specific French 403 when blocked.
(6) _log_decision filter: only approve/revoke/promote persisted.
(7) RegisterRequest now requires `pseudo` (3-30 chars, unique, 'Créatrice'
    reserved).
(8) Block creates a 'blocked' shell row if device didn't exist.
(9) GET /system/site-mode returns {mode, guest_view}.

Always restore site_mode='public' guest_view=null at teardown.
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


def register_device(label: str = "TEST_iter49") -> Tuple[ec.EllipticCurvePrivateKey, str, dict]:
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


def set_site_mode_db(mongo, mode: str, guest_view=None):
    mongo.site_config.update_one(
        {"_id": "site_mode"},
        {"$set": {"mode": mode, "guest_view": guest_view}},
        upsert=True,
    )


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
    # ALWAYS restore site_mode to public + guest_view null at end.
    set_site_mode_db(db, "public", None)
    cli.close()


@pytest.fixture(scope="module")
def cleanup(mongo):
    created_keys: list[str] = []
    created_user_ids: list[str] = []
    yield {"keys": created_keys, "user_ids": created_user_ids}
    safe = [k for k in created_keys if k != KEPT_CREATOR_KEY_ID]
    if safe:
        mongo.device_keys.delete_many({"key_id": {"$in": safe}})
        mongo.device_nonces.delete_many({"key_id": {"$in": safe}})
        mongo.user_sessions.delete_many({"device_key_id": {"$in": safe}})
    mongo.device_keys.delete_many({"label": {"$regex": "^TEST_iter49"}})
    if created_user_ids:
        mongo.users.delete_many({"user_id": {"$in": created_user_ids}})
        mongo.email_verifications.delete_many({"user_id": {"$in": created_user_ids}})
    # Also nuke users by email pattern used in tests (TEST_iter49_*)
    mongo.users.delete_many({"email": {"$regex": "^test_iter49_"}})
    set_site_mode_db(mongo, "public", None)


@pytest.fixture(scope="module")
def temp_creator(mongo, cleanup):
    priv, key_id, _ = register_device("TEST_iter49_tmpcreator")
    cleanup["keys"].append(key_id)
    mongo.device_keys.update_one({"key_id": key_id},
                                 {"$set": {"role": "creator"}})
    yield {"priv": priv, "key_id": key_id}


# ============================================================================
# (A) GET /system/site-mode shape
# ============================================================================


def test_site_mode_get_returns_mode_and_guest_view(mongo):
    set_site_mode_db(mongo, "public", None)
    r = requests.get(f"{API}/system/site-mode", timeout=15)
    assert r.status_code == 200, r.text
    j = r.json()
    assert "mode" in j and "guest_view" in j, j
    assert j["mode"] == "public"
    assert j["guest_view"] is None


# ============================================================================
# (B) /auth/register pseudo validation
# ============================================================================


def test_register_without_pseudo_returns_400():
    email = f"test_iter49_nopseudo_{secrets.token_hex(4)}@gmail.com"
    r = requests.post(f"{API}/auth/register",
                      json={"email": email, "password": "Pass1234"},
                      timeout=15)
    assert r.status_code == 400, r.text
    assert "pseudo" in r.text.lower()


def test_register_pseudo_too_short_returns_400():
    email = f"test_iter49_short_{secrets.token_hex(4)}@gmail.com"
    r = requests.post(f"{API}/auth/register",
                      json={"email": email, "password": "Pass1234", "pseudo": "Cr"},
                      timeout=15)
    assert r.status_code == 400, r.text


def test_register_reserved_pseudo_returns_409():
    """iter75/iter141 — Le pseudo 'Créatrice' n'est plus réservé et le
    pseudo n'est plus unique. Ce test est conservé pour documenter la
    régression comportementale : il ne doit PAS renvoyer 409."""
    import pytest as _pt
    _pt.skip("iter75+ : pseudo n'est plus réservé/unique (public_handle est le seul identifiant unique).")


def test_register_pseudo_uniqueness(mongo, cleanup):
    """iter141 — Le pseudo n'est PLUS unique ; seule l'identité publique
    (public_handle) l'est. On teste l'index MongoDB via insertion directe
    (bypass la validation full-register qui exige aussi device_capture +
    biométrie)."""
    from pymongo.errors import DuplicateKeyError
    import uuid as _u
    shared_handle = f"h_iter141_{secrets.token_hex(3)}"
    email1 = f"test_iter141_uniq_a_{secrets.token_hex(4)}@gmail.com"
    email2 = f"test_iter141_uniq_b_{secrets.token_hex(4)}@gmail.com"
    uid1 = f"user_{_u.uuid4().hex[:12]}"
    uid2 = f"user_{_u.uuid4().hex[:12]}"
    same_pseudo = f"pseudo_dup_{secrets.token_hex(3)}"

    # 1er user avec un handle unique.
    mongo.users.insert_one({
        "user_id": uid1, "email": email1, "password_hash": "x",
        "pseudo": same_pseudo, "pseudo_lower": same_pseudo.lower(),
        "public_handle": shared_handle,
        "public_handle_lower": shared_handle.lower(),
        "verified": True,
    })
    cleanup["user_ids"].append(uid1)

    # 2e user avec le MÊME pseudo — doit réussir (pseudo n'est plus unique).
    mongo.users.insert_one({
        "user_id": uid2, "email": email2, "password_hash": "x",
        "pseudo": same_pseudo, "pseudo_lower": same_pseudo.lower(),
        "public_handle": f"other_{secrets.token_hex(4)}",
        "public_handle_lower": f"other_{secrets.token_hex(4)}".lower(),
        "verified": True,
    })
    cleanup["user_ids"].append(uid2)

    # 3e user avec un handle EN CONFLIT (case-insensitive) — doit lever.
    uid3 = f"user_{_u.uuid4().hex[:12]}"
    with pytest.raises(DuplicateKeyError):
        mongo.users.insert_one({
            "user_id": uid3, "email": f"conflict_{secrets.token_hex(4)}@ex.com",
            "password_hash": "x",
            "pseudo": f"any_{secrets.token_hex(3)}",
            "pseudo_lower": "any",
            "public_handle": shared_handle.upper(),  # case-insensitive uniqueness
            "public_handle_lower": shared_handle.lower(),
            "verified": True,
        })


# ============================================================================
# (C) /auth/login one-device-at-a-time REGARDLESS of site_mode
# ============================================================================


def _login(email: str, password: str, device_key_id: str | None = None):
    body = {"email": email, "password": password}
    if device_key_id:
        body["device_key_id"] = device_key_id
    return requests.post(f"{API}/auth/login", json=body, timeout=15)


def test_login_2nd_device_gated_in_public_mode(mongo, cleanup):
    """Iter49: even in 'public' mode the 2nd device on the same email is gated."""
    set_site_mode_db(mongo, "public", None)
    clear_user_sessions(mongo)

    _, key_a, _ = register_device("TEST_iter49_pub_devA")
    _, key_b, _ = register_device("TEST_iter49_pub_devB")
    cleanup["keys"].extend([key_a, key_b])

    r1 = _login(USER_EMAIL, USER_PASS, key_a)
    assert r1.status_code == 200, r1.text

    r2 = _login(USER_EMAIL, USER_PASS, key_b)
    assert r2.status_code == 202, f"Expected 202 in public mode (iter49), got {r2.status_code}: {r2.text}"
    body2 = r2.json()
    detail = body2.get("detail") if isinstance(body2.get("detail"), dict) else body2
    assert detail.get("code") == "session_pending_approval", detail


# ============================================================================
# (D) PUT /system/site-mode kick logic + guest_view
# ============================================================================


def test_set_site_mode_creator_deletes_non_creator_sessions(mongo, cleanup, temp_creator):
    # Seed: register two non-creator devices and create user_sessions for them.
    set_site_mode_db(mongo, "public", None)
    clear_user_sessions(mongo)

    _, key_a, _ = register_device("TEST_iter49_kick_creatorA")
    _, key_b, _ = register_device("TEST_iter49_kick_creatorB")
    cleanup["keys"].extend([key_a, key_b])

    # Make key_a 'approved' to test the deletion still hits approved (creator mode kicks ALL non-creator).
    mongo.device_keys.update_one({"key_id": key_a}, {"$set": {"role": "approved"}})

    # Insert fake user_sessions tied to these devices.
    user = mongo.users.find_one({"email": USER_EMAIL}, {"user_id": 1})
    now_iso_future = "2999-01-01T00:00:00+00:00"
    mongo.user_sessions.insert_many([
        {"session_token": f"tok_{secrets.token_hex(4)}", "user_id": user["user_id"],
         "device_key_id": key_a, "expires_at": now_iso_future},
        {"session_token": f"tok_{secrets.token_hex(4)}", "user_id": user["user_id"],
         "device_key_id": key_b, "expires_at": now_iso_future},
    ])

    # Switch to creator mode (creator-signed via temp_creator).
    body = creator_signed(temp_creator["priv"], temp_creator["key_id"], {"mode": "creator"})
    r = requests.put(f"{API}/system/site-mode", json=body, timeout=15)
    assert r.status_code == 200, r.text
    assert r.json()["mode"] == "creator"

    # Both sessions must have been deleted (a is approved, b is pending — neither is creator).
    remaining_a = mongo.user_sessions.count_documents({"device_key_id": key_a})
    remaining_b = mongo.user_sessions.count_documents({"device_key_id": key_b})
    assert remaining_a == 0, f"approved device session should be deleted in creator mode (got {remaining_a})"
    assert remaining_b == 0, f"pending device session should be deleted in creator mode (got {remaining_b})"

    # Restore
    set_site_mode_db(mongo, "public", None)


def test_set_site_mode_private_keeps_creator_and_approved_sessions(mongo, cleanup, temp_creator):
    set_site_mode_db(mongo, "public", None)
    clear_user_sessions(mongo)

    _, key_app, _ = register_device("TEST_iter49_kick_privApp")
    _, key_pend, _ = register_device("TEST_iter49_kick_privPend")
    cleanup["keys"].extend([key_app, key_pend])
    mongo.device_keys.update_one({"key_id": key_app}, {"$set": {"role": "approved"}})

    user = mongo.users.find_one({"email": USER_EMAIL}, {"user_id": 1})
    now_iso_future = "2999-01-01T00:00:00+00:00"
    mongo.user_sessions.insert_many([
        {"session_token": f"tok_{secrets.token_hex(4)}", "user_id": user["user_id"],
         "device_key_id": key_app, "expires_at": now_iso_future},
        {"session_token": f"tok_{secrets.token_hex(4)}", "user_id": user["user_id"],
         "device_key_id": key_pend, "expires_at": now_iso_future},
    ])

    body = creator_signed(temp_creator["priv"], temp_creator["key_id"], {"mode": "private"})
    r = requests.put(f"{API}/system/site-mode", json=body, timeout=15)
    assert r.status_code == 200, r.text
    assert r.json()["mode"] == "private"

    remaining_app = mongo.user_sessions.count_documents({"device_key_id": key_app})
    remaining_pend = mongo.user_sessions.count_documents({"device_key_id": key_pend})
    assert remaining_app == 1, f"approved session should NOT be deleted in private mode (got {remaining_app})"
    assert remaining_pend == 0, f"pending session should be deleted in private mode (got {remaining_pend})"

    set_site_mode_db(mongo, "public", None)


def test_set_site_mode_guest_with_guest_view_creator(mongo, temp_creator):
    body = creator_signed(temp_creator["priv"], temp_creator["key_id"],
                          {"mode": "guest", "guest_view": "creator"})
    r = requests.put(f"{API}/system/site-mode", json=body, timeout=15)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["mode"] == "guest"
    assert j["guest_view"] == "creator", j

    g = requests.get(f"{API}/system/site-mode", timeout=15)
    assert g.status_code == 200, g.text
    gj = g.json()
    assert gj["mode"] == "guest"
    assert gj["guest_view"] == "creator", gj

    set_site_mode_db(mongo, "public", None)


# ============================================================================
# (E) /devices/verify kick_reason
# ============================================================================


def test_devices_verify_kick_reason_public_mode_null(mongo, cleanup):
    set_site_mode_db(mongo, "public", None)
    priv, key_id, _ = register_device("TEST_iter49_verify_pub")
    cleanup["keys"].append(key_id)

    nonce = get_nonce(key_id)
    sig = sign_nonce(priv, nonce)
    r = requests.post(f"{API}/devices/verify",
                      json={"key_id": key_id, "nonce": nonce, "signature": sig},
                      timeout=15)
    assert r.status_code == 200, r.text
    j = r.json()
    assert "kick_reason" in j, j
    assert j["kick_reason"] is None, j
    assert j["can_access"] is True


def test_devices_verify_kick_reason_creator_mode_non_creator(mongo, cleanup, temp_creator):
    # Switch to creator mode via the real endpoint (creator-signed).
    body = creator_signed(temp_creator["priv"], temp_creator["key_id"], {"mode": "creator"})
    r0 = requests.put(f"{API}/system/site-mode", json=body, timeout=15)
    assert r0.status_code == 200, r0.text

    # Now register a non-creator device and verify it.
    priv, key_id, _ = register_device("TEST_iter49_verify_kickcre")
    cleanup["keys"].append(key_id)

    nonce = get_nonce(key_id)
    sig = sign_nonce(priv, nonce)
    r = requests.post(f"{API}/devices/verify",
                      json={"key_id": key_id, "nonce": nonce, "signature": sig},
                      timeout=15)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["can_access"] is False, j
    assert j["kick_reason"] == "kick_creator_only", j

    set_site_mode_db(mongo, "public", None)


# ============================================================================
# (F) /devices/block + /devices/unblock + send-to-creator blocked message
# ============================================================================


def test_block_and_unblock_flow(mongo, cleanup, temp_creator):
    target_priv, target_key, _ = register_device("TEST_iter49_block_target")
    cleanup["keys"].append(target_key)

    # Block.
    body = creator_signed(temp_creator["priv"], temp_creator["key_id"],
                          {"target_key_id": target_key})
    r = requests.post(f"{API}/devices/block", json=body, timeout=15)
    assert r.status_code == 200, r.text
    assert r.json().get("blocked") is True

    after = mongo.device_keys.find_one({"key_id": target_key}, {"role": 1})
    assert after and after.get("role") == "blocked", after

    # send-to-creator from blocked device → 403 specific message.
    n = get_nonce(target_key) if False else None  # blocked won't allow nonce flow either
    # Try to send-to-creator. The blocked check fires BEFORE nonce consume.
    # We still need to provide *something* in the payload — generate locally.
    n2 = "x" * 22  # dummy base64url, doesn't matter — blocked check fires first
    sig2 = "x" * 22
    r2 = requests.post(f"{API}/devices/send-to-creator",
                       json={"key_id": target_key, "nonce": n2, "signature": sig2},
                       timeout=15)
    assert r2.status_code == 403, r2.text
    msg = r2.json().get("detail", "")
    assert "formulée de nombreuses fois" in msg, msg
    assert "contacter le créateur" in msg or "créateur" in msg, msg

    # Unblock.
    body3 = creator_signed(temp_creator["priv"], temp_creator["key_id"],
                           {"target_key_id": target_key})
    r3 = requests.post(f"{API}/devices/unblock", json=body3, timeout=15)
    assert r3.status_code == 200, r3.text

    after2 = mongo.device_keys.find_one({"key_id": target_key}, {"role": 1, "blocked_at": 1})
    assert after2 and after2.get("role") == "pending", after2
    assert "blocked_at" not in after2 or after2.get("blocked_at") is None


def test_block_creates_shell_for_unknown_device(mongo, cleanup, temp_creator):
    # Use a fake key_id that doesn't exist in device_keys.
    fake_key = f"dev_iter49_fake_{secrets.token_hex(8)}"
    cleanup["keys"].append(fake_key)

    body = creator_signed(temp_creator["priv"], temp_creator["key_id"],
                          {"target_key_id": fake_key})
    r = requests.post(f"{API}/devices/block", json=body, timeout=15)
    assert r.status_code == 200, r.text

    shell = mongo.device_keys.find_one({"key_id": fake_key})
    assert shell is not None, "shell row should be created"
    assert shell.get("role") == "blocked", shell


# ============================================================================
# (G) _log_decision filter — only approve/revoke/promote persisted
# ============================================================================


def test_log_decision_filter(mongo, cleanup, temp_creator):
    # Reset to public so send-to-creator works normally.
    set_site_mode_db(mongo, "public", None)
    priv, key_id, _ = register_device("TEST_iter49_logfilter_target")
    cleanup["keys"].append(key_id)

    # Snapshot current decision counts for this target.
    before_req = mongo.device_decisions.count_documents({"target_key_id": key_id, "action": "request_access"})
    before_app = mongo.device_decisions.count_documents({"target_key_id": key_id, "action": "approve"})

    # 1) send-to-creator → request_access must NOT be logged.
    nonce = get_nonce(key_id)
    sig = sign_nonce(priv, nonce)
    rs = requests.post(f"{API}/devices/send-to-creator",
                       json={"key_id": key_id, "nonce": nonce, "signature": sig},
                       timeout=15)
    assert rs.status_code == 200, rs.text

    after_req = mongo.device_decisions.count_documents({"target_key_id": key_id, "action": "request_access"})
    assert after_req == before_req, f"request_access must NOT be logged (before={before_req}, after={after_req})"

    # 2) approve → 'approve' MUST be logged.
    body = creator_signed(temp_creator["priv"], temp_creator["key_id"],
                          {"target_key_id": key_id})
    ra = requests.post(f"{API}/devices/approve", json=body, timeout=15)
    assert ra.status_code == 200, ra.text

    after_app = mongo.device_decisions.count_documents({"target_key_id": key_id, "action": "approve"})
    assert after_app == before_app + 1, f"approve should be logged once (before={before_app}, after={after_app})"


# ============================================================================
# (H) Final restore test — ensures site_mode is public at end
# ============================================================================


def test_zz_final_site_mode_is_public(mongo):
    set_site_mode_db(mongo, "public", None)
    r = requests.get(f"{API}/system/site-mode", timeout=15)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["mode"] == "public"
    assert j["guest_view"] is None
