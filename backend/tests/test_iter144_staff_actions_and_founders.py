"""iter144 — Tests source-level pour :
 - founder_guard : is_founder, register_current_creators_as_founders, assert_not_founder
 - staff_actions_routes : matrice permissions modo/admin/créa + endpoints
 - Renommages global + local + creator-view
 - StaffActionsIconBar présent avec 12 icônes
 - AIProgramming responsive (sidebar toggle mobile)
 - devices/list retourne is_founder
"""
import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))


def test_founder_guard_present():
    from backend.utils import founder_guard
    assert hasattr(founder_guard, 'is_founder')
    assert hasattr(founder_guard, 'register_current_creators_as_founders')
    assert hasattr(founder_guard, 'assert_not_founder')
    assert hasattr(founder_guard, 'get_founder_key_ids')


def test_founder_guard_not_founder_by_default():
    from backend.utils import founder_guard
    # None/absent → jamais fondateur.
    assert founder_guard.is_founder(None) is False
    assert founder_guard.is_founder("") is False


def test_founder_guard_assert_raises():
    import pytest
    from fastapi import HTTPException
    from backend.utils import founder_guard
    # Injecte temporairement une clé.
    original = founder_guard._load_from_file
    founder_guard._load_from_file = lambda: {"key_test_founder"}
    try:
        with pytest.raises(HTTPException) as exc:
            founder_guard.assert_not_founder("key_test_founder", "test")
        assert exc.value.status_code == 403
    finally:
        founder_guard._load_from_file = original


def test_staff_actions_router_defined():
    from backend.routes import staff_actions_routes
    src = inspect.getsource(staff_actions_routes.build_staff_actions_router)
    for ep in ('/staff/action', '/staff/rename-global',
               '/rename/local/set', '/rename/local/list',
               '/rename/local/list-on-target'):
        assert ep in src, f"endpoint {ep} manquant"


def test_permission_matrix_modo():
    from backend.routes.staff_actions_routes import _permission_matrix
    assert _permission_matrix("approved", "modo", "mute") is True
    assert _permission_matrix("approved", "modo", "block") is True
    assert _permission_matrix("approved", "modo", "exclude") is True
    assert _permission_matrix("approved", "modo", "ban") is False
    assert _permission_matrix("approved", "modo", "rename_global") is False


def test_permission_matrix_admin():
    from backend.routes.staff_actions_routes import _permission_matrix
    assert _permission_matrix("approved", "admin", "ban") is True
    assert _permission_matrix("approved", "admin", "rename_global") is True
    assert _permission_matrix("approved", "admin", "promote_modo") is True
    assert _permission_matrix("approved", "admin", "promote_admin") is True
    # Admin ne peut PAS promouvoir créa.
    assert _permission_matrix("approved", "admin", "promote_creator") is False


def test_permission_matrix_creator_all():
    from backend.routes.staff_actions_routes import _permission_matrix
    for a in ("mute", "block", "exclude", "force_visitor", "disconnect",
              "ban", "rename_global", "promote_modo", "promote_admin",
              "promote_creator", "demote"):
        assert _permission_matrix("creator", None, a) is True, f"créa refusée sur {a}"


def test_default_durations():
    from backend.routes.staff_actions_routes import DEFAULT_DURATIONS
    assert DEFAULT_DURATIONS["exclude"] > 0
    assert DEFAULT_DURATIONS["force_visitor"] > 0
    assert DEFAULT_DURATIONS["disconnect"] > 0


def test_staff_action_founder_guard_used():
    from backend.routes import staff_actions_routes
    src = inspect.getsource(staff_actions_routes.build_staff_actions_router)
    assert 'is_founder' in src
    assert 'assert_not_founder' in src or 'Créa fondatrice' in src


def test_rename_local_creator_view_endpoint():
    from backend.routes import staff_actions_routes
    src = inspect.getsource(staff_actions_routes.build_staff_actions_router)
    # Créa doit voir tous les alias locaux + pseudo officiel.
    assert 'list-on-target' in src
    assert 'official_pseudo' in src


def test_staff_actions_icon_bar_component_exists():
    p = Path("/app/frontend/src/components/StaffActionsIconBar.jsx")
    assert p.exists()
    content = p.read_text()
    # 12 icônes exactes.
    icon_keys = [
        'visit', 'rename_global', 'promote_modo', 'promote_admin',
        'promote_creator', 'mute', 'block', 'exclude',
        'force_visitor', 'disconnect', 'ban', 'delete',
    ]
    for k in icon_keys:
        assert f"'{k}'" in content or f'"{k}"' in content, f"icon '{k}' manquante"
    # data-testids stables.
    assert 'staff-action-' in content
    assert 'staff-icon-bar-' in content


def test_founder_icon_locked():
    content = Path("/app/frontend/src/components/StaffActionsIconBar.jsx").read_text()
    assert 'targetIsFounder' in content
    assert 'Lock' in content
    assert 'Créa fondatrice' in content


def test_ai_programming_responsive_sidebar():
    content = Path("/app/frontend/src/pages/AIProgramming.js").read_text()
    assert 'ai-prog-sidebar-toggle' in content
    assert 'sidebarOpen' in content
    # Classes responsive présentes.
    assert 'lg:hidden' in content
    assert 'lg:static' in content
    assert 'translate-x' in content


def test_devices_list_marks_founders():
    content = Path("/app/backend/routes/devices_routes.py").read_text()
    assert 'is_founder' in content
    assert 'get_founder_key_ids' in content


def test_founder_guard_registered_on_boot():
    content = Path("/app/backend/server.py").read_text()
    assert 'register_current_creators_as_founders' in content
    assert 'Créas fondatrices figées' in content


def test_staff_actions_router_wired():
    content = Path("/app/backend/server.py").read_text()
    assert 'build_staff_actions_router' in content


def test_staff_action_log_present():
    from backend.routes import staff_actions_routes
    src = inspect.getsource(staff_actions_routes.build_staff_actions_router)
    assert 'staff_actions_log' in src
    # Log inclut actor + target + action.
    assert 'actor_key_id' in src
    assert 'target_key_id' in src
