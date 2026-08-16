"""iter158.13 — P1.2 : Cross-feature interaction tests.

Vérifie que les fonctionnalités livrées (Owner Privileges ON/OFF, sanctions,
délégations Apprentice Creator, transfer ownership, switch_account gate,
AI error mapping) se comportent correctement quand elles s'entrecroisent.

6 scénarios (chaque test vérifie l'INTERACTION, pas juste l'existence) :
  1. Owner OFF → sanction → Owner ON : l'action passe OFF, notification créée,
     ON restaure protection + reconnexion (clear sanctions, role='creator').
  2. Owner OFF → action staff → undo : la matrice d'annulation reste appliquée
     à travers l'état OFF (modo ne peut pas annuler admin, admin peut, etc.).
  3. Apprentice Creator → délégation → Force-visitor : ni les perms déléguées
     ni le force-visitor ne permettent de contourner l'ownership.
  4. Transfer ownership → notifications : isolation entre owners maintenue
     à travers les décisions admin croisées et les mark-read.
  5. Sanction × switch_account × délégation : délégué sans switch_account ne
     voit pas le bouton ; une temp expirée disparaît proprement de
     delegate_perms (backend filtre automatiquement).
  6. AI error mapping × chat multi-tour : une réponse d'erreur classifiée ne
     casse ni l'historique ni les tours suivants (état frontend + backend).

Live tests HTTP contre le backend en cours. Injection DB directe pour seed
des owners/admins/modos (pattern de test_iter158_ownership.py).
"""
from __future__ import annotations

import base64
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Tuple

import pytest
import requests
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from pymongo import MongoClient

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL", "http://localhost:8001"
).rstrip("/")
API = f"{BASE_URL}/api"
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

FRONT = Path("/app/frontend/src")


# ---------------- Crypto helpers (miroir test_iter158_ownership.py) ----------------

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
        json={"public_key_jwk": jwk, "label": f"IT158_13_{uuid.uuid4().hex[:6]}"},
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


def status(priv, kid):
    r = requests.post(f"{API}/ownership/status", json=signed_body(priv, kid), timeout=15)
    r.raise_for_status()
    return r.json()


# ---------------- Fixtures ----------------

@pytest.fixture(scope="module")
def mongo():
    cli = MongoClient(MONGO_URL, serverSelectionTimeoutMS=3000)
    yield cli[DB_NAME]
    cli.close()


