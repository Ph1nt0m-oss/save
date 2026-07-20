"""iter150 — UI/UX améliorations Interface & simulation guest.

Tests source-level + unitaires légers.
"""
from pathlib import Path


REPO = Path("/app")
LOGIN = (REPO / "frontend/src/pages/Login.js").read_text()
DASH = (REPO / "frontend/src/pages/Dashboard.js").read_text()
LAUX = (REPO / "frontend/src/components/LoginAuxButtons.jsx").read_text()
BELL_PATH = REPO / "frontend/src/components/MentionsBell.jsx"


# -----------------------------------------------------------
# Task — LoginAuxButtons: 5 vues + label actif reflété
# -----------------------------------------------------------

def test_login_aux_buttons_lists_all_five_views():
    """iter150 — Le picker doit exposer TOUTES les vues (5), pas seulement 2."""
    for view in ('creator', 'user', 'modo', 'admin', 'guest'):
        assert f"key: '{view}'" in LAUX, f"vue {view} manquante"
    # Chaque option a un testid dynamique login-view-opt-<key>
    assert "login-view-opt-${key}" in LAUX


def test_login_aux_buttons_label_reflects_active_view():
    """Quand une vue est sélectionnée, le libellé change."""
    assert 'login-view-picker-label' in LAUX
    # Le composant lit `codeforge_view_mode` en localStorage.
    assert "'codeforge_view_mode'" in LAUX or 'VIEW_MODE_KEY' in LAUX
    # Le libellé actif inclut le short label ("Vue : Utilisateur", etc.).
    assert "`Vue : ${currentMeta.short}`" in LAUX


def test_login_aux_buttons_sets_simulation_unauth_on_visit():
    """Clic « Visite du compte » → marque le device en simulation-unauth."""
    assert 'setSimulationUnauth(true)' in LAUX


def test_login_aux_buttons_integrated_inside_auth_card():
    """iter150/151 — Les boutons sont DANS la carte auth, AU-DESSUS des tabs
    (spec image 1 iter151). LoginAuxButtons apparaît AVANT tab-signup dans
    le source."""
    idx_tabs = LOGIN.find('data-testid="tab-signup"')
    idx_aux = LOGIN.find('<LoginAuxButtons')
    assert idx_tabs > 0 and idx_aux > 0
    assert idx_aux < idx_tabs, "LoginAuxButtons doit être AVANT les tabs (au-dessus, spec iter151)"
    # Pas d'occurrence en dehors du bloc auth.
    assert LOGIN.count('<LoginAuxButtons') == 1


# -----------------------------------------------------------
# Task — Simulation unauth guard
# -----------------------------------------------------------

def test_use_device_identity_exposes_simulation_flag():
    src = (REPO / "frontend/src/hooks/useDeviceIdentity.js").read_text()
    assert 'setSimulationUnauth' in src
    assert 'isSimulationUnauth' in src
    assert 'codeforge_simulation_unauth' in src


def test_dashboard_redirects_when_sim_unauth_and_no_view():
    assert 'isSimulationUnauth' in DASH
    assert "navigate('/login')" in DASH


# -----------------------------------------------------------
# Task — MentionsBell Discord-style
# -----------------------------------------------------------

def test_mentions_bell_component_exists():
    assert BELL_PATH.exists()
    src = BELL_PATH.read_text()
    for k in ('mentions-bell-btn', 'mentions-badge-count', 'mentions-panel-dropdown',
              'mentions-panel-close', 'mentions-mark-all-read', 'mention-item-'):
        assert k in src, f"testid {k} manquant"
    # Discord-style : badge rouge + click → ouvre la conversation.
    assert 'bg-red-500' in src
    assert 'codeforge:open-conversation' in src


def test_dashboard_uses_mentions_bell_in_header_not_floating():
    assert '<MentionsBell' in DASH
    assert 'import MentionsBell' in DASH
    # Plus de widget flottant.
    assert '<MentionNotifier' not in DASH


def test_old_mention_notifier_component_removed():
    assert not (REPO / "frontend/src/components/MentionNotifier.jsx").exists()


# -----------------------------------------------------------
# Task — Compteurs non-lus par conversation
# -----------------------------------------------------------

def test_unread_routes_backend_registered():
    server = (REPO / "backend/server.py").read_text()
    assert 'build_unread_router' in server
    assert 'unread_routes' in server
    p = REPO / "backend/routes/unread_routes.py"
    assert p.exists()
    src = p.read_text()
    assert '/social/unread-counts' in src
    assert '/social/mark-read' in src
    assert 'conversation_read_state' in src


def test_use_unread_counts_hook_exists():
    p = REPO / "frontend/src/hooks/useUnreadCounts.js"
    assert p.exists()
    src = p.read_text()
    assert 'useUnreadCounts' in src
    assert 'UnreadBadge' in src
    assert '/social/unread-counts' in src
    assert '/social/mark-read' in src


def test_group_chats_panel_uses_unread_hook():
    src = (REPO / "frontend/src/components/GroupChatsPanel.jsx").read_text()
    assert 'useUnreadCounts' in src
    assert 'UnreadBadge' in src
    # markRead lors du clic sur un onglet + à l'ouverture du groupe actif.
    assert "unread.markRead('group', g)" in src
    assert "unread.markRead('group', active)" in src


# -----------------------------------------------------------
# Task — Tutoriel interactif : positionnement robuste
# -----------------------------------------------------------

def test_interactive_tutorial_scrolls_target_into_view():
    src = (REPO / "frontend/src/components/InteractiveTutorial.jsx").read_text()
    assert 'scrollTargetIntoView' in src
    # Retry si l'élément n'est pas encore monté (jusqu'à 2s).
    assert 'maxAttempts' in src
    # iter154 — Auto-flip et clamp via l'algorithme tryPlacement.
    assert 'tryPlacement' in src
    assert 'const clamp' in src


# -----------------------------------------------------------
# Regression : previous iter tests still hold key invariants
# -----------------------------------------------------------

def test_iter147_bot_analyzer_two_layers_still_intact():
    from utils import bot_analyzer  # noqa
    assert hasattr(bot_analyzer, 'analyze_message')
    assert hasattr(bot_analyzer, 'analyze_message_combined')


def test_iter149_ai_profile_injector_still_wired():
    server = (REPO / "backend/server.py").read_text()
    assert 'ai_profile_injector' in server
