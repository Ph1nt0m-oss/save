"""iter88 — Tests pour :
- Bug fix Eye import dans ViewModePicker
- Refacto slice 3 : /groups/* extracted vers routes/social_routes.py
- Preview RÉEL : on_preview hook + enable_preview_rebuild opt-in dans orchestrator
"""
import os
import requests

BACKEND_URL = os.environ.get('BACKEND_URL') or 'http://localhost:8001'
API = f"{BACKEND_URL}/api"


class TestEyeImportFix:
    def test_eye_imported(self):
        content = open("/app/frontend/src/components/ViewModePicker.jsx").read()
        # iter88 — Eye doit être présent dans l'import (fix runtime error)
        assert " Eye," in content or " Eye }" in content


class TestSlice3GroupsRefacto:
    def test_groups_endpoints_still_work(self):
        # /groups/list répond toujours via le router extrait
        r = requests.post(f"{API}/groups/list",
                          json={"key_id": "x", "nonce": "n", "signature": "s"})
        assert r.status_code in (403, 404)

        r2 = requests.post(f"{API}/groups/messages",
                          json={"key_id": "x", "nonce": "n", "signature": "s", "group_type": "public"})
        assert r2.status_code in (403, 404)

        r3 = requests.post(f"{API}/groups/send",
                          json={"key_id": "x", "nonce": "n", "signature": "s",
                                "group_type": "public", "content": "hi"})
        assert r3.status_code in (403, 404)

    def test_build_groups_router_exists(self):
        from routes.social_routes import build_groups_router
        assert callable(build_groups_router)

    def test_groups_routes_removed_from_server(self):
        src = open("/app/backend/server.py").read()
        # Les @api_router.post pour /groups/list etc. ont été retirés
        assert '@api_router.post("/groups/list")' not in src
        assert '@api_router.post("/groups/messages")' not in src
        assert '@api_router.post("/groups/send")' not in src


class TestPreviewRebuild:
    def test_orchestrate_in_has_preview_flag(self):
        src = open("/app/backend/server.py").read()
        assert "enable_preview_rebuild" in src
        # on_preview_real fonction définie
        assert "async def on_preview_real()" in src
        # yarn build call présent
        assert '"yarn", "build"' in src

    def test_orchestrator_accepts_on_preview(self):
        from orchestrator import orchestrate_actions
        import inspect
        sig = inspect.signature(orchestrate_actions)
        assert "on_preview" in sig.parameters

    def test_preview_event_includes_rebuild_result(self):
        src = open("/app/backend/orchestrator.py").read()
        # preview_ready event maintenant inclut le résultat du rebuild
        assert "rebuild_result" in src
        assert "preview_result" in src