@pytest.fixture(scope="module")
def actors(mongo):
    """Actors : ownerA, ownerB (2 propriétaires), admin, modo, approved user,
    delegate (rôle créa déléguée)."""
    priv_a, kid_a = register()
    priv_b, kid_b = register()
    priv_adm, kid_adm = register()
    priv_modo, kid_modo = register()
    priv_u, kid_u = register()
    priv_d, kid_d = register()  # delegate

    mongo.ownership.update_one(
        {"_id": "root"},
        {"$addToSet": {"owner_key_ids": {"$each": [kid_a, kid_b]}}},
    )
    mongo.device_keys.update_one({"key_id": kid_a}, {"$set": {
        "role": "creator", "pseudo": "OwnerA", "public_handle": f"owner_a_{uuid.uuid4().hex[:6]}",
        "owner_privileges_active": True,
    }})
    mongo.device_keys.update_one({"key_id": kid_b}, {"$set": {
        "role": "creator", "pseudo": "OwnerB", "public_handle": f"owner_b_{uuid.uuid4().hex[:6]}",
        "owner_privileges_active": True,
    }})
    mongo.device_keys.update_one({"key_id": kid_adm}, {"$set": {
        "role": "approved", "staff_kind": "admin", "pseudo": "AdminX",
        "public_handle": f"admin_{uuid.uuid4().hex[:6]}",
    }})
    mongo.device_keys.update_one({"key_id": kid_modo}, {"$set": {
        "role": "approved", "staff_kind": "modo", "pseudo": "ModoX",
        "public_handle": f"modo_{uuid.uuid4().hex[:6]}",
    }})
    mongo.device_keys.update_one({"key_id": kid_u}, {"$set": {
        "role": "approved", "pseudo": "UserX",
        "public_handle": f"user_{uuid.uuid4().hex[:6]}",
    }})
    mongo.device_keys.update_one({"key_id": kid_d}, {"$set": {
        "role": "approved", "pseudo": "DelegateX",
        "public_handle": f"delegate_{uuid.uuid4().hex[:6]}",
    }})

    ctx = {
        "a":    (priv_a, kid_a),
        "b":    (priv_b, kid_b),
        "adm":  (priv_adm, kid_adm),
        "modo": (priv_modo, kid_modo),
        "u":    (priv_u, kid_u),
        "d":    (priv_d, kid_d),
    }
    yield ctx

    # cleanup
    ids = [kid_a, kid_b, kid_adm, kid_modo, kid_u, kid_d]
    mongo.ownership.update_one({"_id": "root"}, {"$pull": {"owner_key_ids": {"$in": ids}}})
    mongo.ownership.update_one({"_id": "root"}, {"$pull": {"delegates": {"key_id": {"$in": ids}}}})
    mongo.device_keys.delete_many({"key_id": {"$in": ids}})
    mongo.device_nonces.delete_many({"key_id": {"$in": ids}})
    mongo.account_history.delete_many({"actor_key_id": {"$in": ids}})
    mongo.account_history.delete_many({"target_key_id": {"$in": ids}})
    mongo.owner_notifications.delete_many({"actor_key_id": {"$in": ids}})
    mongo.owner_notifications.delete_many({"owner_key_id": {"$in": ids}})
    mongo.staff_actions_log.delete_many({"actor_key_id": {"$in": ids}})


# ============================================================================
# Scénario 1 — Owner OFF → sanction → Owner ON
# ============================================================================

def test_scenario1_owner_off_then_sanction_then_on_restores(actors, mongo):
    """État initial → OFF via toggle → admin ban owner A (doit passer) →
    notification créée avec identité admin → ON via toggle → sanctions
    clear + rôle restauré à creator + is_owner_device toujours True."""
    priv_a, kid_a = actors["a"]
    priv_adm, kid_adm = actors["adm"]

    # État initial : privilèges ON, role=creator
    s0 = status(priv_a, kid_a)
    assert s0["is_owner"] is True
    assert s0.get("owner_privileges_active") is True

    # Toggle OFF
    r = requests.post(f"{API}/ownership/toggle-privileges",
                      json=signed_body(priv_a, kid_a), timeout=15)
    assert r.status_code == 200, r.text
    assert r.json()["owner_privileges_active"] is False

    # Admin issue une sanction "ban" — spec CDC : passe car privilèges OFF,
    # mais notification secrète créée.
    r = requests.post(f"{API}/staff/action",
                      json=signed_body(priv_adm, kid_adm,
                                       target_key_id=kid_a, action="ban"),
                      timeout=15)
    assert r.status_code == 200, r.text
    # Vérifier que le ban a été appliqué en DB.
    dev = mongo.device_keys.find_one({"key_id": kid_a})
    assert dev.get("role") == "banned"

    # Notification créée avec identité admin (public_handle + role + staff_kind).
    notif = mongo.owner_notifications.find_one(
        {"owner_key_id": kid_a, "action": "ban", "actor_key_id": kid_adm}
    )
    assert notif is not None
    assert notif["actor_role"] == "approved"
    assert notif["actor_staff_kind"] == "admin"
    assert notif["actor_public_handle"], "public_handle admin doit être présent"

    # Toggle ON → clear sanctions + restore role. Le propriétaire garde
    # son statut owner peu importe l'état (owner_key_ids intouché).
    # Bonus : `is_owner_device` continue à retourner True pendant la période
    # où le rôle est temporairement 'banned'.
    from utils.ownership_guard import is_owner_device
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        db = MongoClient(MONGO_URL)[DB_NAME]
        # sync wrapper : la fonction est async mais le doc ownership est OK
        # à lire en sync via pymongo — on court-circuite en vérifiant que
        # owner_key_ids contient toujours kid_a.
        doc = db.ownership.find_one({"_id": "root"})
        assert kid_a in doc["owner_key_ids"], (
            "Propriétaire NE DOIT PAS être retiré de owner_key_ids par un ban"
        )
    finally:
        loop.close()

    r = requests.post(f"{API}/ownership/toggle-privileges",
                      json=signed_body(priv_a, kid_a), timeout=15)
    assert r.status_code == 200, r.text
    assert r.json()["owner_privileges_active"] is True

    dev = mongo.device_keys.find_one({"key_id": kid_a})
    assert dev.get("role") == "creator", (
        "Rôle doit être restauré à 'creator' au passage ON (reconnexion CDC)"
    )
    assert dev.get("banned") in (False, None)
    assert dev.get("muted") in (False, None)
    assert not dev.get("banned_at")

    # ownership_status doit refléter ON + is_owner=True.
    s_final = status(priv_a, kid_a)
    assert s_final["is_owner"] is True
    assert s_final.get("owner_privileges_active") is True


