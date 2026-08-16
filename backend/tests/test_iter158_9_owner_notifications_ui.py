"""iter158.9 — P0.2 : Tests Owner Notifications UI (backend + frontend).

Vérifie :
  1. Backend `/ownership/notifications` réservé owner (_require_owner).
  2. `/ownership/notifications/mark-read` réservé owner + isolation par
     owner_key_id (mark-read n'affecte QUE les notifs de l'appelant).
  3. `/ownership/notifications` renvoie ses propres notifs + celles générées
     par d'autres owners (transparence, PAS de fuite entre propriétaires
     hors périmètre : chaque owner voit ses actions administrées + celles
     des autres owners, jamais les notifs privées d'un autre owner marquées
     `owner_key_id != self`).
  4. Frontend `OwnerNotificationsBell.jsx` — data-testids présents, gaté
     par `is_owner`, appelle les endpoints corrects, mark-read wired.
  5. Le composant est monté dans Dashboard uniquement dans le bloc
     conditionnel (isOwner=true).
"""
from __future__ import annotations

from pathlib import Path

BACK = Path("/app/backend")
FRONT = Path("/app/frontend/src")


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# --- Backend security (source-level) ---

def test_backend_notifications_requires_owner():
    src = _read(BACK / "routes/ownership_routes.py")
    idx = src.find('/ownership/notifications"')
    assert idx > 0
    block = src[idx:idx + 1500]
    assert "_require_owner" in block, (
        "L'endpoint doit être gaté par _require_owner (owner-only)."
    )


def test_backend_notifications_query_isolation():
    """L'appelant ne voit QUE :
      - ses propres notifs (owner_key_id == self)
      - actions d'autres OWNERS uniquement (actor_key_id ∈ owner_key_ids)
    Il ne voit jamais les notifs privées adressées à un autre owner.
    """
    src = _read(BACK / "routes/ownership_routes.py")
    idx = src.find('/ownership/notifications"')
    assert idx > 0
    block = src[idx:idx + 2000]
    assert 'owner_key_id": payload.key_id' in block
    assert "actor_key_id" in block
    assert "owner_key_ids(db)" in block
    # Filtre explicite : quand actor est owner autre, exclure ses notifs privées
    assert 'owner_key_id": {"$ne": payload.key_id}' in block


def test_backend_mark_read_isolated_per_owner():
    src = _read(BACK / "routes/ownership_routes.py")
    idx = src.find("/ownership/notifications/mark-read")
    assert idx > 0
    block = src[idx:idx + 1200]
    assert "_require_owner" in block
    # Filtre update: uniquement les notifs de l'appelant
    assert '"owner_key_id": payload.key_id' in block
    assert '"read": False' in block


def test_backend_endpoints_registered():
    src = _read(BACK / "routes/ownership_routes.py")
    assert '@router.post("/ownership/notifications")' in src
    assert '@router.post("/ownership/notifications/mark-read")' in src


# --- Frontend component ---

def test_frontend_bell_component_exists():
    p = FRONT / "components/OwnerNotificationsBell.jsx"
    assert p.exists()
    src = _read(p)
    for testid in [
        "owner-notifications-bell",
        "owner-notifications-panel",
        "owner-notifications-close",
        "owner-notifications-mark-read",
        "owner-notifications-empty",
        "owner-notifications-unread-badge",
    ]:
        assert testid in src, f"data-testid {testid} manquant"
    assert '/ownership/notifications' in src
    assert '/ownership/notifications/mark-read' in src
    assert '/ownership/status' in src  # Vérifie is_owner


def test_frontend_bell_hidden_if_not_owner():
    src = _read(FRONT / "components/OwnerNotificationsBell.jsx")
    # `if (!isOwner) return null` avant le rendu
    assert "if (!isOwner) return null" in src
    # is_owner vient de /ownership/status
    assert "r.data?.is_owner" in src


def test_frontend_bell_shows_actor_identity():
    """Le CDC exige l'affichage de l'acteur (public_handle + role/staff_kind)."""
    src = _read(FRONT / "components/OwnerNotificationsBell.jsx")
    assert "actor_public_handle" in src
    assert "actor_role" in src
    assert "actor_staff_kind" in src
    # Fallback sur key_id si pas de public_handle
    assert "actor_key_id" in src


def test_frontend_bell_marks_read_via_endpoint():
    src = _read(FRONT / "components/OwnerNotificationsBell.jsx")
    idx = src.find('/ownership/notifications/mark-read')
    assert idx > 0
    # Le bouton mark-read doit être disabled quand unread === 0
    assert "unread === 0" in src


def test_dashboard_mounts_bell():
    src = _read(FRONT / "pages/Dashboard.js")
    assert "import OwnerNotificationsBell" in src
    assert "<OwnerNotificationsBell" in src


def test_bell_does_not_leak_via_general_notification_bell():
    """Le CDC exige que les notifs OWNER ne soient PAS mélangées au système
    général de notifications (NotificationBell). Vérification source-level :
    NotificationBell.jsx ne doit pas consommer /ownership/notifications."""
    p = FRONT / "components/NotificationBell.jsx"
    if p.exists():
        src = _read(p)
        assert "/ownership/notifications" not in src, (
            "NotificationBell général ne doit PAS lire /ownership/notifications "
            "(spec CDC : notifs owner secrètes = système séparé)."
        )
