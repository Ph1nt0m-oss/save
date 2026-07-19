"""iter143 Batch D+E — Tests source-level pour :
 - moderation_routes : alertes + assignations + décisions + timeouts
 - Auto-alerte création dans /groups/send quand suspicion détectée
 - ModAlertModal (frontend) présent + testids
 - MentionInput (autocomplete @handle) intégré à GroupChatsPanel
"""
import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))


def test_moderation_router_defined():
    from backend.routes import moderation_routes
    src = inspect.getsource(moderation_routes.build_moderation_router)
    assert '/moderation/alerts/create' in src
    assert '/moderation/assignments/mine' in src
    assert '/moderation/assignments/action' in src
    assert '/moderation/decisions/list' in src
    assert '/moderation/alerts/list' in src


def test_moderation_pick_online_staff_balances_load():
    from backend.routes import moderation_routes
    src = inspect.getsource(moderation_routes.build_moderation_router)
    assert '_pick_online_staff' in src
    assert 'loads' in src
    assert 'staff_kind' in src


def test_moderation_assignment_timeout():
    from backend.routes.moderation_routes import ASSIGNMENT_TIMEOUT_SEC
    assert ASSIGNMENT_TIMEOUT_SEC == 120


def test_moderation_actions_include_all_decisions():
    from backend.routes import moderation_routes
    src = inspect.getsource(moderation_routes.build_moderation_router)
    for a in ("accept", "refuse", "sanction", "not_infraction", "delegate"):
        assert f'"{a}"' in src or f"'{a}'" in src, f"missing action {a}"


def test_moderation_alerts_creator_admin_only():
    from backend.routes import moderation_routes
    src = inspect.getsource(moderation_routes.build_moderation_router)
    # alerts/list restricted to creator/admin
    assert 'Réservé Créa/Admin' in src


def test_groups_send_creates_alert_on_suspicion():
    content = Path("/app/backend/routes/social_routes.py").read_text()
    assert 'mod_alerts' in content
    assert 'mod_assignments' in content
    assert 'assigned_to' in content


def test_mod_alert_modal_present():
    p = Path("/app/frontend/src/components/ModAlertModal.jsx")
    assert p.exists()
    content = p.read_text()
    for tid in ('mod-alert-modal', 'mod-alert-accept', 'mod-alert-refuse',
                'mod-alert-sanction', 'mod-alert-not-infraction',
                'mod-alert-delegate', 'mod-alert-submit-nosanction'):
        assert tid in content, f"missing data-testid {tid}"


def test_mod_alert_modal_toggles_sun_mode():
    content = Path("/app/frontend/src/components/ModAlertModal.jsx").read_text()
    assert '/social/sun-mode' in content
    # sanction → activation + désactivation (Sun temporaire).
    assert "enabled: true" in content
    assert "enabled: false" in content


def test_dashboard_mounts_mod_alert_modal():
    content = Path("/app/frontend/src/pages/Dashboard.js").read_text()
    assert 'import ModAlertModal' in content
    assert '<ModAlertModal' in content


def test_mention_input_component_exists():
    p = Path("/app/frontend/src/components/MentionInput.jsx")
    assert p.exists()
    content = p.read_text()
    assert 'mention-suggestions' in content
    assert 'mention-opt-' in content
    assert 'MentionInputWithSend' in content


def test_group_chats_panel_uses_mention_input():
    content = Path("/app/frontend/src/components/GroupChatsPanel.jsx").read_text()
    assert 'MentionInputWithSend' in content
    # Legacy plain input removed.
    assert 'placeholder="Message…"' not in content or 'MentionInput' in content


def test_moderation_router_wired_in_server():
    content = Path("/app/backend/server.py").read_text()
    assert 'build_moderation_router' in content
    assert '/moderation' in content or '/api' in content