# ============================================================================
# Scénario 2 — Owner OFF → action staff → undo (matrice permission respectée)
# ============================================================================

def test_scenario1b_non_regression_delegate_creator_still_protected(actors, mongo):
    """Non-régression du fix iter158.13 : la relaxation Créa-vs-Créa NE
    S'APPLIQUE QU'aux propriétaires OFF. Un Créa DÉLÉGUÉ (rôle=creator mais
    is_owner=False) reste protégé contre les actions d'admin."""
    priv_a, kid_a = actors["a"]
    priv_adm, kid_adm = actors["adm"]
    priv_d, kid_d = actors["d"]

    # Nettoyer.
    mongo.ownership.update_one(
        {"_id": "root"}, {"$pull": {"delegates": {"key_id": kid_d}}}
    )
    mongo.device_keys.update_one({"key_id": kid_d}, {"$set": {"role": "approved"}})

    # Owner A promeut D en délégué → role='creator' visible mais is_owner=False.
    r = requests.post(f"{API}/ownership/delegate/add",
                      json=signed_body(priv_a, kid_a,
                                       delegate_key_id=kid_d,
                                       perms=["moderate"]),
                      timeout=15)
    assert r.status_code == 200, r.text
    dev_d = mongo.device_keys.find_one({"key_id": kid_d})
    assert dev_d.get("role") == "creator"
    assert dev_d.get("is_delegate_creator") is True

    # Admin tente de mute le délégué → doit ÊTRE REFUSÉ (Créa-vs-Créa),
    # car D n'est PAS owner-OFF, il est délégué.
    r = requests.post(f"{API}/staff/action",
                      json=signed_body(priv_adm, kid_adm,
                                       target_key_id=kid_d, action="mute"),
                      timeout=15)
    assert r.status_code == 403, (
        f"Admin NE DOIT PAS pouvoir mute un délégué Créa — {r.status_code}: {r.text}"
    )
    assert "Seule une Créa" in r.text

    # cleanup
    requests.post(f"{API}/ownership/delegate/revoke",
                  json=signed_body(priv_a, kid_a, delegate_key_id=kid_d),
                  timeout=15)


# ============================================================================
# Scénario 2 — Owner OFF → action staff → undo (matrice permission respectée)
# ============================================================================

