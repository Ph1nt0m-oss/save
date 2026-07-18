"""iter142 — Tests source-level pour les changements Batch 1+2 :
 - Matrice groupes : Admin ne voit plus 'modo', Invité voit 'public_staff'
 - /groups/messages : bloque l'historique pour guests sur public_staff
 - /devices/list : enrichit avec public_handle
 - /accounts/list : simplified affichage (email/type retirés du frontend)
 - PreviewMenuButton présent
"""
import sys
import inspect
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))


def test_admin_does_not_see_modo_group():
    from backend.routes.social_routes import _groups_for_device
    dev = {"role": "approved", "staff_kind": "admin"}
    got = set(_groups_for_device(dev))
    assert "modo" not in got, f"Admin ne doit PAS voir 'modo' : {got}"
    assert "staff" in got and "admin" in got  # sanity


def test_guest_sees_public_staff():
    from backend.routes.social_routes import _groups_for_device
    got = set(_groups_for_device({"role": "guest"}))
    assert got == {"public", "public_staff"}


def test_creator_sim_admin_no_modo():
    from backend.routes.social_routes import _groups_for_device
    got = set(_groups_for_device({"role": "creator"}, view_mode="admin"))
    assert "modo" not in got
    assert "admin" in got and "staff" in got


def test_creator_sim_guest_sees_public_staff():
    from backend.routes.social_routes import _groups_for_device
    got = set(_groups_for_device({"role": "creator"}, view_mode="guest"))
    assert got == {"public", "public_staff"}


def test_messages_endpoint_blocks_history_for_guest_on_public_staff():
    from backend.routes import social_routes
    src = inspect.getsource(social_routes.build_groups_router)
    assert 'is_guest_effective' in src
    assert '"public_staff"' in src
    assert '"messages": []' in src


def test_devices_list_enriches_public_handle():
    from backend.routes import devices_routes
    src = inspect.getsource(devices_routes.build_devices_router)
    assert 'public_handle' in src
    assert 'db.users.find' in src


def test_preview_menu_component_exists():
    p = Path("/app/frontend/src/components/PreviewMenuButton.jsx")
    assert p.exists()
    content = p.read_text()
    assert 'preview-menu-btn' in content
    assert 'setStoredViewMode' in content
    assert 'Visite du menu' in content


def test_landing_uses_preview_menu():
    p = Path("/app/frontend/src/pages/Landing.js")
    content = p.read_text()
    assert 'PreviewMenuButton' in content


def test_login_removes_creator_toolbar():
    p = Path("/app/frontend/src/pages/Login.js")
    content = p.read_text()
    # CreatorToolbar import removed
    assert "import CreatorToolbar" not in content
    # PreviewMenuButton présent
    assert "PreviewMenuButton" in content


def test_creator_toolbar_hides_in_simulation():
    p = Path("/app/frontend/src/components/CreatorToolbar.jsx")
    content = p.read_text()
    # Vérifie que showSiteModeBadge est conditionné par !viewMode ou viewMode==='creator'
    assert "device.viewMode" in content
    assert "!device.viewMode" in content or "viewMode || device.viewMode === 'creator'" in content


def test_accounts_button_shows_only_pseudo_and_handle():
    p = Path("/app/frontend/src/components/AccountsButton.jsx")
    content = p.read_text()
    # Doit contenir la nouvelle balise handle
    assert 'acc-handle-' in content
    assert 'Identifiant unique' in content
    # Doit avoir retiré les anciennes lignes email + Type + Clé
    assert 'acc-email-' not in content
    assert 'acc-device-' not in content
    assert 'acc-key-' not in content


def test_device_manager_removed_last_seen_and_shows_handle():
    p = Path("/app/frontend/src/components/DeviceManager.jsx")
    content = p.read_text()
    assert 'device-handle-' in content
    # dm_never_seen n'est plus affiché
    assert "t('dm_never_seen')" not in content


def test_toasts_removed_in_toggles():
    """iter142 — Suppression des toasts sur les actions de routine
    (mode invisible, anonyme, sun/night). Les toasts d'erreur restent."""
    for f in [
        "/app/frontend/src/components/InvisibleModeToggle.jsx",
        "/app/frontend/src/components/AnonymousModeToggle.jsx",
        "/app/frontend/src/components/SunNightModeToggle.jsx",
    ]:
        content = Path(f).read_text()
        assert "toast.success" not in content, f"toast.success présent dans {f}"


def test_member_actions_bar_has_confirm_for_destructive():
    p = Path("/app/frontend/src/components/MemberActionsBar.jsx")
    content = p.read_text()
    assert "isDestructive" in content
    assert "window.confirm" in content
    # Plus de toast.success routine
    assert "toast.success" not in content


def test_group_chat_panel_silent_on_403():
    p = Path("/app/frontend/src/components/GroupChatsPanel.jsx")
    content = p.read_text()
    # Vérifie que le catch de loadMessages ignore les 403
    assert "status !== 403" in content
