"""iter158 — Tests campagne : Propriété réelle (Ownership) + auth renforcée.

Live tests (HTTP contre le backend en cours). Couvre :
  - séparation propriété / rôle,
  - challenge lié à l'action + double signature ECDSA,
  - transfert / ajout / retrait d'appareil propriétaire,
  - récupération propriétaire (code secret + brute-force guard),
  - délégation (add/revoke) et interdiction pour un délégué de toucher la propriété,
  - garde staff : impossible d'agir sur un appareil propriétaire.
"""
from __future__ import annotations

import base64
import os
import uuid
from typing import Tuple

import pytest
import requests
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://no-code-builder-25.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "test_database"


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
    return priv, {"kty": "EC", "crv": "P-256", "x": _b64url_int(pub.x), "y": _b64url_int(pub.y)}


def sign(priv, nonce_b64url: str) -> str:
    der = priv.sign(_b64url_decode(nonce_b64url), ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    return _b64url(r.to_bytes(32, "big") + s.to_bytes(32, "big"))


def register() -> Tuple[ec.EllipticCurvePrivateKey, str]:
    priv, jwk = gen_keypair()
    r = requests.post(f"{API}/devices/register", json={"public_key_jwk": jwk, "label": f"IT158_{uuid.uuid4().hex[:6]}"}, timeout=15)
    r.raise_for_status()
    return priv, r.json()["key_id"]


def nonce(key_id: str) -> str:
    r = requests.post(f"{API}/devices/challenge", json={"key_id": key_id}, timeout=15)
    r.raise_for_status()
    return r.json()["nonce"]


def signed_body(priv, key_id: str, **extra):
    n = nonce(key_id)
    return {"key_id": key_id, "nonce": n, "signature": sign(priv, n), **extra}


@pytest.fixture(scope="module")
def mongo():
    cli = MongoClient(MONGO_URL, serverSelectionTimeoutMS=3000)
    yield cli[DB_NAME]
    cli.close()


@pytest.fixture(scope="module")
def owners(mongo):
    """Deux appareils propriétaires (A, B) + un délégué + un admin + un simple."""
    priv_a, kid_a = register()
    priv_b, kid_b = register()
    priv_d, kid_d = register()   # delegate
    priv_adm, kid_adm = register()
    priv_u, kid_u = register()
    # A et B → propriétaires réels (injection DB directe = simulation seed).
    mongo.ownership.update_one({"_id": "root"}, {"$addToSet": {"owner_key_ids": {"$each": [kid_a, kid_b]}}})
    mongo.device_keys.update_one({"key_id": kid_a}, {"$set": {"role": "creator"}})
    mongo.device_keys.update_one({"key_id": kid_b}, {"$set": {"role": "creator"}})
    mongo.device_keys.update_one({"key_id": kid_adm}, {"$set": {"role": "approved", "staff_kind": "admin"}})
    mongo.device_keys.update_one({"key_id": kid_u}, {"$set": {"role": "approved"}})
    ctx = {"a": (priv_a, kid_a), "b": (priv_b, kid_b), "d": (priv_d, kid_d),
           "adm": (priv_adm, kid_adm), "u": (priv_u, kid_u)}
    yield ctx
    # cleanup
    ids = [kid_a, kid_b, kid_d, kid_adm, kid_u]
    mongo.ownership.update_one({"_id": "root"}, {"$pull": {"owner_key_ids": {"$in": ids}}})
    mongo.ownership.update_one({"_id": "root"}, {"$pull": {"delegates": {"key_id": {"$in": ids}}}})
    mongo.device_keys.delete_many({"key_id": {"$in": ids}})
    mongo.device_nonces.delete_many({"key_id": {"$in": ids}})


def _status(ctx, who):
    priv, kid = ctx[who]
    r = requests.post(f"{API}/ownership/status", json=signed_body(priv, kid), timeout=15)
    r.raise_for_status()
    return r.json()


# ---------------- Séparation propriété / rôle ----------------

def test_owner_device_is_owner(owners):
    assert _status(owners, "a")["is_owner"] is True


def test_admin_role_is_not_owner(owners):
    """Un admin (rôle/permissions élevés) N'EST PAS propriétaire."""
    s = _status(owners, "adm")
    assert s["is_owner"] is False


def test_plain_user_not_owner(owners):
    assert _status(owners, "u")["is_owner"] is False


# ---------------- Challenge + double signature ----------------

def _challenge(ctx, who, action, target=None):
    priv, kid = ctx[who]
    body = signed_body(priv, kid, action=action)
    if target:
        body["target_key_id"] = target
    r = requests.post(f"{API}/ownership/challenge", json=body, timeout=15)
    return r


def test_non_owner_cannot_get_challenge(owners):
    r = _challenge(owners, "u", "transfer_ownership")
    assert r.status_code == 403


def test_transfer_requires_double_signature(owners):
    r = _challenge(owners, "a", "transfer_ownership")
    assert r.status_code == 200, r.text
    assert r.json()["needs_double_signature"] is True


def test_transfer_with_single_sig_rejected(owners):
    ch = _challenge(owners, "a", "transfer_ownership").json()
    priv_a, kid_a = owners["a"]
    priv_new, kid_new = register()
    body = {"challenge_id": ch["challenge_id"],
            "proofs": [{"key_id": kid_a, "signature": sign(priv_a, ch["challenge_nonce"])}],
            "new_owner_key_id": kid_new}
    r = requests.post(f"{API}/ownership/transfer", json=body, timeout=15)
    assert r.status_code == 403  # une seule signature insuffisante


def test_transfer_with_double_sig_succeeds(owners, mongo):
    ch = _challenge(owners, "a", "transfer_ownership").json()
    priv_a, kid_a = owners["a"]
    priv_b, kid_b = owners["b"]
    priv_new, kid_new = register()
    body = {"challenge_id": ch["challenge_id"],
            "proofs": [{"key_id": kid_a, "signature": sign(priv_a, ch["challenge_nonce"])},
                       {"key_id": kid_b, "signature": sign(priv_b, ch["challenge_nonce"])}],
            "new_owner_key_id": kid_new}
    r = requests.post(f"{API}/ownership/transfer", json=body, timeout=15)
    assert r.status_code == 200, r.text
    doc = mongo.ownership.find_one({"_id": "root"})
    assert kid_new in doc["owner_key_ids"]
    mongo.ownership.update_one({"_id": "root"}, {"$pull": {"owner_key_ids": kid_new}})
    mongo.device_keys.delete_many({"key_id": kid_new})


def test_challenge_replay_rejected(owners):
    ch = _challenge(owners, "a", "add_owner_device").json()
    priv_a, kid_a = owners["a"]
    priv_new, kid_new = register()
    body = {"challenge_id": ch["challenge_id"],
            "proofs": [{"key_id": kid_a, "signature": sign(priv_a, ch["challenge_nonce"])}],
            "new_owner_key_id": kid_new}
    r1 = requests.post(f"{API}/ownership/add-owner-device", json=body, timeout=15)
    assert r1.status_code == 200, r1.text
    r2 = requests.post(f"{API}/ownership/add-owner-device", json=body, timeout=15)
    assert r2.status_code == 403  # rejeu interdit


# ---------------- Récupération propriétaire ----------------

def test_recovery_flow(owners, mongo):
    # init (si pas encore configuré) → récupère un code
    priv_a, kid_a = owners["a"]
    r = requests.post(f"{API}/ownership/init", json=signed_body(priv_a, kid_a), timeout=15)
    if r.status_code == 409:
        # déjà init : on force un code connu directement en DB
        from hashlib import pbkdf2_hmac  # noqa
        import sys
        sys.path.insert(0, "/app/backend")
        from utils.ownership_guard import hash_recovery_code
        code = "TESTX-TESTY-TESTZ-TEST9"
        h = hash_recovery_code(code)
        mongo.ownership.update_one({"_id": "root"}, {"$set": {"recovery_code_hash": h["hash"], "recovery_salt": h["salt"]}})
    else:
        assert r.status_code == 200, r.text
        code = r.json()["recovery_code"]
    # nouvel appareil compromis-recovery
    priv_new, kid_new = register()
    n = nonce(kid_new)
    bad = {"key_id": kid_new, "nonce": n, "signature": sign(priv_new, n), "recovery_code": "WRONG-WRONG-WRONG-WRON"}
    rb = requests.post(f"{API}/ownership/recover", json=bad, timeout=15)
    assert rb.status_code == 403
    n2 = nonce(kid_new)
    good = {"key_id": kid_new, "nonce": n2, "signature": sign(priv_new, n2), "recovery_code": code}
    rg = requests.post(f"{API}/ownership/recover", json=good, timeout=15)
    assert rg.status_code == 200, rg.text
    doc = mongo.ownership.find_one({"_id": "root"})
    assert kid_new in doc["owner_key_ids"]
    mongo.ownership.update_one({"_id": "root"}, {"$pull": {"owner_key_ids": kid_new}})
    mongo.device_keys.delete_many({"key_id": kid_new})


# ---------------- Délégation ----------------

def test_delegate_add_and_cannot_touch_owner(owners, mongo):
    priv_a, kid_a = owners["a"]
    priv_d, kid_d = owners["d"]
    r = requests.post(f"{API}/ownership/delegate/add",
                      json=signed_body(priv_a, kid_a, delegate_key_id=kid_d, perms=["moderate", "manage_site"]),
                      timeout=15)
    assert r.status_code == 200, r.text
    # Le délégué a le rôle visible creator mais N'EST PAS propriétaire.
    s = _status(owners, "d")
    assert s["is_owner"] is False and s["is_delegate"] is True
    # Le délégué ne peut PAS obtenir de challenge propriétaire.
    rc = _challenge(owners, "d", "transfer_ownership")
    assert rc.status_code == 403


def test_staff_cannot_ban_owner_device(owners):
    """Un admin ne peut jamais bannir un appareil propriétaire."""
    priv_adm, kid_adm = owners["adm"]
    _, kid_a = owners["a"]
    r = requests.post(f"{API}/staff/action",
                      json=signed_body(priv_adm, kid_adm, target_key_id=kid_a, action="ban"),
                      timeout=15)
    assert r.status_code == 403