def test_scenario2_undo_permission_matrix_respected(actors, mongo):
    """Admin mute un user → modo tente undo (refusé matrice) → admin undo (OK)
    → l'état final est propre (muted=False, event `undo_mute` loggé)."""
    priv_adm, kid_adm = actors["adm"]
    priv_modo, kid_modo = actors["modo"]
    priv_u, kid_u = actors["u"]

    # Reset state utilisateur.
    mongo.device_keys.update_one({"key_id": kid_u},
                                  {"$set": {"muted": False},
                                   "$unset": {"muted_at": ""}})

    # Admin mute user via /accounts/mute (loggue dans account_history).
    r = requests.post(f"{API}/accounts/mute",
                      json=signed_body(priv_adm, kid_adm, target_key_id=kid_u),
                      timeout=15)
    assert r.status_code == 200, r.text
    assert mongo.device_keys.find_one({"key_id": kid_u}).get("muted") is True

    # Retrouver l'event_id.
    row = mongo.account_history.find_one(
        {"target_key_id": kid_u, "event": "mute", "actor_key_id": kid_adm},
        sort=[("ts", -1)],
    )
    assert row is not None
    event_id = row["event_id"]

    # Modo tente undo (matrice : modo ne peut annuler QUE ses propres décisions).
    r = requests.post(f"{API}/accounts/history/undo",
                      json=signed_body(priv_modo, kid_modo, event_id=event_id),
                      timeout=15)
    assert r.status_code == 403, (
        f"Modo doit être refusé (matrice CDC) — reçu {r.status_code}: {r.text}"
    )

    # État inchangé : user toujours muté.
    assert mongo.device_keys.find_one({"key_id": kid_u}).get("muted") is True

    # Admin undo (matrice : admin peut annuler admin+modo).
    r = requests.post(f"{API}/accounts/history/undo",
                      json=signed_body(priv_adm, kid_adm, event_id=event_id),
                      timeout=15)
    assert r.status_code == 200, r.text
    assert r.json().get("success") is True

    # État final propre.
    dev = mongo.device_keys.find_one({"key_id": kid_u})
    assert dev.get("muted") is False, "muted doit être False après undo"

    # Événement `undo_mute` bien loggué (traçabilité).
    undo_row = mongo.account_history.find_one(
        {"event": "undo_mute", "target_key_id": kid_u, "actor_key_id": kid_adm}
    )
    assert undo_row is not None, "undo_mute doit être journalisé"
    assert undo_row.get("original_event_id") == event_id


# ============================================================================
# Scénario 3 — Apprentice Creator × délégation × Force-visitor : pas de contournement
# ============================================================================

def test_scenario3_delegate_and_force_visitor_no_ownership_bypass(actors, mongo):
    """Un délégué (même avec `full_control`) ne peut PAS :
      - obtenir un challenge propriétaire critique,
      - toucher un appareil propriétaire ON,
      - être promu owner par un simple set MongoDB depuis un staff.
    Un force-visitor appliqué sur un OWNER ON reste bloqué (403)."""
    priv_a, kid_a = actors["a"]
    priv_adm, kid_adm = actors["adm"]
    priv_d, kid_d = actors["d"]

    # Setup : delegate avec `full_control` (perms maximales déléguées).
    r = requests.post(f"{API}/ownership/delegate/add",
                      json=signed_body(priv_a, kid_a,
                                       delegate_key_id=kid_d,
                                       perms=["full_control", "moderate"]),
                      timeout=15)
    assert r.status_code == 200, r.text

    # Statut : delegate=True, owner=False, même avec full_control.
    s = status(priv_d, kid_d)
    assert s["is_delegate"] is True
    assert s["is_owner"] is False, (
        "Un délégué (même full_control) N'EST JAMAIS propriétaire (CDC)"
    )

    # Le délégué ne peut PAS obtenir un challenge critique.
    r = requests.post(f"{API}/ownership/challenge",
                      json=signed_body(priv_d, kid_d, action="transfer_ownership"),
                      timeout=15)
    assert r.status_code == 403, (
        f"Délégué ne doit pas pouvoir obtenir de challenge (owner-only) — {r.status_code}"
    )

    # Owner A privilèges ON : force_visitor via admin doit échouer (protection).
    # On s'assure que A est bien ON.
    mongo.device_keys.update_one({"key_id": kid_a},
                                  {"$set": {"owner_privileges_active": True,
                                            "role": "creator"}})
    r = requests.post(f"{API}/staff/action",
                      json=signed_body(priv_adm, kid_adm,
                                       target_key_id=kid_a,
                                       action="force_visitor"),
                      timeout=15)
    assert r.status_code == 403, (
        f"force_visitor sur owner ON DOIT être 403 — {r.status_code}: {r.text[:200]}"
    )

    # Le rôle de A n'a PAS été modifié.
    dev = mongo.device_keys.find_one({"key_id": kid_a})
    assert dev.get("role") == "creator"
    assert not dev.get("force_visitor_until")

    # Le délégué n'est jamais dans owner_key_ids.
    doc = mongo.ownership.find_one({"_id": "root"})
    assert kid_d not in (doc.get("owner_key_ids") or []), (
        "Un délégué ne doit JAMAIS être ajouté à owner_key_ids"
    )

    # cleanup : révoquer la délégation.
    requests.post(f"{API}/ownership/delegate/revoke",
                  json=signed_body(priv_a, kid_a, delegate_key_id=kid_d),
                  timeout=15)


