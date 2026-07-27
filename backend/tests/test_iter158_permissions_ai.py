"""iter158 — Tests campagne : permissions staff + garde IA + isolation données.

1. Matrice de permissions (modo vs admin vs user) via /staff/action.
2. Invariant sécurité : AUCUN module IA (agents/, caly, community_bots) ne
   modifie les rôles, permissions ou la propriété.
3. Isolation : un non-propriétaire ne voit jamais la liste des appareils
   propriétaires ni les délégués.
"""
from __future__ import annotations

import base64
import os
import pathlib
import re
import uuid

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
BACKEND_DIR = pathlib.Path("/app/backend")


def _b64u(b): return base64.urlsafe_b64encode(b).decode().rstrip("=")
def _b64ui(n): return _b64u(n.to_bytes(32, "big"))
def _b64d(s): return base64.urlsafe_b64decode(s + "=" * ((4 - len(s) % 4) % 4))


def gen():
    priv = ec.generate_private_key(ec.SECP256R1())
    p = priv.public_key().public_numbers()
    return priv, {"kty": "EC", "crv": "P-256", "x": _b64ui(p.x), "y": _b64ui(p.y)}


def sign(priv, n):
    der = priv.sign(_b64d(n), ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    return _b64u(r.to_bytes(32, "big") + s.to_bytes(32, "big"))


def register():
    priv, jwk = gen()
    r = requests.post(f"{API}/devices/register", json={"public_key_jwk": jwk, "label": f"PERM_{uuid.uuid4().hex[:6]}"}, timeout=15)
    r.raise_for_status()
    return priv, r.json()["key_id"]


def signed(priv, kid, **extra):
    n = requests.post(f"{API}/devices/challenge", json={"key_id": kid}, timeout=15).json()["nonce"]
    return {"key_id": kid, "nonce": n, "signature": sign(priv, n), **extra}


@pytest.fixture(scope="module")
def mongo():
    cli = MongoClient(MONGO_URL, serverSelectionTimeoutMS=3000)
    yield cli[DB_NAME]
    cli.close()


@pytest.fixture(scope="module")
def actors(mongo):
    a = {}
    for name, role, sk in [("modo", "approved", "modo"), ("admin", "approved", "admin"),
                           ("user", "approved", None), ("victim", "approved", None)]:
        priv, kid = register()
        mongo.device_keys.update_one({"key_id": kid}, {"$set": {"role": role, "staff_kind": sk}})
        a[name] = (priv, kid)
    yield a
    ids = [kid for _, kid in a.values()]
    mongo.device_keys.delete_many({"key_id": {"$in": ids}})
    mongo.device_nonces.delete_many({"key_id": {"$in": ids}})


def _action(actor, target_kid, action):
    priv, kid = actor
    return requests.post(f"{API}/staff/action", json=signed(priv, kid, target_key_id=target_kid, action=action), timeout=15)


# ---------------- Matrice de permissions ----------------

def test_modo_can_mute(actors):
    r = _action(actors["modo"], actors["victim"][1], "mute")
    assert r.status_code == 200, r.text


def test_modo_cannot_ban(actors):
    r = _action(actors["modo"], actors["victim"][1], "ban")
    assert r.status_code == 403  # ban réservé admin+


def test_admin_can_ban(actors, mongo):
    r = _action(actors["admin"], actors["victim"][1], "ban")
    assert r.status_code == 200, r.text
    mongo.device_keys.update_one({"key_id": actors["victim"][1]}, {"$set": {"role": "approved", "banned": False}})


def test_user_cannot_use_staff_action(actors):
    r = _action(actors["user"], actors["victim"][1], "mute")
    assert r.status_code == 403  # simple utilisateur = aucun outil staff


def test_modo_can_exclude_and_force_visitor(actors, mongo):
    for act in ("exclude", "force_visitor", "disconnect", "block"):
        r = _action(actors["modo"], actors["victim"][1], act)
        assert r.status_code == 200, f"{act}: {r.text}"
    mongo.device_keys.update_one({"key_id": actors["victim"][1]}, {"$set": {"role": "approved"}})


# ---------------- Invariant IA : jamais de modification d'autorisation ----------------

FORBIDDEN = re.compile(r"device_keys\s*\.\s*(update_one|update_many|delete_one|delete_many|insert_one)"
                       r"|ownership\s*\.\s*(update_one|update_many)"
                       r"|\.(update_one|update_many)\([^)]*(staff_kind|owner_key_ids)")


def test_ai_modules_never_modify_authorization():
    """Aucun module IA n'écrit dans device_keys/ownership ni ne change un rôle."""
    offenders = []
    scan = list((BACKEND_DIR / "agents").glob("*.py"))
    for extra in ("routes/caly_routes.py", "routes/community_bots_routes.py", "utils/ai_profile_injector.py"):
        p = BACKEND_DIR / extra
        if p.exists():
            scan.append(p)
    for f in scan:
        txt = f.read_text(encoding="utf-8", errors="ignore")
        if FORBIDDEN.search(txt):
            offenders.append(f.name)
    assert not offenders, f"Modules IA modifiant l'autorisation : {offenders}"


# ---------------- Isolation des données privées ----------------

def test_non_owner_status_hides_owner_list(mongo):
    priv, kid = register()
    mongo.device_keys.update_one({"key_id": kid}, {"$set": {"role": "approved"}})
    r = requests.post(f"{API}/ownership/status", json=signed(priv, kid), timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert data["is_owner"] is False
    assert "owner_key_ids" not in data   # jamais exposé à un non-propriétaire
    assert "delegates" not in data
    mongo.device_keys.delete_many({"key_id": kid})
