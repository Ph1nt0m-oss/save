"""iter158 — Tests SUPPLEMENT (campagne finale) : couvertures manquantes.

Complète la campagne principale (test_iter158_*.py) sur :
  1. Escalade impossible : un admin (rôle) ne peut PAS devenir propriétaire
     via /ownership/challenge ni via /staff/action action='promote_creator'.
  2. Export refonte (iter158) : /projects/{id}/duplicate → 403,
     /projects/{id}/share {enable:true} → 403, {enable:false} → OK.
  3. Export gating : /exports/zip-project/{id} et /export/download sans
     demande d'export APPROUVÉE → 403.
  4. Invariants signature : /api/ownership/* et /api/sandbox/* sans
     signature/nonce → 403/422.
  5. Sanction : /staff/action exclude puis /devices/verify → can_access=False
     (kick_reason=kick_excluded) ; expiration passée → auto-levée.
"""
from __future__ import annotations

import base64
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Tuple

import pytest
import requests
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from pymongo import MongoClient

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL", "https://no-code-builder-25.preview.emergentagent.com"
).rstrip("/")
API = f"{BASE_URL}/api"
MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "test_database"


# ------------------------ helpers ECDSA ------------------------

def _b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _b64ui(n: int) -> str:
    return _b64u(n.to_bytes(32, "big"))


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * ((4 - len(s) % 4) % 4))


def gen_keypair():
    priv = ec.generate_private_key(ec.SECP256R1())
    p = priv.public_key().public_numbers()
    return priv, {"kty": "EC", "crv": "P-256", "x": _b64ui(p.x), "y": _b64ui(p.y)}