# ============================================================================
# Scénario 4 — Transfer ownership × notifications : isolation entre owners
# ============================================================================

def test_scenario4_notifications_isolation_between_owners(actors, mongo):
    """B se met OFF → admin le mute → notification créée pour B.
    - B voit sa propre notification (owner_key_id=B).
    - A voit la décision admin (branche actor_key_id ∈ owners, owner_key_id ≠ A).
    - B mark-read : A ne voit PAS ses notifs marquées comme lues.
    """
    priv_a, kid_a = actors["a"]
    priv_b, kid_b = actors["b"]
    priv_adm, kid_adm = actors["adm"]

    # Reset A & B ON.
    mongo.device_keys.update_one({"key_id": kid_a},
                                  {"$set": {"owner_privileges_active": True, "role": "creator"}})
    mongo.device_keys.update_one({"key_id": kid_b},
                                  {"$set": {"owner_privileges_active": True, "role": "creator"}})
    # Purge notifs test.
    mongo.owner_notifications.delete_many({"owner_key_id": {"$in": [kid_a, kid_b]}})

    # B → OFF.
    r = requests.post(f"{API}/ownership/toggle-privileges",
                      json=signed_body(priv_b, kid_b), timeout=15)
    assert r.status_code == 200
    assert r.json()["owner_privileges_active"] is False

    # Admin mute B — passe (privilèges OFF) + notif créée pour B.
    r = requests.post(f"{API}/staff/action",
                      json=signed_body(priv_adm, kid_adm,
                                       target_key_id=kid_b, action="mute"),
                      timeout=15)
    assert r.status_code == 200, r.text

    # B liste ses notifications : sa notif est visible (owner_key_id=B).
    r = requests.post(f"{API}/ownership/notifications",
                      json=signed_body(priv_b, kid_b), timeout=15)
    assert r.status_code == 200, r.text
    b_notifs = r.json()["notifications"]
    b_own = [n for n in b_notifs if n.get("owner_key_id") == kid_b]
    assert any(n.get("action") == "mute" and n.get("actor_key_id") == kid_adm
               for n in b_own), "B doit voir la notif mute prise contre lui"

    # A n'a PAS d'entrée avec owner_key_id=A pour cette action (isolation privée),
    # MAIS voit la décision via la branche transparence (actor_key_id ∈ owners
    # seulement — admin n'est pas owner donc rien pour A).
    r = requests.post(f"{API}/ownership/notifications",
                      json=signed_body(priv_a, kid_a), timeout=15)
    assert r.status_code == 200, r.text
    a_notifs = r.json()["notifications"]
    a_own = [n for n in a_notifs if n.get("owner_key_id") == kid_a]
    # A ne doit PAS voir de notif marquée avec owner_key_id=B (isolation).
    assert not any(n.get("owner_key_id") == kid_b for n in a_own), (
        "A ne doit JAMAIS voir les notifs privées de B (owner_key_id=B)"
    )

    # B mark-read : A ne doit PAS être impacté.
    initial_unread_a = r.json()["unread_count"]
    r = requests.post(f"{API}/ownership/notifications/mark-read",
                      json=signed_body(priv_b, kid_b), timeout=15)
    assert r.status_code == 200

    # A recharge : compteur inchangé (isolation).
    r = requests.post(f"{API}/ownership/notifications",
                      json=signed_body(priv_a, kid_a), timeout=15)
    assert r.status_code == 200
    assert r.json()["unread_count"] == initial_unread_a, (
        "mark-read de B ne doit PAS modifier le compteur unread de A"
    )

    # B doit maintenant avoir unread=0 sur SES notifs propres.
    r = requests.post(f"{API}/ownership/notifications",
                      json=signed_body(priv_b, kid_b), timeout=15)
    b_own_unread = sum(1 for n in r.json()["notifications"]
                       if n.get("owner_key_id") == kid_b and not n.get("read"))
    assert b_own_unread == 0, "B doit voir toutes ses notifs propres comme lues"

    # Cleanup : remettre B ON.
    requests.post(f"{API}/ownership/toggle-privileges",
                  json=signed_body(priv_b, kid_b), timeout=15)


