"""iter146 — Sprint 2 (partiel) + câblages : StaffActionsIconBar dans
DeviceManager, mini crayon renommage local dans MessageBubble, filtres
membres par rôle (GroupMembersList), auth flow multi-devices sécurisé.
"""
import inspect
from pathlib import Path


def test_devicemanager_uses_staff_actions_icon_bar():
    content = Path("/app/frontend/src/components/DeviceManager.jsx").read_text()
    assert 'import StaffActionsIconBar' in content
    assert '<StaffActionsIconBar' in content
    # onRename câblé sur /staff/rename-global.
    assert '/staff/rename-global' in content


def test_devicemanager_supports_creator_approval():
    content = Path("/app/frontend/src/components/DeviceManager.jsx").read_text()
    # Créa peut promouvoir directement comme créa via approve-as-creator.
    assert 'creator' in content
    assert 'approve-as-creator' in content or "'creator'" in content


def test_messagebubble_has_local_rename_button():
    content = Path("/app/frontend/src/components/MessageBubble.jsx").read_text()
    assert 'msg-rename-local-' in content
    assert 'msg-rename-input-' in content
    assert 'msg-rename-save-' in content
    # Utilise /rename/local/set + list.
    assert '/rename/local/list' in content
    assert '/rename/local/set' in content


def test_messagebubble_hooks_before_early_return():
    """Vérifie que useState/useEffect sont AVANT `if (!message) return null;`."""
    content = Path("/app/frontend/src/components/MessageBubble.jsx").read_text()
    idx_state = content.find('const [alias, setAlias]')
    idx_return = content.find('if (!message) return null;')
    assert idx_state > 0 and idx_return > 0
    assert idx_state < idx_return, "Hooks doivent être appelés avant early return"


def test_group_members_list_component_exists():
    p = Path("/app/frontend/src/components/GroupMembersList.jsx")
    assert p.exists()
    content = p.read_text()
    for tid in ('gm-filter-${k}', 'gm-member-', 'group-members-panel'):
        assert tid in content, f"testid {tid} manquant"
    # Les 4 clés de filtre présentes dans l'array FILTERS.
    for k in ('all', 'staff', 'friends', 'anon'):
        assert f"k: '{k}'" in content or f'k: "{k}"' in content, f"filter {k} manquant"


def test_group_chats_panel_mounts_members_list():
    content = Path("/app/frontend/src/components/GroupChatsPanel.jsx").read_text()
    assert 'import GroupMembersList' in content
    assert '<GroupMembersList' in content


def test_auth_session_pending_filters_requesting_device():
    """Le nouveau code exclut les requêtes dont requesting_key_id est le
    device actuellement authentifié (première connexion)."""
    from backend.routes import auth_pwreset_session_routes
    src = inspect.getsource(auth_pwreset_session_routes)
    assert 'requesting_key_id' in src
    assert 'active_dev' in src
    # Filtre appliqué sur les rows retournées.
    assert 'r.get("requesting_key_id") != active_dev' in src \
        or "requesting_key_id') != active_dev" in src


def test_msgbubble_shows_alias_indicator():
    content = Path("/app/frontend/src/components/MessageBubble.jsx").read_text()
    # Petit indicateur "(alias)" quand un alias est actif.
    assert '(alias)' in content
    # Tooltip avec le pseudo officiel quand alias actif.
    assert 'Pseudo officiel' in content


def test_group_members_list_shows_role_icons():
    content = Path("/app/frontend/src/components/GroupMembersList.jsx").read_text()
    for icon in ('Crown', 'Shield', 'ShieldCheck', 'EyeOff', 'Heart'):
        assert icon in content, f"icon {icon} manquant"
