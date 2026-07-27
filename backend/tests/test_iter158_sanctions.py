"""iter158 — Tests campagne : sanctions temporaires (durée, expiration auto, levée)."""
from __future__ import annotations

import base64
import os
import uuid
from datetime import datetime, timedelta, timezone

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
    r = requests.post(f"{API}/devices/register", json={"public_key_jwk": jwk, "label": f"SANC_{uuid.uuid4().hex[:6]}"}, timeout=15)
    r.raise_for_status()
    return priv, r.json()["key_id"]


def verify(priv, kid):
    r = requests.post(f"{API}/devices/challenge", json={"key_id": kid}, timeout=15)
    n = r.json()["nonce"]
    return requests.post(f"{API}/devices/verify", json={"key_id": kid, "nonce": n, "signature": sign(priv, n)}, timeout=15).json()


@pytest.fixture(scope="module")
def mongo():
    cli = MongoClient(MONGO_URL, serverSelectionTimeoutMS=3000)
    yield cli[DB_NAME]
    cli.close()


def test_active_exclude_blocks_access(mongo):
    priv, kid = register()
    mongo.device_keys.update_one({"key_id": kid}, {"$set": {
        "role": "approved",
        "exclude_until": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
    }})
    v = verify(priv, kid)
    assert v["can_access"] is False and v["kick_reason"] == "kick_excluded"
    mongo.device_keys.delete_many({"key_id": kid})


def test_expired_exclude_auto_lifted(mongo):
    priv, kid = register()
    mongo.device_keys.update_one({"key_id": kid}, {"$set": {
        "role": "approved",
        "exclude_until": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
    }})
    v = verify(priv, kid)
    assert v["can_access"] is True  # expiré → auto-levée → retour normal
    # le champ a été effacé en DB
    doc = mongo.device_keys.find_one({"key_id": kid})
    assert not doc.get("exclude_until")
    mongo.device_keys.delete_many({"key_id": kid})


def test_force_visitor_until_reported(mongo):
    priv, kid = register()
    mongo.device_keys.update_one({"key_id": kid}, {"$set": {
        "role": "approved",
        "force_visitor_until": (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(),
    }})
    v = verify(priv, kid)
    assert v["force_visitor"] is True
    mongo.device_keys.delete_many({"key_id": kid})


def test_muted_reported(mongo):
    priv, kid = register()
    mongo.device_keys.update_one({"key_id": kid}, {"$set": {"role": "approved", "muted": True}})
    v = verify(priv, kid)
    assert v["muted"] is True
    mongo.device_keys.delete_many({"key_id": kid})


def test_disconnect_until_blocks(mongo):
    priv, kid = register()
    mongo.device_keys.update_one({"key_id": kid}, {"$set": {
        "role": "approved",
        "disconnect_until": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat(),
    }})
    v = verify(priv, kid)
    assert v["can_access"] is False and v["kick_reason"] == "kick_disconnected"
    mongo.device_keys.delete_many({"key_id": kid})
