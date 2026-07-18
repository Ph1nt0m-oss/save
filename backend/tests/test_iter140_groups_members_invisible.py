"""iter140 — Tests des 3 phases : nouveaux groupes, 6 boutons membre, mode invisible."""
import os
from pathlib import Path

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_codeforge_iter140")

ROOT = Path("/app/backend")
FRONT = Path("/app/frontend/src")


def _read(p):
    return (ROOT / p).read_text(encoding="utf-8")


def _rf(p):
    return (FRONT / p).read_text(encoding="utf-8")


# ============================================================
# Phase 1 — Refonte des tchats de groupe
# ============================================================

class TestPhase1Groups:
    def test_group_types_updated_in_social_routes(self):
        src = _read("routes/social_routes.py")
        # Nouveaux groupes présents.
        for g in ('"users"', '"private_staff"', '"users_staff"', '"users_private"'):
            assert g in src, f"missing {g}"
        # 'public_private' retiré.
        assert '"public_private"' not in src

    def test_group_types_updated_in_server(self):
        src = _read("server.py")
        for g in ('"users"', '"private_staff"', '"users_staff"', '"users_private"'):
            assert g in src, f"missing {g}"
        assert '"public_private"' not in src

    def test_groups_for_device_pending_users(self):
        from routes.social_routes import _groups_for_device
        pending = {"role": "pending", "staff_kind": None}
        out = _groups_for_device(pending)
        # Un utilisateur doit voir : public, users, users_private, users_staff, public_staff
        for g in ("public", "users", "users_private", "users_staff", "public_staff"):
            assert g in out, f"pending should see {g}"

    def test_groups_for_device_private_approved(self):
        from routes.social_routes import _groups_for_device
        approved = {"role": "approved", "staff_kind": None}
        out = _groups_for_device(approved)
        # Un privé voit : public, private, users_private, public_staff, private_staff
        for g in ("public", "private", "users_private", "public_staff", "private_staff"):
            assert g in out, f"approved should see {g}"

    def test_groups_for_device_admin(self):
        from routes.social_routes import _groups_for_device
        admin = {"role": "approved", "staff_kind": "admin"}
        out = _groups_for_device(admin)
        for g in ("staff", "admin", "public_staff", "private_staff", "users_staff"):
            assert g in out, f"admin should see {g}"

    def test_groups_for_device_creator_sees_all(self):
        from routes.social_routes import _groups_for_device, GROUP_TYPES
        creator = {"role": "creator"}
        out = _groups_for_device(creator)
        assert set(out) == set(GROUP_TYPES)

    def test_frontend_group_meta_updated(self):
        src = _rf("components/GroupChatsPanel.jsx")
        for lbl in ("'Utilisateurs'", "'Privé + Staff'", "'Utilisateurs + Staff'", "'Utilisateurs + Privé'"):
            assert lbl in src, f"missing label {lbl}"
        # Public + Privé retiré.
        assert "'Public + Privé'" not in src

    def test_frontend_group_order(self):
        src = _rf("components/GroupChatsPanel.jsx")
        # Ordre : public, private, users, staff, modo, admin, public_staff, private_staff, users_staff, users_private
        idx = src.find("const ORDER")
        assert idx != -1
        block = src[idx:idx + 400]
        expected = ["'public'", "'private'", "'users'", "'staff'", "'modo'", "'admin'",
                    "'public_staff'", "'private_staff'", "'users_staff'", "'users_private'"]
        positions = [block.find(k) for k in expected]
        assert all(p > 0 for p in positions), f"positions={positions}"
        assert positions == sorted(positions)


# ============================================================
# Phase 2 — 6 boutons membre
# ============================================================

class TestPhase2MemberActions:
    def test_router_module_exists(self):
        assert (ROOT / "routes/social_members_routes.py").is_file()

    def test_endpoints_registered(self):
        src = _read("routes/social_members_routes.py")
        for ep in ('"/social/member/action"', '"/social/member/prefs"'):
            assert ep in src, f"missing {ep}"

    def test_action_types_supported(self):
        src = _read("routes/social_members_routes.py")
        for a in ('"mute"', '"unmute"', '"notif_off"', '"notif_on"', '"block"', '"unblock"', '"report"', '"friend_req"'):
            assert a in src, f"missing action {a}"

    def test_hierarchy_blocks_mute_on_superior(self):
        src = _read("routes/social_members_routes.py")
        assert "_tier(target) > _tier(me):" in src
        assert "supérieur hiérarchique" in src

    def test_hierarchy_map_correct(self):
        from routes.social_members_routes import HIERARCHY
        assert HIERARCHY["users"] < HIERARCHY["private"] < HIERARCHY["modo"] < HIERARCHY["admin"] < HIERARCHY["creator"]

    def test_frontend_component_exists(self):
        assert (FRONT / "components/MemberActionsBar.jsx").is_file()

    def test_frontend_has_6_buttons(self):
        src = _rf("components/MemberActionsBar.jsx")
        for tid in ("member-mute-", "member-notif-", "member-block-", "member-report-", "member-friend-", "member-delete-"):
            assert tid in src, f"missing {tid}"

    def test_frontend_disables_mute_on_superior(self):
        src = _rf("components/MemberActionsBar.jsx")
        assert "tierOf(target) <= tierOf(me)" in src

    def test_server_registers_router(self):
        src = _read("server.py")
        assert "build_social_member_router" in src


# ============================================================
# Phase 3 — Mode invisible admin/créa
# ============================================================

class TestPhase3InvisibleMode:
    def test_endpoint_declared(self):
        src = _read("routes/social_members_routes.py")
        assert '"/social/invisible"' in src
        assert '"/social/invisible/state"' in src

    def test_only_admin_and_creator(self):
        src = _read("routes/social_members_routes.py")
        assert "réservé aux admins et à la créa" in src

    def test_creator_forbidden_in_staff(self):
        src = _read("routes/social_members_routes.py")
        assert "créa doit rester visible dans le tchat Staff" in src

    def test_toggle_component_exists(self):
        assert (FRONT / "components/InvisibleModeToggle.jsx").is_file()

    def test_toggle_slider_style(self):
        src = _rf("components/InvisibleModeToggle.jsx")
        # Noir gauche off, jaune #E4FF00 droite on.
        assert "bg-[#E4FF00]" in src
        assert "bg-black" in src
        assert "invisible-toggle-" in src

    def test_toggle_disabled_for_creator_staff(self):
        src = _rf("components/InvisibleModeToggle.jsx")
        assert "staffLock = isCreator && groupType === 'staff'" in src

    def test_mounted_in_group_chats_panel(self):
        src = _rf("components/GroupChatsPanel.jsx")
        assert "InvisibleModeToggle" in src
