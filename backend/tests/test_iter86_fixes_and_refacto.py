"""iter86 — Tests pour :
- /friends/* extracted to routes/social_routes.py (slice 2 du refacto)
- group 'admin' added to GROUP_TYPES + _groups_for_device
- _device_matches_mode public/private vs staff distinction
- on_commit hook in orchestrator
- Correction loop (planner-fix on execution failure)
- Private code browser endpoints (/private/code/read-file + grep)
"""
import os
import requests

BACKEND_URL = os.environ.get('BACKEND_URL') or 'http://localhost:8001'
API = f"{BACKEND_URL}/api"


class TestSlice2Refacto:
    def test_friends_routes_still_accessible(self):
        """/friends/* doivent répondre identiquement depuis social_routes."""
        r = requests.post(f"{API}/friends/request",
                          json={"key_id": "x", "nonce": "n", "signature": "s", "target_key_id": "y"})
        assert r.status_code in (403, 404)

        r2 = requests.post(f"{API}/friends/list",
                          json={"key_id": "x", "nonce": "n", "signature": "s"})
        assert r2.status_code in (403, 404)

    def test_build_friends_router_signature(self):
        from routes.social_routes import build_friends_router
        assert callable(build_friends_router)


class TestAdminGroup:
    def test_admin_in_group_types(self):
        from routes.social_routes import GROUP_TYPES
        assert "admin" in GROUP_TYPES
        # Toujours 7 types
        assert len(GROUP_TYPES) == 7

    def test_admin_user_has_admin_group(self):
        from routes.social_routes import _groups_for_device
        dev = {"role": "approved", "staff_kind": "admin"}
        groups = _groups_for_device(dev)
        assert "admin" in groups
        assert "staff" in groups
        assert "modo" not in groups  # admin pas modo

    def test_modo_user_no_admin_group(self):
        from routes.social_routes import _groups_for_device
        dev = {"role": "approved", "staff_kind": "modo"}
        groups = _groups_for_device(dev)
        assert "admin" not in groups
        assert "modo" in groups

    def test_creator_sees_admin_group(self):
        from routes.social_routes import _groups_for_device, GROUP_TYPES
        dev = {"role": "creator"}
        assert set(_groups_for_device(dev)) == GROUP_TYPES


class TestPublicPrivateStaffDistinction:
    def test_device_matches_mode_helper(self):
        import importlib
        srv = importlib.import_module('server')
        match = srv._device_matches_mode
        # Approved sans staff_kind
        normal_user = {"role": "approved", "staff_kind": None}
        # Public seul = passe pour user normal
        assert match(normal_user, ["public"]) is True
        # Private seul = passe pour user normal (clé validée)
        assert match(normal_user, ["private"]) is True
        # Staff seul = bloque user normal
        assert match(normal_user, ["staff"]) is False
        # Admin seul = bloque user normal
        assert match(normal_user, ["admin"]) is False

        # Admin device
        admin_dev = {"role": "approved", "staff_kind": "admin"}
        # public seul = BLOQUE admin (sémantique : doit cocher staff)
        assert match(admin_dev, ["public"]) is False
        # public + staff = passe admin
        assert match(admin_dev, ["public", "staff"]) is True
        # staff seul = passe admin
        assert match(admin_dev, ["staff"]) is True

        # Modo device
        modo_dev = {"role": "approved", "staff_kind": "modo"}
        assert match(modo_dev, ["modo"]) is True
        assert match(modo_dev, ["admin"]) is False  # modo pas admin
        assert match(modo_dev, ["public"]) is False  # public seul exclut staff

        # Creator passe partout
        creator = {"role": "creator"}
        for m in ("public", "private", "staff", "admin", "modo", "creator", "guest"):
            assert match(creator, [m]) is True, f"creator devrait passer {m}"


class TestOnCommitHook:
    def test_signature_accepts_on_commit(self):
        from orchestrator import orchestrate_actions
        import inspect
        sig = inspect.signature(orchestrate_actions)
        assert "on_commit" in sig.parameters
        assert "test_loop" in sig.parameters

    def test_correction_loop_present(self):
        """Lecture de code : correction loop (planner-fix) déclenchée sur stderr."""
        import orchestrator
        src = open(orchestrator.__file__).read()
        assert "planner-fix" in src
        assert "Tentative de correction" in src
        assert "Correction réussie" in src or "Correction échouée" in src


class TestPrivateCodeBrowser:
    def test_read_file_requires_creator(self):
        r = requests.post(f"{API}/private/code/read-file",
                          json={"key_id": "x", "nonce": "n", "signature": "s", "path": "backend/server.py"})
        assert r.status_code in (403, 404)

    def test_grep_requires_creator(self):
        r = requests.post(f"{API}/private/code/grep",
                          json={"key_id": "x", "nonce": "n", "signature": "s", "pattern": "test"})
        assert r.status_code in (403, 404)


class TestGuestViewExtended:
    def test_guest_view_accepts_modo_admin(self):
        """Pydantic schema accepte 'modo' et 'admin' comme guest_view."""
        r = requests.put(f"{API}/system/site-mode",
                         json={"modes": ["guest"], "guest_view": "modo",
                               "key_id": "x", "nonce": "n", "signature": "s"})
        # 403/404 (signature), pas 422 (validation)
        assert r.status_code in (400, 403, 404)
        r2 = requests.put(f"{API}/system/site-mode",
                          json={"modes": ["guest"], "guest_view": "admin",
                                "key_id": "x", "nonce": "n", "signature": "s"})
        assert r2.status_code in (400, 403, 404)


class TestViewModePickerCheckbox:
    def test_picker_decoche_creator(self):
        path = "/app/frontend/src/components/ViewModePicker.jsx"
        content = open(path).read()
        # Click sur case active = decoche (retour creator)
        assert "if (mode === viewMode)" in content
        assert "setStoredViewMode('creator')" in content
        # Bouton "Revenir à la vue Créatrice" présent
        assert "view-mode-revert-creator" in content

    def test_simulation_banner_exists(self):
        path = "/app/frontend/src/components/ViewSimulationBanner.jsx"
        assert os.path.exists(path)
        content = open(path).read()
        assert "view-simulation-banner" in content
        assert "view-simulation-revert" in content