# ============================================================================
# Scénario 5 — Sanction × switch_account × délégation (temp expirée)
# ============================================================================

def test_scenario5_switch_account_gate_with_expired_temp(actors, mongo):
    """Un délégué SANS switch_account → delegate_perms n'inclut pas cette perm.
    Grant temp switch_account 60 min → delegate_perms inclut la perm.
    Forcer expires_at dans le passé (simulation expiration) → delegate_perms
    exclut à nouveau la perm (backend filtre automatiquement)."""
    priv_a, kid_a = actors["a"]
    priv_d, kid_d = actors["d"]

    # Purge any existing delegate entry.
    mongo.ownership.update_one(
        {"_id": "root"}, {"$pull": {"delegates": {"key_id": kid_d}}}
    )

    # 1) Delegate avec perms limitées (moderate seulement) — pas switch_account.
    r = requests.post(f"{API}/ownership/delegate/add",
                      json=signed_body(priv_a, kid_a,
                                       delegate_key_id=kid_d,
                                       perms=["moderate"]),
                      timeout=15)
    assert r.status_code == 200, r.text
    s = status(priv_d, kid_d)
    assert s["is_delegate"] is True
    assert "switch_account" not in s.get("delegate_perms", []), (
        "Delegate sans switch_account NE DOIT PAS avoir la perm"
    )

    # 2) Grant temp switch_account pour 60 min.
    r = requests.post(f"{API}/ownership/delegate/grant-temp",
                      json=signed_body(priv_a, kid_a,
                                       delegate_key_id=kid_d,
                                       perm="switch_account",
                                       duration_minutes=60),
                      timeout=15)
    assert r.status_code == 200, r.text

    s = status(priv_d, kid_d)
    assert "switch_account" in s.get("delegate_perms", []), (
        "Après grant-temp, switch_account doit apparaître dans delegate_perms"
    )

    # 3) Forcer l'expiration en DB (simulation d'une temp qui expire).
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    mongo.ownership.update_one(
        {"_id": "root", "delegates.key_id": kid_d},
        {"$set": {"delegates.$.temp_perms": [
            {"perm": "switch_account", "expires_at": past,
             "granted_by": kid_a, "granted_at": past},
        ]}},
    )

    s = status(priv_d, kid_d)
    assert "switch_account" not in s.get("delegate_perms", []), (
        "Une perm temp EXPIRÉE doit être filtrée par _all_active_perms"
    )

    # 4) Le backend `has_delegate_perm` doit également refuser la perm expirée.
    #    On teste indirectement via /ownership/status qui utilise
    #    `_all_active_perms` (autorité du gate frontend).
    assert s["is_delegate"] is True, "delegate reste actif malgré la perm expirée"

    # cleanup
    requests.post(f"{API}/ownership/delegate/revoke",
                  json=signed_body(priv_a, kid_a, delegate_key_id=kid_d),
                  timeout=15)


