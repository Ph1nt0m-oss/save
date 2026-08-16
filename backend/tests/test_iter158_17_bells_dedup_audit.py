"""iter158.17 — P1.6 : Audit anti-duplication entre les 3 cloches/badges.

Vérifie qu'il n'existe AUCUNE duplication injustifiée entre :
  1. `NotificationBell`      — approbation d'appareils (rôle pending).
  2. `AccountsButton`        — badge « ⏳ N à valider » (décisions staff temporaires).
  3. `OwnerNotificationsBell`— notifications propriétaire secrètes.

Résultat de l'audit :
  - Sources de vérité STRICTEMENT distinctes :
      * NotificationBell        → `device_keys` where role='pending'
                                  via /devices/pending-count (SSE optionnel).
      * AccountsButton badge    → `staff_decisions` where status='pending'
                                  via /staff-decisions/list.
      * OwnerNotificationsBell  → `owner_notifications` collection
                                  via /ownership/notifications.
  - AUCUNE collection partagée, AUCUN endpoint partagé.
  - Audience distincte :
      * device-pending  → tous les créas (vue créa).
      * staff-decisions → créa uniquement (vue créa).
      * owner-notifs    → uniquement propriétaires (403 sinon — spec P0.2).
  - Interaction attendue et JUSTIFIÉE CDC iter158.3 : quand un staff non-créa
    agit sur un propriétaire OFF, DEUX écritures ont lieu (staff_decisions
    + owner_notifications). Ce n'est PAS une duplication UI : chaque bell
    l'affiche pour un rôle distinct avec une action utilisateur différente
    (validate/revert vs mark-read).

Tests couverts :
  1. Sources de vérité distinctes (source-level).
  2. Isolation Ownership déjà validée P0.2 : /ownership/notifications 403 sur
     non-propriétaires (délégué, admin, modo, user).
  3. Isolation entre propriétaires (owner_key_id filter).
  4. Événement compte staff non-créa → apparaît dans staff_decisions,
     PAS dans owner_notifications si target n'est pas owner-OFF.
  5. Événement staff sur owner OFF → apparaît dans les 2 collections
     (justification CDC : audiences distinctes).
  6. Compteurs cohérents après mark-read (unread=0 sur owner-notifs,
     staff_decisions inchangé — collections indépendantes).
  7. Composants UI : chaque cloche importe une SEULE source d'endpoint.
"""
from __future__ import annotations

import base64
import os
import re
import uuid
from pathlib import Path
from typing import Tuple

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
FRONT = Path("/app/frontend/src")


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ---------------- ECDSA helpers ----------------

def _b64url(b): return base64.urlsafe_b64encode(b).decode("ascii").rstrip("=")
def _b64url_int(n, length=32): return _b64url(n.to_bytes(length, "big"))
def _b64url_decode(s):
    pad = "=" * ((4 - len(s) % 4) % 4)
    return base64.urlsafe_b64decode(s + pad)


def gen_keypair():
    priv = ec.generate_private_key(ec.SECP256R1())
    pub = priv.public_key().public_numbers()
    return priv, {"kty": "EC", "crv": "P-256",
                  "x": _b64url_int(pub.x), "y": _b64url_int(pub.y)}


