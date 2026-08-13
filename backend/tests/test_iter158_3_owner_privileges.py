"""iter158.3 — Tests source-level de la fonctionnalité Owner Privileges ON/OFF.

Vérifie que :
  1. Le module `ownership_guard` expose `is_privileges_active` + `log_owner_notification`.
  2. `assert_not_owner_target` accepte le mode OFF (log notification, no raise).
  3. Les endpoints `/ownership/toggle-privileges` et `/ownership/notifications` sont enregistrés.
  4. `/ownership/status` renvoie `owner_privileges_active` pour un owner.
  5. Le frontend possède les composants `OwnerPrivilegesToggle` et `ForceVisitorBanner`.
  6. Les traductions i18n `kick_force_visitor_*` contiennent le message CDC exact.
  7. Les traductions i18n `kick_disconnected_*` contiennent le message CDC exact.
"""
from __future__ import annotations

from pathlib import Path

BACK = Path("/app/backend")
FRONT = Path("/app/frontend/src")


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_ownership_guard_exposes_new_helpers():
    src = _read(BACK / "utils/ownership_guard.py")
    assert "async def is_privileges_active" in src
    assert "async def log_owner_notification" in src
    assert "owner_privileges_active" in src


def test_ownership_routes_toggle_and_notifications():
    src = _read(BACK / "routes/ownership_routes.py")
    assert '@router.post("/ownership/toggle-privileges")' in src
    assert '@router.post("/ownership/notifications")' in src
    assert '@router.post("/ownership/notifications/mark-read")' in src
    assert '"owner_privileges_active"' in src


def test_assert_not_owner_target_off_path_exists():
    src = _read(BACK / "utils/ownership_guard.py")
    idx = src.find("async def assert_not_owner_target")
    assert idx > 0
    block = src[idx:idx + 3500]
    assert "is_privileges_active" in block
    assert "log_owner_notification" in block
    assert "return  # Laisse l'action se poursuivre" in block


def test_toggle_privileges_clears_sanctions_and_restores_role():
    src = _read(BACK / "routes/ownership_routes.py")
    idx = src.find('/ownership/toggle-privileges')
    assert idx > 0
    block = src[idx:idx + 2500]
    for f in ("muted", "banned", "force_visitor"):
        assert f'"{f}"' in block, f"Le champ {f} doit être clear en toggle ON"
    for tf in ("exclude_until", "force_visitor_until", "disconnect_until"):
        assert f'"{tf}"' in block, f"Le champ temporel {tf} doit être unset en toggle ON"
    assert '("blocked", "banned")' in block


def test_frontend_owner_privileges_toggle_component():
    p = FRONT / "components/OwnerPrivilegesToggle.jsx"
    assert p.exists()
    src = _read(p)
    assert "/ownership/toggle-privileges" in src
    assert "/ownership/status" in src
    assert "owner-privileges-toggle" in src
    assert "if (!isOwner) return null" in src


def test_frontend_force_visitor_banner_component():
    p = FRONT / "components/ForceVisitorBanner.jsx"
    assert p.exists()
    src = _read(p)
    assert "kick_force_visitor_title" in src
    assert "kick_force_visitor_body" in src
    assert "force-visitor-banner" in src


def test_dashboard_mounts_new_components():
    src = _read(FRONT / "pages/Dashboard.js")
    assert "import OwnerPrivilegesToggle" in src
    assert "<OwnerPrivilegesToggle" in src
    assert "import ForceVisitorBanner" in src
    assert "<ForceVisitorBanner" in src


def test_i18n_force_visitor_body_exact_text_fr():
    src = _read(FRONT / "contexts/LanguageContext.js")
    expected = ("Ton historique de discussion ou tes projets sont perçus "
                "comme une menace")
    assert expected in src


def test_i18n_disconnected_body_exact_text_fr():
    src = _read(FRONT / "contexts/LanguageContext.js")
    expected = "Oh oh... on dirait que vous avez un problème de connexion"
    assert expected in src
