"""iter141 — Tests source-level pour :
 - Matrice de visibilité des groupes (modo, users, admin, private, guest, créa)
 - Créa simulée : accès via view_mode
 - /groups/members : Créa invisible sauf staff (admins voient toujours)
 - Anonymous + Sun mode endpoints présents
 - public_handle requis + unique dans /auth/register
"""
import sys
import inspect
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))


def test_groups_matrix_modo():
    from backend.routes.social_routes import _groups_for_device
    dev = {"role": "approved", "staff_kind": "modo"}
    got = set(_groups_for_device(dev))
    assert got == {"public", "modo", "public_staff", "private_staff", "users_staff"}, got


def test_groups_matrix_users_pending():
    from backend.routes.social_routes import _groups_for_device
    dev = {"role": "pending"}
    got = set(_groups_for_device(dev))
    assert got == {"public", "users", "users_staff", "users_private"}, got


def test_groups_matrix_admin():
    from backend.routes.social_routes import _groups_for_device
    dev = {"role": "approved", "staff_kind": "admin"}
    got = set(_groups_for_device(dev))
    # iter142 — Admin ne voit PAS 'modo'.
    assert got == {"public", "staff", "admin",
                   "public_staff", "private_staff", "users_staff"}, got


def test_groups_matrix_private_approved():
    from backend.routes.social_routes import _groups_for_device
    dev = {"role": "approved"}
    got = set(_groups_for_device(dev))
    assert got == {"public", "private", "users_private",
                   "public_staff", "private_staff"}, got


def test_groups_matrix_guest():
    from backend.routes.social_routes import _groups_for_device
    dev = {"role": "guest"}
    got = set(_groups_for_device(dev))
    # iter142 — Guest voit aussi 'public_staff' (historique bloqué).
    assert got == {"public", "public_staff"}, got


def test_groups_matrix_creator_all():
    from backend.routes.social_routes import _groups_for_device, GROUP_TYPES
    dev = {"role": "creator"}
    got = set(_groups_for_device(dev))
    assert got == set(GROUP_TYPES), (got, GROUP_TYPES)


def test_groups_matrix_creator_simulated_admin_no_modo():
    from backend.routes.social_routes import _groups_for_device
    dev = {"role": "creator"}
    got = set(_groups_for_device(dev, view_mode="admin"))
    # iter142 — Admin simulé ne voit PAS 'modo'.
    assert got == {"public", "staff", "admin",
                   "public_staff", "private_staff", "users_staff"}, got


def test_groups_matrix_creator_simulated_modo():
    from backend.routes.social_routes import _groups_for_device
    dev = {"role": "creator"}
    got = set(_groups_for_device(dev, view_mode="modo"))
    # Créa qui simule modo doit voir comme un modo.
    assert got == {"public", "modo", "public_staff", "private_staff", "users_staff"}, got


def test_groups_matrix_creator_simulated_user():
    from backend.routes.social_routes import _groups_for_device
    dev = {"role": "creator"}
    got = set(_groups_for_device(dev, view_mode="user"))
    assert got == {"public", "users", "users_staff", "users_private"}, got


def test_groups_matrix_creator_simulated_guest_only_public():
    from backend.routes.social_routes import _groups_for_device
    dev = {"role": "creator"}
    got = set(_groups_for_device(dev, view_mode="guest"))
    # iter142 — Guest simulé voit aussi 'public_staff' (mais historique
    # bloqué au rendu).
    assert got == {"public", "public_staff"}, got


def test_group_members_endpoint_defined():
    from backend.routes import social_routes
    # Le router est construit par build_groups_router — on inspecte la
    # source pour vérifier que /groups/members est bien déclaré.
    src = inspect.getsource(social_routes.build_groups_router)
    assert '/groups/members' in src
    assert 'creator' in src and 'admin' in src  # Règle Créa/Admin présente


def test_anonymous_and_sun_mode_endpoints_defined():
    from backend.routes import social_members_routes
    src = inspect.getsource(social_members_routes.build_social_member_router)
    assert '/social/anonymous' in src
    assert '/social/sun-mode' in src
    assert '/social/modes/state' in src


def test_anonymous_toggle_model_present():
    from backend.routes.social_members_routes import AnonymousToggleIn, SunModeToggleIn
    fields = set(AnonymousToggleIn.model_fields.keys())
    assert {"key_id", "nonce", "signature", "enabled"}.issubset(fields)
    sun_fields = set(SunModeToggleIn.model_fields.keys())
    assert {"key_id", "nonce", "signature", "enabled"}.issubset(sun_fields)


def test_public_handle_required_in_register():
    from backend.server import RegisterRequest
    fields = RegisterRequest.model_fields
    assert 'public_handle' in fields


def test_public_handle_validation_present():
    """Vérifie que la validation du public_handle est bien dans le source
    de /auth/register."""
    import backend.server as srv
    # On regarde la source du fichier plutôt que de la fonction wrapped.
    src = inspect.getsource(srv)
    assert 'public_handle' in src
    # 3-24 caractères + regex.
    assert 'entre 3 et 24' in src
    # Index unique.
    assert 'public_handle_lower' in src


def test_group_send_stores_public_handle():
    from backend.routes import social_routes
    src = inspect.getsource(social_routes.build_groups_router)
    assert 'from_public_handle' in src


def test_view_mode_param_on_groups_endpoints():
    from backend.routes.social_routes import GroupListIn, GroupMessagesIn, GroupSendIn
    assert 'view_mode' in GroupListIn.model_fields
    assert 'view_mode' in GroupMessagesIn.model_fields
    assert 'view_mode' in GroupSendIn.model_fields


def test_creator_invisible_rule_in_members_route():
    from backend.routes import social_routes
    src = inspect.getsource(social_routes.build_groups_router)
    # Règle : créa masquée sauf dans 'staff', mais admins voient toujours.
    assert "role\") == \"creator\"" in src
    assert 'caller_is_admin' in src
    assert '"staff"' in src


def test_anonymous_rendering_in_messages():
    from backend.routes import social_routes
    src = inspect.getsource(social_routes.build_groups_router)
    assert '_render_sender' in src
    assert 'Anonyme' in src
    assert 'sun_mode' in src.lower() or 'sun_mode_active' in src.lower()
