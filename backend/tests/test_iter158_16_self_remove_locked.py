"""iter158.16 — P1.5 : protection self-remove d'un créateur verrouillé.

Sécurise `/accounts/remove-creator` pour qu'un délégué créateur marqué
`locked=true` dans `ownership.delegates[]` (véritable créateur, spec CDC
iter158.6) NE PUISSE PAS retirer son statut créateur — ni lui-même
(self-remove) ni via un autre acteur créa.

Scénarios :
  1. self-remove + locked=true → 409 avec message explicite ("verrouillé").
  2. self-remove + locked=false → passe le guard locked (le pré-check password
     retourne alors 403 normal — le comportement nominal côté locked est
     inchangé).
  3. remove-target-locked par un autre créa → 409 (même protection).
  4. Actor non-créa avec signature valide → 403 (matrice inchangée).
  5. owner_key_ids INTACT dans tous les cas (garde-fou global P0/P1 CDC).

Le fix est spécifique à `/accounts/remove-creator` — les autres endpoints
(delegate/revoke, staff/action, etc.) restent inchangés.
"""
from __future__ import annotations

import base64
import os
import uuid
from pathlib import Path
from typing import Tuple

import bcrypt
import pytest
import requests
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


# ---------------- ECDSA helpers (miroir iter158_14) ----------------

def _b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("ascii").rstrip("=")


def _b64url_int(n: int, length: int = 32) -> str:
    return _b64url(n.to_bytes(length, "big"))


def _b64url_decode(s: str) -> bytes:
    pad = "=" * ((4 - len(s) % 4) % 4)
    return base64.urlsafe_b64decode(s + pad)


def gen_keypair():
    priv = ec.generate_private_key(ec.SECP256R1())
    pub = priv.public_key().public_numbers()
    return priv, {"kty": "EC", "crv": "P-256",
                  "x": _b64url_int(pub.x), "y": _b64url_int(pub.y)}