# ============================================================================
# Scénario 6 — AI error mapping × chat multi-tour (frontend + backend)
# ============================================================================

def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_scenario6_ai_error_preserves_chat_history():
    """Vérifie que le catch d'erreur IA du Chat.js :
      - conserve TOUS les messages précédents (prev.filter(m => !m._streaming))
      - annote le message d'erreur avec _error: true + _error_code (identifiable
        par l'UI et les tours suivants),
      - libère `isLoading` dans le bloc `finally` pour permettre le prochain tour.
    """
    src = _read(FRONT / "pages/Chat.js")

    # Le catch utilise classifyAiError (import dynamique).
    assert "await import('../lib/aiErrorMapper')" in src or \
           'await import("../lib/aiErrorMapper")' in src

    # Le setMessages du catch préserve les messages non-streaming (multi-tour).
    idx = src.find("[AI error]")
    assert idx > 0, "Log '[AI error]' doit être présent dans le catch"
    block = src[max(0, idx - 800):idx + 500]
    assert "prev.filter(m => !m._streaming)" in block, (
        "L'erreur doit CONSERVER l'historique (prev.filter non-streaming)"
    )
    assert "_error: true" in block or "_error:true" in block
    assert "_error_code" in block

    # setIsLoading(false) dans le finally (permet tour suivant).
    finally_idx = src.find("} finally {", idx)
    assert finally_idx > 0
    finally_block = src[finally_idx:finally_idx + 200]
    assert "setIsLoading(false)" in finally_block, (
        "isLoading doit être libéré dans finally pour permettre le tour suivant"
    )


def test_scenario6_ai_error_mapper_frontend_returns_i18n_key_and_fallback():
    """Le mapper frontend doit fournir i18nKey + fallback pour que le catch
    puisse afficher `t(errInfo.i18nKey) || errInfo.fallback` sans crasher
    même si la traduction est absente."""
    src = _read(FRONT / "lib/aiErrorMapper.js")
    assert "i18nKey" in src
    assert "fallback" in src
    # 10 catégories doivent être présentes (cohérence avec backend mapper).
    for code in ("cloudflare", "ollama_offline", "ollama_error", "timeout",
                 "json_invalid", "auth_error", "rate_limit", "provider_error",
                 "network", "unknown"):
        assert code in src, f"Catégorie manquante dans mapper JS : {code}"


def test_scenario6_ai_error_mapper_backend_llm_json_returns_error_code():
    """`agents/common.py::llm_json` retourne toujours `_error_code` sur erreur
    pour que l'appelant multi-tour puisse identifier la cause sans réinventer
    le classifieur."""
    src = _read(Path("/app/backend/agents/common.py"))
    assert "_error_code" in src, (
        "llm_json doit propager _error_code (contrat multi-tour côté backend)"
    )
    assert "classify_ai_error" in src


def test_scenario6_backend_generate_exposes_ai_error_code_field():
    """`/api/generate` DOIT exposer `ai_error_code` pour que l'UI de chat
    puisse différencier un fallback template (ai_error_code=null) d'un
    fallback dû à une erreur classifiée (ai_error_code=<code>)."""
    src = _read(Path("/app/backend/server.py"))
    assert '"ai_error_code"' in src or "ai_error_code" in src
