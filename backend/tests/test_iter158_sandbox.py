"""iter158 — Tests campagne : Sandbox multi-rôles (gated owner + TEST_MODE)."""
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
    r = requests.post(f"{API}/devices/register", json={"public_key_jwk": jwk, "label": f"SBX_{uuid.uuid4().hex[:6]}"}, timeout=15)
    r.raise_for_status()
    return priv, r.json()["key_id"]


def body(priv, kid, **extra):
    r = requests.post(f"{API}/devices/challenge", json={"key_id": kid}, timeout=15)
    n = r.json()["nonce"]
    return {"key_id": kid, "nonce": n, "signature": sign(priv, n), **extra}


@pytest.fixture(scope="module")
def mongo():
    cli = MongoClient(MONGO_URL, serverSelectionTimeoutMS=3000)
    yield cli[DB_NAME]
    cli.close()


@pytest.fixture(scope="module")
def owner(mongo):
    priv, kid = register()
    mongo.ownership.update_one({"_id": "root"}, {"$addToSet": {"owner_key_ids": kid}})
    mongo.device_keys.update_one({"key_id": kid}, {"$set": {"role": "creator"}})
    yield (priv, kid)
    mongo.ownership.update_one({"_id": "root"}, {"$pull": {"owner_key_ids": kid}})
    mongo.device_keys.delete_many({"key_id": kid})
    mongo.device_nonces.delete_many({"key_id": kid})
    # teardown sandbox data
    for c in ("device_keys", "users", "private_messages", "mention_notifications",
              "account_requests", "projects", "export_requests"):
        mongo[c].delete_many({"sandbox": True})


def test_non_owner_cannot_seed(owner):
    priv, kid = register()  # simple device
    r = requests.post(f"{API}/sandbox/seed", json=body(priv, kid), timeout=20)
    assert r.status_code == 403


def test_seed_creates_9_profiles(owner, mongo):
    priv, kid = owner
    r = requests.post(f"{API}/sandbox/seed", json=body(priv, kid), timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data["created"]) == 10  # 9 rôles + owner sandbox = 10 profils
    # incarnations contiennent des clés privées
    assert all("private_jwk" in i for i in data["incarnations"])
    # les comptes sont bien flaggés sandbox
    assert mongo.device_keys.count_documents({"sandbox": True}) == 10


def test_incarnation_can_sign_real_requests(owner, mongo):
    """Une identité sandbox incarnée peut signer de vraies requêtes."""
    priv, kid = owner
    r = requests.post(f"{API}/sandbox/seed", json=body(priv, kid), timeout=30)
    inc = {i["slug"]: i for i in r.json()["incarnations"]}
    admin = inc["admin"]
    # reconstruire une clé privée depuis le JWK
    d = int.from_bytes(_b64d(admin["private_jwk"]["d"]), "big")
    priv_admin = ec.derive_private_key(d, ec.SECP256R1())
    # signer un challenge et appeler /ownership/status → doit répondre is_owner False
    rr = requests.post(f"{API}/ownership/status", json=body(priv_admin, admin["key_id"]), timeout=15)
    assert rr.status_code == 200
    assert rr.json()["is_owner"] is False


def test_seed_creates_isolated_interactions(owner, mongo):
    priv, kid = owner
    requests.post(f"{API}/sandbox/seed", json=body(priv, kid), timeout=30)
    assert mongo.private_messages.count_documents({"sandbox": True}) >= 2
    assert mongo.mention_notifications.count_documents({"sandbox": True}) >= 1
    assert mongo.account_requests.count_documents({"sandbox": True}) >= 3


def test_teardown_removes_all(owner, mongo):
    priv, kid = owner
    requests.post(f"{API}/sandbox/seed", json=body(priv, kid), timeout=30)
    r = requests.post(f"{API}/sandbox/teardown", json=body(priv, kid), timeout=20)
    assert r.status_code == 200, r.text
    assert mongo.device_keys.count_documents({"sandbox": True}) == 0