def sign(priv, nonce_b64url: str) -> str:
    der = priv.sign(_b64url_decode(nonce_b64url), ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    return _b64url(r.to_bytes(32, "big") + s.to_bytes(32, "big"))


def register() -> Tuple[ec.EllipticCurvePrivateKey, str]:
    priv, jwk = gen_keypair()
    r = requests.post(
        f"{API}/devices/register",
        json={"public_key_jwk": jwk, "label": f"IT158_16_{uuid.uuid4().hex[:6]}"},
        timeout=15,
    )
    r.raise_for_status()
    return priv, r.json()["key_id"]


def nonce(key_id: str) -> str:
    r = requests.post(f"{API}/devices/challenge", json={"key_id": key_id}, timeout=15)
    r.raise_for_status()
    return r.json()["nonce"]


def signed_body(priv, key_id: str, **extra):
    n = nonce(key_id)
    return {"key_id": key_id, "nonce": n, "signature": sign(priv, n), **extra}


# ---------------- Fixtures ----------------

@pytest.fixture(scope="module")
def mongo():
    cli = MongoClient(MONGO_URL, serverSelectionTimeoutMS=3000)
    yield cli[DB_NAME]
    cli.close()


@pytest.fixture()
def env(mongo):
    """Environnement isolé pour un test :
      - owner : appareil propriétaire (owner_key_ids)
      - delegate_locked : délégué créateur avec locked=true (email+pwd valides)
      - delegate_unlocked : délégué créateur avec locked=false (email+pwd valides)
      - plain_creator : créateur non-délégué (email+pwd valides)
    """
    priv_o, kid_o = register()
    priv_l, kid_l = register()
    priv_u, kid_u = register()
    priv_c, kid_c = register()

    pwd = "P1_5-Test!2026"
    pwd_hash = bcrypt.hashpw(pwd.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    mongo.ownership.update_one(
        {"_id": "root"}, {"$addToSet": {"owner_key_ids": kid_o}}
    )
    mongo.device_keys.update_one({"key_id": kid_o}, {"$set": {
        "role": "creator", "pseudo": "OwnerP15",
        "email": f"owner_p15_{uuid.uuid4().hex[:8]}@t.test",
        "public_handle": f"owner_p15_{uuid.uuid4().hex[:6]}",
    }})

    def _setup_delegate_creator(kid, pseudo, locked):
        email = f"deleg_{uuid.uuid4().hex[:8]}@t.test"
        mongo.users.insert_one({
            "user_id": f"u_{uuid.uuid4().hex[:12]}",
            "email": email, "password_hash": pwd_hash,
        })
        mongo.device_keys.update_one({"key_id": kid}, {"$set": {
            "role": "creator", "is_delegate_creator": True,
            "pseudo": pseudo, "email": email,
            "public_handle": f"{pseudo.lower()}_{uuid.uuid4().hex[:6]}",
        }})
        mongo.ownership.update_one(
            {"_id": "root"}, {"$pull": {"delegates": {"key_id": kid}}}
        )
        mongo.ownership.update_one({"_id": "root"}, {"$push": {"delegates": {
            "key_id": kid, "perms": ["moderate"], "temp_perms": [],
            "locked": locked, "history": [],
            "added_by": kid_o, "added_at": "2026-02-16T00:00:00+00:00",
        }}})
        return email

    email_l = _setup_delegate_creator(kid_l, "LockedC", True)
    email_u = _setup_delegate_creator(kid_u, "UnlockedC", False)

    # Plain creator (non-delegate): role='creator' avec email+pwd valides,
    # PAS d'entrée dans ownership.delegates → get_delegate() → None.
    email_c = f"plain_{uuid.uuid4().hex[:8]}@t.test"
    mongo.users.insert_one({
        "user_id": f"u_{uuid.uuid4().hex[:12]}",
        "email": email_c, "password_hash": pwd_hash,
    })
    mongo.device_keys.update_one({"key_id": kid_c}, {"$set": {
        "role": "creator", "pseudo": "PlainC", "email": email_c,
        "public_handle": f"plainc_{uuid.uuid4().hex[:6]}",
    }})

    yield {
        "owner":              (priv_o, kid_o),
        "delegate_locked":    (priv_l, kid_l, email_l),
        "delegate_unlocked":  (priv_u, kid_u, email_u),
        "plain_creator":      (priv_c, kid_c, email_c),
        "password":           pwd,
    }

    # Cleanup complet.
    ids = [kid_o, kid_l, kid_u, kid_c]
    mongo.ownership.update_one({"_id": "root"}, {"$pull": {"owner_key_ids": {"$in": ids}}})
    mongo.ownership.update_one({"_id": "root"}, {"$pull": {"delegates": {"key_id": {"$in": ids}}}})
    mongo.device_keys.delete_many({"key_id": {"$in": ids}})
    mongo.device_nonces.delete_many({"key_id": {"$in": ids}})
    mongo.users.delete_many({"email": {"$in": [email_l, email_u, email_c]}})
    mongo.account_history.delete_many({"target_key_id": {"$in": ids}})
    mongo.account_history.delete_many({"actor_key_id": {"$in": ids}})
    mongo.device_decisions.delete_many({"actor_key_id": {"$in": ids}})


def _snapshot_owner_key_ids(mongo) -> list:
    return list(mongo.ownership.find_one({"_id": "root"}, {"_id": 0, "owner_key_ids": 1})
                .get("owner_key_ids") or [])


# ============================================================================
# Scénario 1 — Self-remove d'un créateur locked → 409 explicite
# ============================================================================

def test_self_remove_locked_creator_refused_409(env, mongo):
    priv_l, kid_l, _ = env["delegate_locked"]
    pwd = env["password"]

    before = _snapshot_owner_key_ids(mongo)

    r = requests.post(
        f"{API}/accounts/remove-creator",
        json=signed_body(priv_l, kid_l, password=pwd, target_key_id=kid_l),
        timeout=15,
    )
    assert r.status_code == 409, (
        f"self-remove sur locked doit renvoyer 409 — {r.status_code}: {r.text}"
    )
    detail = r.json().get("detail", "")
    assert "verrouillé" in detail.lower() or "locked" in detail.lower(), (
        f"Message d'erreur doit mentionner le verrouillage — got: {detail!r}"
    )
    # Fondation CDC : role='creator' toujours en place (aucune démotion).
    dev = mongo.device_keys.find_one({"key_id": kid_l})
    assert dev.get("role") == "creator"
    # owner_key_ids intact (le délégué n'y figure jamais mais on garde le check).
    assert _snapshot_owner_key_ids(mongo) == before


# ============================================================================
# Scénario 2 — Un autre créateur tente de retirer un locked → 409
# ============================================================================

def test_other_creator_removing_locked_refused_409(env, mongo):
    priv_c, kid_c, _ = env["plain_creator"]
    _, kid_l, _ = env["delegate_locked"]
    pwd = env["password"]

    before = _snapshot_owner_key_ids(mongo)

    r = requests.post(
        f"{API}/accounts/remove-creator",
        json=signed_body(priv_c, kid_c, password=pwd, target_key_id=kid_l),
        timeout=15,
    )
    assert r.status_code == 409, (
        f"Un autre créateur retirant un locked doit être bloqué — {r.status_code}: {r.text}"
    )
    detail = r.json().get("detail", "")
    assert "verrouillé" in detail.lower() or "locked" in detail.lower()
    # Le locked n'a PAS été démotée.
    dev_l = mongo.device_keys.find_one({"key_id": kid_l})
    assert dev_l.get("role") == "creator"
    assert _snapshot_owner_key_ids(mongo) == before


# ============================================================================
# Scénario 3 — Self-remove sur unlocked : le guard locked ne bloque plus
# (comportement nominal préservé — 200 succès quand toutes les conditions
# nominales sont réunies).
# ============================================================================

def test_self_remove_unlocked_delegate_nominal_success(env, mongo):
    priv_u, kid_u, _ = env["delegate_unlocked"]
    pwd = env["password"]

    before = _snapshot_owner_key_ids(mongo)

    r = requests.post(
        f"{API}/accounts/remove-creator",
        json=signed_body(priv_u, kid_u, password=pwd, target_key_id=kid_u),
        timeout=15,
    )
    # Comportement nominal préservé : 200 avec self=True, role démotée.
    assert r.status_code == 200, (
        f"self-remove sur unlocked doit passer nominalement — {r.status_code}: {r.text}"
    )
    body = r.json()
    assert body.get("success") is True
    assert body.get("self") is True

    dev = mongo.device_keys.find_one({"key_id": kid_u})
    assert dev.get("role") == "approved", "démotion effective vers 'approved'"
    assert _snapshot_owner_key_ids(mongo) == before, (
        "owner_key_ids NE DOIT PAS bouger sur remove-creator (jamais un owner)"
    )


# ============================================================================
# Scénario 4 — Plain creator (non-délégué, locked=absent) self-remove : nominal
# ============================================================================

def test_self_remove_plain_creator_nominal_success(env, mongo):
    priv_c, kid_c, _ = env["plain_creator"]
    pwd = env["password"]

    before = _snapshot_owner_key_ids(mongo)

    r = requests.post(
        f"{API}/accounts/remove-creator",
        json=signed_body(priv_c, kid_c, password=pwd, target_key_id=kid_c),
        timeout=15,
    )
    assert r.status_code == 200, r.text
    assert r.json().get("self") is True
    assert mongo.device_keys.find_one({"key_id": kid_c}).get("role") == "approved"
    assert _snapshot_owner_key_ids(mongo) == before


# ============================================================================
# Scénario 5 — Wrong password : le guard nominal l'attrape (403), même sur locked
# (le guard locked ne masque pas les protections existantes en amont).
# ============================================================================

def test_locked_creator_wrong_password_still_403(env, mongo):
    priv_l, kid_l, _ = env["delegate_locked"]

    r = requests.post(
        f"{API}/accounts/remove-creator",
        json=signed_body(priv_l, kid_l, password="wrong-password",
                         target_key_id=kid_l),
        timeout=15,
    )
    # 403 wrong-password OU 409 locked (les deux sont acceptables selon l'ordre) —
    # l'important : PAS 200, et role toujours 'creator'.
    assert r.status_code in (403, 409), r.text
    assert mongo.device_keys.find_one({"key_id": kid_l}).get("role") == "creator"


# ============================================================================
# Scénario 6 — Non-créateur signant : matrice inchangée (403 avant tout)
# ============================================================================

def test_non_creator_actor_still_403(mongo):
    """Un simple approved (non-creator) → 403 au niveau du signature gate.
    Le guard locked n'est jamais atteint. Non-régression iter56."""
    priv, kid = register()
    mongo.device_keys.update_one({"key_id": kid}, {"$set": {"role": "approved"}})
    try:
        r = requests.post(
            f"{API}/accounts/remove-creator",
            json=signed_body(priv, kid, password="whatever", target_key_id=kid),
            timeout=15,
        )
        assert r.status_code == 403, r.text
    finally:
        mongo.device_keys.delete_many({"key_id": kid})
        mongo.device_nonces.delete_many({"key_id": kid})


# ============================================================================
# Scénario 7 — owner_key_ids TOTALEMENT intact sur tout le fixture
# ============================================================================

def test_owner_key_ids_never_touched_by_remove_creator(env, mongo):
    """Invariant fort P0/P1 CDC : `/accounts/remove-creator` ne modifie
    JAMAIS `ownership.owner_key_ids`. On combine ici plusieurs tentatives
    (self-remove locked, remove-locked-by-other) et on vérifie l'invariant."""
    priv_l, kid_l, _ = env["delegate_locked"]
    priv_c, kid_c, _ = env["plain_creator"]
    pwd = env["password"]

    before = _snapshot_owner_key_ids(mongo)

    # Try self-remove locked
    requests.post(f"{API}/accounts/remove-creator",
                  json=signed_body(priv_l, kid_l, password=pwd, target_key_id=kid_l),
                  timeout=15)
    # Try other-remove locked
    requests.post(f"{API}/accounts/remove-creator",
                  json=signed_body(priv_c, kid_c, password=pwd, target_key_id=kid_l),
                  timeout=15)

    after = _snapshot_owner_key_ids(mongo)
    assert after == before, (
        f"owner_key_ids modifié par /accounts/remove-creator (interdit CDC) : "
        f"before={before}, after={after}"
    )


# ============================================================================
# Scénario 8 — Contrôle source-level du guard (défense en profondeur)
# ============================================================================

def test_source_level_guard_present_and_uses_get_delegate():
    """Le fichier `accounts_routes.py` DOIT explicitement vérifier `locked`
    via `get_delegate` avant la démotion. Défense en profondeur : si un
    refactor futur touchait le guard sans faire tourner les tests live,
    ce test source-level garantit la présence du garde-fou."""
    src = Path("/app/backend/routes/accounts_routes.py").read_text(encoding="utf-8")
    # Localiser la fonction accounts_remove_creator
    idx = src.find("async def accounts_remove_creator")
    assert idx > 0
    # Le guard doit intervenir avant l'update_one qui démote le role.
    block = src[idx:idx + 4000]
    assert "get_delegate" in block, (
        "get_delegate doit être utilisé pour lire le flag `locked`"
    )
    assert 'delegate_row.get("locked")' in block or '"locked"' in block
    # Le raise 409 doit précéder la démotion role→approved.
    demote_idx = block.find('"role": "approved"')
    guard_idx = block.find('"locked"')
    assert 0 < guard_idx < demote_idx, (
        "Le guard locked doit intervenir AVANT la démotion (ordre critique)"
    )