def sign(priv, nonce_b64: str) -> str:
    der = priv.sign(_b64d(nonce_b64), ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    return _b64u(r.to_bytes(32, "big") + s.to_bytes(32, "big"))


def register() -> Tuple[ec.EllipticCurvePrivateKey, str]:
    priv, jwk = gen_keypair()
    r = requests.post(
        f"{API}/devices/register",
        json={"public_key_jwk": jwk, "label": f"SUP_{uuid.uuid4().hex[:6]}"},
        timeout=15,
    )
    r.raise_for_status()
    return priv, r.json()["key_id"]


def signed(priv, kid: str, **extra) -> dict:
    n = requests.post(f"{API}/devices/challenge", json={"key_id": kid}, timeout=15).json()["nonce"]
    return {"key_id": kid, "nonce": n, "signature": sign(priv, n), **extra}


# ------------------------ fixtures ------------------------

@pytest.fixture(scope="module")
def mongo():
    cli = MongoClient(MONGO_URL, serverSelectionTimeoutMS=3000)
    yield cli[DB_NAME]
    cli.close()


@pytest.fixture(scope="module")
def owner_pair(mongo):
    """Paire de propriétaires réels (double sig OK ailleurs si besoin)."""
    priv_a, kid_a = register()
    priv_b, kid_b = register()
    mongo.ownership.update_one(
        {"_id": "root"}, {"$addToSet": {"owner_key_ids": {"$each": [kid_a, kid_b]}}}
    )
    mongo.device_keys.update_one({"key_id": kid_a}, {"$set": {"role": "creator"}})
    mongo.device_keys.update_one({"key_id": kid_b}, {"$set": {"role": "creator"}})
    yield {"a": (priv_a, kid_a), "b": (priv_b, kid_b)}
    mongo.ownership.update_one({"_id": "root"}, {"$pull": {"owner_key_ids": {"$in": [kid_a, kid_b]}}})
    mongo.device_keys.delete_many({"key_id": {"$in": [kid_a, kid_b]}})
    mongo.device_nonces.delete_many({"key_id": {"$in": [kid_a, kid_b]}})


@pytest.fixture()
def admin_device(mongo):
    priv, kid = register()
    mongo.device_keys.update_one(
        {"key_id": kid}, {"$set": {"role": "approved", "staff_kind": "admin"}}
    )
    yield priv, kid
    mongo.device_keys.delete_many({"key_id": kid})
    mongo.device_nonces.delete_many({"key_id": kid})


@pytest.fixture()
def modo_device(mongo):
    priv, kid = register()
    mongo.device_keys.update_one(
        {"key_id": kid}, {"$set": {"role": "approved", "staff_kind": "modo"}}
    )
    yield priv, kid
    mongo.device_keys.delete_many({"key_id": kid})
    mongo.device_nonces.delete_many({"key_id": kid})


@pytest.fixture()
def plain_device(mongo):
    priv, kid = register()
    mongo.device_keys.update_one({"key_id": kid}, {"$set": {"role": "approved"}})
    yield priv, kid
    mongo.device_keys.delete_many({"key_id": kid})
    mongo.device_nonces.delete_many({"key_id": kid})


@pytest.fixture()
def test_session(mongo):
    """Crée une session utilisateur factice pour hitter les endpoints /projects/*."""
    user_id = f"TEST_user_{uuid.uuid4().hex[:8]}"
    token = f"TEST_sess_{secrets.token_urlsafe(24)}"
    mongo.user_sessions.insert_one({
        "user_id": user_id,
        "session_token": token,
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    yield user_id, token
    mongo.user_sessions.delete_many({"session_token": token})
    mongo.projects.delete_many({"user_id": user_id})
    mongo.export_requests.delete_many({"user_id": user_id})


# =====================================================================
# 1. ESCALADE IMPOSSIBLE — un admin ne peut PAS devenir propriétaire
# =====================================================================

def test_admin_cannot_get_ownership_challenge(admin_device):
    """Un admin (rôle staff) qui appelle /ownership/challenge → 403."""
    priv, kid = admin_device
    body = signed(priv, kid, action="transfer_ownership")
    r = requests.post(f"{API}/ownership/challenge", json=body, timeout=15)
    assert r.status_code == 403, f"admin ne doit pas obtenir de challenge propriétaire: {r.status_code} {r.text}"


def test_admin_cannot_add_owner_device_directly(admin_device):
    """Même en appelant /ownership/add-owner-device un admin doit être rejeté."""
    priv, kid = admin_device
    _, target = register()
    r = requests.post(
        f"{API}/ownership/add-owner-device",
        json={"challenge_id": "fake", "proofs": [], "new_owner_key_id": target},
        timeout=15,
    )
    assert r.status_code in (400, 403, 422)


def test_promote_creator_never_grants_real_ownership(owner_pair, admin_device, mongo):
    """iter158 : /staff/action action='promote_creator' NE fait JAMAIS passer un
    device dans owner_key_ids (la propriété réelle reste immuable)."""
    priv_a, kid_a = owner_pair["a"]
    priv_adm, kid_adm = admin_device
    _, target = register()
    mongo.device_keys.update_one({"key_id": target}, {"$set": {"role": "approved"}})
    before = set(mongo.ownership.find_one({"_id": "root"}).get("owner_key_ids", []))
    # Un owner tente promote_creator sur target (censé n'affecter QUE rôle, pas propriété)
    r = requests.post(
        f"{API}/staff/action",
        json=signed(priv_a, kid_a, target_key_id=target, action="promote_creator"),
        timeout=15,
    )
    # peu importe le code (200 ou 403 selon matrice), l'invariant est sur la DB
    after = set(mongo.ownership.find_one({"_id": "root"}).get("owner_key_ids", []))
    assert target not in after, "promote_creator ne doit JAMAIS ajouter à owner_key_ids"
    assert before == after or after - before == set(), "aucune écriture inattendue sur owner_key_ids"
    mongo.device_keys.delete_many({"key_id": target})
    _ = r  # unused


# =====================================================================
# 2. EXPORT REFONTE — duplicate/share désactivés
# =====================================================================

def test_duplicate_project_returns_403(test_session):
    _, token = test_session
    pid = f"TEST_proj_{uuid.uuid4().hex[:6]}"
    r = requests.post(
        f"{API}/projects/{pid}/duplicate",
        headers={"Authorization": f"Bearer {token}"},
        json={},
        timeout=15,
    )
    assert r.status_code == 403, f"duplicate doit être 403: {r.status_code} {r.text}"


def test_share_enable_true_returns_403(test_session, mongo):
    user_id, token = test_session
    pid = f"TEST_proj_{uuid.uuid4().hex[:6]}"
    mongo.projects.insert_one({"project_id": pid, "user_id": user_id, "name": "T", "is_public": False})
    r = requests.post(
        f"{API}/projects/{pid}/share",
        headers={"Authorization": f"Bearer {token}"},
        json={"enable": True},
        timeout=15,
    )
    assert r.status_code == 403


def test_share_enable_false_allowed(test_session, mongo):
    user_id, token = test_session
    pid = f"TEST_proj_{uuid.uuid4().hex[:6]}"
    mongo.projects.insert_one(
        {"project_id": pid, "user_id": user_id, "name": "T", "is_public": True, "share_slug": "abc"}
    )
    r = requests.post(
        f"{API}/projects/{pid}/share",
        headers={"Authorization": f"Bearer {token}"},
        json={"enable": False},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["is_public"] is False
    doc = mongo.projects.find_one({"project_id": pid})
    assert doc["is_public"] is False


# =====================================================================
# 3. EXPORT GATING — zip-project & /export/download exigent approbation
# =====================================================================

def test_zip_project_without_approved_request_returns_403(test_session, mongo):
    user_id, token = test_session
    pid = f"TEST_proj_{uuid.uuid4().hex[:6]}"
    mongo.projects.insert_one({"project_id": pid, "user_id": user_id, "name": "T"})
    r = requests.get(
        f"{API}/exports/zip-project/{pid}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    assert r.status_code == 403, f"attendu 403 sans export approuvé: {r.status_code} {r.text}"


def test_zip_project_with_approved_request_ok(test_session, mongo):
    user_id, token = test_session
    pid = f"TEST_proj_{uuid.uuid4().hex[:6]}"
    mongo.projects.insert_one({"project_id": pid, "user_id": user_id, "name": "T"})
    mongo.export_requests.insert_one({
        "request_id": f"req_{uuid.uuid4().hex[:8]}",
        "project_id": pid,
        "user_id": user_id,
        "status": "approved",
    })
    r = requests.get(
        f"{API}/exports/zip-project/{pid}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=20,
    )
    assert r.status_code == 200, f"attendu 200 avec export approuvé: {r.status_code}"
    assert r.headers.get("content-type", "").startswith("application/zip")


def test_export_download_without_approval_returns_403(test_session, mongo):
    user_id, token = test_session
    pid = f"TEST_proj_{uuid.uuid4().hex[:6]}"
    mongo.projects.insert_one({"project_id": pid, "user_id": user_id, "name": "T"})
    r = requests.post(
        f"{API}/export/download",
        headers={"Authorization": f"Bearer {token}"},
        json={"project_id": pid, "export_type": "web"},
        timeout=15,
    )
    assert r.status_code == 403, f"attendu 403: {r.status_code} {r.text}"


# =====================================================================
# 4. INVARIANTS SIGNATURE — /ownership/* et /sandbox/* exigent une sig
# =====================================================================

@pytest.mark.parametrize("path", [
    "/ownership/status",
    "/ownership/challenge",
    "/ownership/init",
    "/sandbox/seed",
    "/sandbox/teardown",
])
def test_endpoints_reject_missing_signature(path):
    """Appel sans body signé → 401/403/422 (JAMAIS 200)."""
    r = requests.post(f"{API}{path}", json={}, timeout=15)
    assert r.status_code in (401, 403, 422), f"{path}: attendu 401/403/422, got {r.status_code}"


def test_ownership_status_rejects_bad_signature(plain_device):
    """Nonce valide mais signature bidon → 401/403."""
    priv, kid = plain_device
    n = requests.post(f"{API}/devices/challenge", json={"key_id": kid}, timeout=15).json()["nonce"]
    bad_sig = _b64u(b"\x00" * 64)
    r = requests.post(
        f"{API}/ownership/status",
        json={"key_id": kid, "nonce": n, "signature": bad_sig},
        timeout=15,
    )
    assert r.status_code in (401, 403), f"signature bidon: {r.status_code}"


def test_ownership_status_rejects_replay(plain_device):
    """Le même nonce ne peut PAS être réutilisé."""
    priv, kid = plain_device
    body = signed(priv, kid)
    r1 = requests.post(f"{API}/ownership/status", json=body, timeout=15)
    r2 = requests.post(f"{API}/ownership/status", json=body, timeout=15)
    assert r1.status_code == 200
    assert r2.status_code in (401, 403), f"replay attendu 401/403: {r2.status_code}"


# =====================================================================
# 5. SANCTIONS via /staff/action → /devices/verify
# =====================================================================

def test_exclude_via_staff_then_verify_blocks(admin_device, plain_device, mongo):
    """Admin pose exclude sur un device → /devices/verify renvoie kick_excluded."""
    priv_adm, kid_adm = admin_device
    priv_v, kid_v = plain_device
    r = requests.post(
        f"{API}/staff/action",
        json=signed(priv_adm, kid_adm, target_key_id=kid_v, action="exclude"),
        timeout=15,
    )
    assert r.status_code == 200, r.text
    # verify côté victime
    n = requests.post(f"{API}/devices/challenge", json={"key_id": kid_v}, timeout=15).json()["nonce"]
    v = requests.post(
        f"{API}/devices/verify",
        json={"key_id": kid_v, "nonce": n, "signature": sign(priv_v, n)},
        timeout=15,
    ).json()
    assert v["can_access"] is False
    assert v.get("kick_reason") == "kick_excluded"


def test_expired_exclude_auto_lifted_end_to_end(plain_device, mongo):
    """exclude_until passé → auto-levée à la vérification suivante."""
    priv, kid = plain_device
    mongo.device_keys.update_one({"key_id": kid}, {"$set": {
        "exclude_until": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
    }})
    n = requests.post(f"{API}/devices/challenge", json={"key_id": kid}, timeout=15).json()["nonce"]
    v = requests.post(
        f"{API}/devices/verify",
        json={"key_id": kid, "nonce": n, "signature": sign(priv, n)},
        timeout=15,
    ).json()
    assert v["can_access"] is True
    doc = mongo.device_keys.find_one({"key_id": kid})
    assert not doc.get("exclude_until")