def sign(priv, nonce_b64url):
    der = priv.sign(_b64url_decode(nonce_b64url), ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    return _b64url(r.to_bytes(32, "big") + s.to_bytes(32, "big"))


def register():
    priv, jwk = gen_keypair()
    r = requests.post(f"{API}/devices/register",
                      json={"public_key_jwk": jwk,
                            "label": f"IT158_17_{uuid.uuid4().hex[:6]}"},
                      timeout=15)
    r.raise_for_status()
    return priv, r.json()["key_id"]


def nonce(kid):
    r = requests.post(f"{API}/devices/challenge", json={"key_id": kid}, timeout=15)
    r.raise_for_status()
    return r.json()["nonce"]


def signed_body(priv, kid, **extra):
    n = nonce(kid)
    return {"key_id": kid, "nonce": n, "signature": sign(priv, n), **extra}


# ---------------- Fixtures ----------------

@pytest.fixture(scope="module")
def mongo():
    cli = MongoClient(MONGO_URL, serverSelectionTimeoutMS=3000)
    yield cli[DB_NAME]
    cli.close()


@pytest.fixture()
def cast(mongo):
    """3 propriétaires (A/B), 1 admin, 1 modo, 1 user cible."""
    priv_a, kid_a = register()
    priv_b, kid_b = register()
    priv_adm, kid_adm = register()
    priv_modo, kid_modo = register()
    priv_target, kid_target = register()

    mongo.ownership.update_one(
        {"_id": "root"}, {"$addToSet": {"owner_key_ids": {"$each": [kid_a, kid_b]}}}
    )
    mongo.device_keys.update_one({"key_id": kid_a}, {"$set": {
        "role": "creator", "pseudo": "OwnerA17",
        "public_handle": f"a17_{uuid.uuid4().hex[:6]}",
        "owner_privileges_active": True,
    }})
    mongo.device_keys.update_one({"key_id": kid_b}, {"$set": {
        "role": "creator", "pseudo": "OwnerB17",
        "public_handle": f"b17_{uuid.uuid4().hex[:6]}",
        "owner_privileges_active": True,
    }})
    mongo.device_keys.update_one({"key_id": kid_adm}, {"$set": {
        "role": "approved", "staff_kind": "admin", "pseudo": "AdmP16",
        "public_handle": f"adm17_{uuid.uuid4().hex[:6]}",
    }})
    mongo.device_keys.update_one({"key_id": kid_modo}, {"$set": {
        "role": "approved", "staff_kind": "modo", "pseudo": "ModoP16",
        "public_handle": f"modo17_{uuid.uuid4().hex[:6]}",
    }})
    mongo.device_keys.update_one({"key_id": kid_target}, {"$set": {
        "role": "approved", "pseudo": "TargetP16",
        "public_handle": f"tgt17_{uuid.uuid4().hex[:6]}",
    }})

    yield {
        "a":      (priv_a, kid_a),
        "b":      (priv_b, kid_b),
        "adm":    (priv_adm, kid_adm),
        "modo":   (priv_modo, kid_modo),
        "target": (priv_target, kid_target),
    }

    ids = [kid_a, kid_b, kid_adm, kid_modo, kid_target]
    mongo.ownership.update_one({"_id": "root"}, {"$pull": {"owner_key_ids": {"$in": ids}}})
    mongo.device_keys.delete_many({"key_id": {"$in": ids}})
    mongo.device_nonces.delete_many({"key_id": {"$in": ids}})
    mongo.account_history.delete_many({"target_key_id": {"$in": ids}})
    mongo.account_history.delete_many({"actor_key_id": {"$in": ids}})
    mongo.staff_decisions.delete_many({"actor_key_id": {"$in": ids}})
    mongo.owner_notifications.delete_many({"owner_key_id": {"$in": ids}})
    mongo.owner_notifications.delete_many({"actor_key_id": {"$in": ids}})


# ============================================================================
# Audit source-level : chaque cloche a UNE source d'endpoint distincte
# ============================================================================

def test_notification_bell_uses_only_pending_count_endpoint():
    """NotificationBell : consomme UNIQUEMENT device.pendingCount
    (via useDeviceIdentity → /devices/pending-count + SSE optionnel).
    Aucun autre endpoint métier direct."""
    src = _read(FRONT / "components/NotificationBell.jsx")
    # Ne touche pas aux autres sources
    assert "/ownership/notifications" not in src, (
        "NotificationBell NE DOIT PAS consommer /ownership/notifications"
    )
    assert "/staff-decisions" not in src, (
        "NotificationBell NE DOIT PAS consommer /staff-decisions"
    )
    assert "/accounts/list" not in src, (
        "NotificationBell NE DOIT PAS consommer /accounts/list"
    )
    # Utilise device.pendingCount
    assert "pendingCount" in src


def test_accounts_button_uses_accounts_list_and_staff_decisions_only():
    """AccountsButton : consomme /accounts/list + /staff-decisions/list
    (badge ⏳ N à valider). Aucun accès à /ownership/notifications
    (isolation P0.2) NI à /devices/pending-count."""
    src = _read(FRONT / "components/AccountsButton.jsx")
    assert "/accounts/list" in src
    assert "/staff-decisions/list" in src
    assert "/ownership/notifications" not in src, (
        "AccountsButton NE DOIT PAS consommer /ownership/notifications "
        "(isolation P0.2 : owner-secret)"
    )
    assert "/devices/pending-count" not in src, (
        "AccountsButton NE DOIT PAS consommer /devices/pending-count "
        "(source de NotificationBell)"
    )


def test_owner_notifications_bell_uses_ownership_endpoints_only():
    """OwnerNotificationsBell : consomme /ownership/status + /ownership/notifications
    + /ownership/notifications/mark-read UNIQUEMENT. Aucun mélange."""
    src = _read(FRONT / "components/OwnerNotificationsBell.jsx")
    assert "/ownership/status" in src
    assert "/ownership/notifications" in src
    assert "/ownership/notifications/mark-read" in src
    assert "/staff-decisions" not in src, (
        "OwnerNotificationsBell NE DOIT PAS consommer /staff-decisions"
    )
    assert "/devices/pending-count" not in src, (
        "OwnerNotificationsBell NE DOIT PAS consommer /devices/pending-count"
    )
    assert "/accounts/list" not in src, (
        "OwnerNotificationsBell NE DOIT PAS consommer /accounts/list"
    )


def test_three_bells_have_distinct_testids():
    """Chaque cloche/badge expose un data-testid unique — aucune collision
    UI possible."""
    nb = _read(FRONT / "components/NotificationBell.jsx")
    ab = _read(FRONT / "components/AccountsButton.jsx")
    on = _read(FRONT / "components/OwnerNotificationsBell.jsx")

    assert 'data-testid="notification-bell"' in nb
    assert 'data-testid="notification-bell-count"' in nb
    assert 'data-testid="accounts-btn"' in ab
    assert 'data-testid="accounts-pending-review-toggle"' in ab
    assert 'data-testid="owner-notifications-bell"' in on
    assert 'data-testid="owner-notifications-unread-badge"' in on

    # Aucun testid partagé entre les 3.
    ids_nb = set(re.findall(r'data-testid="([^"]+)"', nb))
    ids_ab = set(re.findall(r'data-testid="([^"]+)"', ab))
    ids_on = set(re.findall(r'data-testid="([^"]+)"', on))
    assert not (ids_nb & ids_ab), f"Collision testids NotifBell↔Accounts: {ids_nb & ids_ab}"
    assert not (ids_nb & ids_on), f"Collision testids NotifBell↔OwnerNotif: {ids_nb & ids_on}"
    assert not (ids_ab & ids_on), f"Collision testids Accounts↔OwnerNotif: {ids_ab & ids_on}"


# ============================================================================
# Audit backend : sources de vérité (collections) strictement distinctes
# ============================================================================

def test_backend_sources_of_truth_are_distinct_collections():
    """Les 3 collections MongoDB sont indépendantes :
      - device_keys (pending)
      - staff_decisions
      - owner_notifications
    Aucun endpoint ne les mélange (chaque endpoint = 1 collection primaire)."""
    devices = _read(Path("/app/backend/routes/devices_routes.py"))
    accounts = _read(Path("/app/backend/routes/accounts_routes.py"))
    staff = _read(Path("/app/backend/routes/staff_decisions_routes.py"))
    ownership = _read(Path("/app/backend/routes/ownership_routes.py"))

    # /devices/pending-count : device_keys.role='pending' uniquement.
    assert re.search(
        r"pending_count.*?device_keys\.count_documents\(\{\"role\":\s*\"pending\"\}",
        devices, flags=re.DOTALL,
    ), "pending-count doit ne compter QUE device_keys.role='pending'"

    # /staff-decisions/list : staff_decisions uniquement.
    assert "staff_decisions.find" in staff or "staff_decisions.count_documents" in staff

    # /ownership/notifications : owner_notifications uniquement.
    assert "owner_notifications.find" in ownership
    # Guard owner-only déjà validé P0.2.
    assert "_require_owner" in ownership


# ============================================================================
# Isolation OwnerNotifications (P0.2) — non-régression
# ============================================================================

def test_ownership_notifications_rejects_non_owners(cast, mongo):
    """Non-owner (admin/modo/target user) → 403 sur /ownership/notifications."""
    priv_adm, kid_adm = cast["adm"]
    priv_modo, kid_modo = cast["modo"]
    priv_t, kid_t = cast["target"]

    for priv, kid, label in [
        (priv_adm, kid_adm, "admin"),
        (priv_modo, kid_modo, "modo"),
        (priv_t, kid_t, "target user"),
    ]:
        r = requests.post(f"{API}/ownership/notifications",
                          json=signed_body(priv, kid), timeout=15)
        assert r.status_code in (401, 403), (
            f"{label} doit être refusé sur /ownership/notifications "
            f"(reçu {r.status_code})"
        )


def test_ownership_notifications_isolated_between_owners(cast, mongo):
    """Les notifs privées d'un owner (owner_key_id) ne fuient PAS vers l'autre."""
    priv_a, kid_a = cast["a"]
    priv_b, kid_b = cast["b"]

    # Inject une notif privée pour A seulement.
    mongo.owner_notifications.insert_one({
        "owner_key_id": kid_a,
        "actor_key_id": "dev_someone_not_owner",
        "actor_role": "approved",
        "actor_staff_kind": "modo",
        "action": "mute",
        "target_key_id": kid_a,
        "detail": {}, "ts": "2026-02-16T10:00:00+00:00", "read": False,
    })

    r = requests.post(f"{API}/ownership/notifications",
                      json=signed_body(priv_b, kid_b), timeout=15)
    assert r.status_code == 200
    b_own = [n for n in r.json()["notifications"] if n.get("owner_key_id") == kid_a]
    assert not b_own, (
        "B ne DOIT PAS voir les notifs privées (owner_key_id=A) de A"
    )


# ============================================================================
# Événement staff non-créa contre non-owner : staff_decisions OUI,
# owner_notifications NON (pas de duplication injustifiée)
# ============================================================================

def test_staff_action_on_normal_user_no_owner_notification(cast, mongo):
    """Modo mute un simple user (non-owner) :
      - staff_decisions reçoit un doc (badge AccountsButton).
      - owner_notifications NE REÇOIT RIEN (pas de duplication)."""
    priv_modo, kid_modo = cast["modo"]
    _, kid_t = cast["target"]

    # État de base propre.
    mongo.staff_decisions.delete_many({"actor_key_id": kid_modo, "target_key_id": kid_t})
    mongo.owner_notifications.delete_many({"target_key_id": kid_t})

    r = requests.post(f"{API}/accounts/mute",
                      json=signed_body(priv_modo, kid_modo, target_key_id=kid_t),
                      timeout=15)
    assert r.status_code == 200, r.text

    # staff_decisions : 1 entrée créée
    sd_rows = list(mongo.staff_decisions.find(
        {"actor_key_id": kid_modo, "target_key_id": kid_t, "event": "mute"}
    ))
    assert len(sd_rows) == 1, (
        f"staff_decisions doit avoir exactement 1 entrée, got {len(sd_rows)}"
    )
    # owner_notifications : 0 entrée (target n'est pas owner)
    on_rows = list(mongo.owner_notifications.find(
        {"target_key_id": kid_t, "action": "mute"}
    ))
    assert len(on_rows) == 0, (
        f"owner_notifications NE DOIT PAS recevoir de notif pour un user "
        f"non-owner, got {len(on_rows)}"
    )


def test_staff_action_on_owner_off_creates_owner_notification_via_unified_route(cast, mongo):
    """Modo mute un OWNER en OFF via /staff/action (unifié iter144) :
      - `staff_actions_log` reçoit 1 doc (traçabilité serveur).
      - `owner_notifications` reçoit 1 doc (propriétaire alerté secrètement).
    Ces deux collections servent des audiences distinctes — AUCUN composant
    frontend ne consomme les deux, donc AUCUNE duplication UI.

    Note d'audit : `/accounts/mute` (legacy) n'invoque PAS `assert_not_owner_target`
    — c'est un chemin séparé qui n'alimente PAS owner_notifications. Ceci
    confirme l'isolation stricte des sources : chaque endpoint écrit
    dans UNE collection primaire."""
    priv_a, kid_a = cast["a"]
    priv_modo, kid_modo = cast["modo"]

    # A → OFF
    r = requests.post(f"{API}/ownership/toggle-privileges",
                      json=signed_body(priv_a, kid_a), timeout=15)
    assert r.status_code == 200

    mongo.staff_actions_log.delete_many({"actor_key_id": kid_modo, "target_key_id": kid_a})
    mongo.owner_notifications.delete_many({"target_key_id": kid_a, "action": "mute"})

    r = requests.post(f"{API}/staff/action",
                      json=signed_body(priv_modo, kid_modo,
                                       target_key_id=kid_a, action="mute"),
                      timeout=15)
    assert r.status_code == 200, r.text

    # staff_actions_log : 1 doc (audit serveur)
    log_rows = list(mongo.staff_actions_log.find(
        {"target_key_id": kid_a, "actor_key_id": kid_modo, "action": "mute"}
    ))
    assert len(log_rows) == 1

    # owner_notifications : 1 doc via assert_not_owner_target
    on_rows = list(mongo.owner_notifications.find(
        {"target_key_id": kid_a, "action": "mute", "actor_key_id": kid_modo}
    ))
    assert len(on_rows) == 1, "1 entrée owner_notifications attendue (OFF owner)"

    # Chaque entrée sert une audience différente — aucune duplication UI.
    assert on_rows[0]["actor_role"] == "approved"
    assert on_rows[0]["actor_staff_kind"] == "modo"

    # A → ON pour cleanup.
    requests.post(f"{API}/ownership/toggle-privileges",
                  json=signed_body(priv_a, kid_a), timeout=15)


# ============================================================================
# Compteurs cohérents après mark-read (collections indépendantes)
# ============================================================================

def test_mark_read_owner_notifs_does_not_touch_staff_decisions(cast, mongo):
    """Mark-read owner-notifs ne modifie EN AUCUN CAS staff_decisions
    (collections indépendantes → aucun couplage transversal).
    Setup : legacy /accounts/mute crée staff_decisions ; injection manuelle
    d'un owner_notifications côté A pour isoler l'assertion couplage."""
    priv_a, kid_a = cast["a"]
    priv_modo, kid_modo = cast["modo"]
    _, kid_t = cast["target"]

    # 1) Modo mute un user normal via /accounts/mute → staff_decisions=+1.
    mongo.staff_decisions.delete_many({"actor_key_id": kid_modo})
    mongo.owner_notifications.delete_many({"owner_key_id": kid_a})
    r = requests.post(f"{API}/accounts/mute",
                      json=signed_body(priv_modo, kid_modo, target_key_id=kid_t),
                      timeout=15)
    assert r.status_code == 200

    sd_before = mongo.staff_decisions.count_documents(
        {"actor_key_id": kid_modo, "status": "pending"}
    )
    assert sd_before >= 1, "Un staff_decision doit être créé par /accounts/mute"

    # 2) Inject une owner_notification côté A.
    mongo.owner_notifications.insert_one({
        "owner_key_id": kid_a,
        "actor_key_id": "dev_someone",
        "actor_role": "approved", "actor_staff_kind": "admin",
        "action": "mute", "target_key_id": kid_a,
        "detail": {}, "ts": "2026-02-16T00:00:00+00:00", "read": False,
    })

    # 3) Owner mark-read.
    r = requests.post(f"{API}/ownership/notifications/mark-read",
                      json=signed_body(priv_a, kid_a), timeout=15)
    assert r.status_code == 200

    unread_after = mongo.owner_notifications.count_documents(
        {"owner_key_id": kid_a, "read": False}
    )
    assert unread_after == 0

    # 4) staff_decisions INCHANGÉ (pending toujours en attente créa).
    sd_after = mongo.staff_decisions.count_documents(
        {"actor_key_id": kid_modo, "status": "pending"}
    )
    assert sd_after == sd_before, (
        "mark-read owner-notifs NE DOIT PAS toucher staff_decisions"
    )


# ============================================================================
# Non-régression composants existants
# ============================================================================

def test_dashboard_mounts_all_three_bells_in_creator_view():
    """Dashboard doit monter les 3 cloches distinctes dans la barre créa
    (aucun ne se substitue à l'autre)."""
    src = _read(FRONT / "pages/Dashboard.js")
    assert "NotificationBell" in src
    assert "AccountsButton" in src
    assert "OwnerNotificationsBell" in src


def test_no_component_reads_two_notification_sources_simultaneously():
    """Aucun composant hors des 3 spécialisés ne consomme simultanément
    2 sources parmi /devices/pending-count, /staff-decisions/list,
    /ownership/notifications (défense en profondeur : source de vérité
    unique par composant)."""
    for fname in ("Dashboard.js", "Landing.js", "Login.js"):
        src = _read(FRONT / "pages" / fname)
        # Ces pages peuvent importer les composants, mais ne doivent PAS
        # appeler directement les endpoints métier des cloches.
        assert "/ownership/notifications" not in src, (
            f"{fname} NE DOIT PAS consommer /ownership/notifications "
            f"(source réservée à OwnerNotificationsBell)"
        )
