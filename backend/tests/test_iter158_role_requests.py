"""iter158.1 — Tests campagne : demandes entre comptes RÉELLES (rôles/appareil/privé)."""
from __future__ import annotations

import base64
import os
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
    r = requests.post(f"{API}/devices/register", json={"public_key_jwk": jwk, "label": f"REQ_{uuid.uuid4().hex[:6]}"}, timeout=15)
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
    priv_o, kid_o = register()
    mongo.ownership.update_one({"_id": "root"}, {"$addToSet": {"owner_key_ids": kid_o}})
    mongo.device_keys.update_one({"key_id": kid_o}, {"$set": {"role": "creator"}})
    a["owner"] = (priv_o, kid_o)
    priv_c, kid_c = register()
    mongo.device_keys.update_one({"key_id": kid_c}, {"$set": {"role": "creator"}})  # créa déléguée (non owner)
    a["creator"] = (priv_c, kid_c)
    priv_ad, kid_ad = register()
    mongo.device_keys.update_one({"key_id": kid_ad}, {"$set": {"role": "approved", "staff_kind": "admin"}})
    a["admin"] = (priv_ad, kid_ad)
    for name in ("req_modo", "req_admin", "req_creator", "req_device"):
        priv, kid = register()
        mongo.device_keys.update_one({"key_id": kid}, {"$set": {"role": "pending"}})
        a[name] = (priv, kid)
    yield a
    ids = [kid for _, kid in a.values()]
    mongo.ownership.update_one({"_id": "root"}, {"$pull": {"owner_key_ids": {"$in": ids}}})
    mongo.device_keys.delete_many({"key_id": {"$in": ids}})
    mongo.device_nonces.delete_many({"key_id": {"$in": ids}})
    mongo.role_requests.delete_many({"from_key_id": {"$in": ids}})


def _create(actor, kind):
    priv, kid = actor
    return requests.post(f"{API}/requests/create", json=signed(priv, kid, kind=kind), timeout=15)


def _decide(actor, req_id, decision):
    priv, kid = actor
    return requests.post(f"{API}/requests/decide", json=signed(priv, kid, request_id=req_id, decision=decision), timeout=15)


# ---------------- Création + statut + notification ----------------

def test_create_and_mine(actors):
    r = _create(actors["req_device"], "device_validation")
    assert r.status_code == 200, r.text
    rid = r.json()["request_id"]
    priv, kid = actors["req_device"]
    mine = requests.post(f"{API}/requests/mine", json=signed(priv, kid), timeout=15).json()
    assert any(x["request_id"] == rid and x["status"] == "pending" for x in mine["requests"])


def test_duplicate_prevented(actors):
    _create(actors["req_device"], "device_validation")
    r2 = _create(actors["req_device"], "device_validation")
    assert r2.json().get("duplicate") is True


# ---------------- Application réelle du changement ----------------

def test_admin_approves_modo_applies(actors, mongo):
    r = _create(actors["req_modo"], "role_modo")
    rid = r.json()["request_id"]
    d = _decide(actors["admin"], rid, "approve")
    assert d.status_code == 200 and d.json()["applied"] == "modo", d.text
    doc = mongo.device_keys.find_one({"key_id": actors["req_modo"][1]})
    assert doc["staff_kind"] == "modo" and doc["role"] == "approved"


def test_admin_cannot_approve_admin_role(actors):
    r = _create(actors["req_admin"], "role_admin")
    rid = r.json()["request_id"]
    d = _decide(actors["admin"], rid, "approve")
    assert d.status_code == 403  # seule une Créa accorde Admin


def test_creator_approves_admin(actors, mongo):
    # nettoyer une éventuelle demande refusée précédente
    r = _create(actors["req_admin"], "role_admin")
    rid = r.json().get("request_id")
    d = _decide(actors["creator"], rid, "approve")
    assert d.status_code == 200 and d.json()["applied"] == "admin", d.text


# ---------------- role_creator : PROPRIÉTAIRE uniquement + jamais la propriété ----------------

def test_creator_role_needs_owner_not_delegate(actors, mongo):
    r = _create(actors["req_creator"], "role_creator")
    rid = r.json()["request_id"]
    # une créa déléguée (non owner) ne peut PAS approuver role_creator
    d = _decide(actors["creator"], rid, "approve")
    assert d.status_code == 403
    # le propriétaire réel peut, mais cela n'accorde QUE le rôle visible
    d2 = _decide(actors["owner"], rid, "approve")
    assert d2.status_code == 200 and d2.json()["applied"] == "creator_visible", d2.text
    doc = mongo.device_keys.find_one({"key_id": actors["req_creator"][1]})
    assert doc["role"] == "creator"
    own = mongo.ownership.find_one({"_id": "root"})
    assert actors["req_creator"][1] not in own["owner_key_ids"]  # JAMAIS la propriété réelle


# ---------------- Sécurité : signature requise + pas de fuite ----------------

def test_requires_signature(actors):
    r = requests.post(f"{API}/requests/create", json={"kind": "role_modo"}, timeout=15)
    assert r.status_code in (403, 422)


def test_pending_no_private_leak(actors):
    _create(actors["req_modo"], "role_modo")
    priv, kid = actors["admin"]
    p = requests.post(f"{API}/requests/pending", json=signed(priv, kid), timeout=15).json()
    for r in p["requests"]:
        assert "email" not in r and "public_key_jwk" not in r and "password_hash" not in r
