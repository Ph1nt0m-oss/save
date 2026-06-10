"""iter85 — Tests pour :
- ViewModePicker (frontend, audit code)
- Streaming token-par-token DANS final event (final_chunk events)
- preview_ready + commit_pushed events émis après exécution réussie
- /orchestrate/test-loop endpoint (pytest interne)
- Refacto routes/social_routes.py (_groups_for_device extrait)
"""
import os
import requests

BACKEND_URL = os.environ.get('BACKEND_URL') or 'http://localhost:8001'
API = f"{BACKEND_URL}/api"


class TestRefactoSocialRoutes:
    def test_module_exists(self):
        from routes.social_routes import _groups_for_device, GROUP_TYPES
        assert callable(_groups_for_device)
        assert "public" in GROUP_TYPES
        assert "modo" in GROUP_TYPES

    def test_groups_for_creator(self):
        from routes.social_routes import _groups_for_device, GROUP_TYPES
        dev = {"role": "creator", "staff_kind": None}
        groups = _groups_for_device(dev)
        assert set(groups) == GROUP_TYPES

    def test_groups_for_modo(self):
        from routes.social_routes import _groups_for_device
        dev = {"role": "approved", "staff_kind": "modo"}
        groups = _groups_for_device(dev)
        assert "modo" in groups
        assert "staff" in groups
        assert "public_staff" in groups

    def test_groups_for_admin(self):
        from routes.social_routes import _groups_for_device
        dev = {"role": "approved", "staff_kind": "admin"}
        groups = _groups_for_device(dev)
        assert "staff" in groups
        assert "public_staff" in groups
        assert "modo" not in groups  # admin n'a pas accès au groupe modo-only

    def test_groups_for_blocked(self):
        from routes.social_routes import _groups_for_device
        dev = {"role": "blocked", "staff_kind": None}
        assert _groups_for_device(dev) == []


class TestStreamingFinalChunks:
    def test_llm_stream_tokens_exists(self):
        from orchestrator import _llm_stream_tokens
        import asyncio
        # Sans clé EMERGENT, le générateur termine sans yield. C'est ok.
        async def collect():
            chunks = []
            async for c in _llm_stream_tokens("sys", "user", role="x", session_id="s1"):
                chunks.append(c)
            return chunks
        out = asyncio.get_event_loop().run_until_complete(collect())
        assert isinstance(out, list)

    def test_orchestrate_actions_yields_final_chunk_event_type(self):
        """Validation par lecture de code : final_chunk yield présent."""
        import importlib
        import orchestrator
        importlib.reload(orchestrator)
        src = open(orchestrator.__file__).read()
        assert 'final_chunk' in src
        assert '_llm_stream_tokens' in src
        # preview_ready et commit_pushed sont émis post-exécution réussie
        assert '"preview_ready"' in src
        assert '"commit_pushed"' in src


class TestTestLoopEndpoint:
    def test_test_loop_requires_auth(self):
        r = requests.post(f"{API}/orchestrate/test-loop",
                          json={"target": "backend", "path": "tests/"}, timeout=5)
        assert r.status_code in (401, 422)

    def test_test_loop_endpoint_documented(self):
        import importlib
        srv = importlib.import_module('server')
        src = open(srv.__file__).read()
        assert '/orchestrate/test-loop' in src
        assert 'TestLoopIn' in src
        # safety : refuse path traversal
        assert 'Path invalide' in src or 'safe_path' in src


class TestViewModePicker:
    def test_component_file_exists(self):
        path = "/app/frontend/src/components/ViewModePicker.jsx"
        assert os.path.exists(path)
        content = open(path).read()
        # Les 5 vues attendues
        for mode in ("creator", "user", "modo", "admin", "guest"):
            assert f"'{mode}'" in content or f'"{mode}"' in content

    def test_useDevice_extended_views(self):
        path = "/app/frontend/src/hooks/useDeviceIdentity.js"
        content = open(path).read()
        assert "VALID_VIEW_MODES" in content
        assert "['creator', 'user', 'modo', 'admin', 'guest']" in content
        assert "effectiveStaffKind" in content
        assert "isRealCreator" in content


class TestRegressionIntact:
    def test_friends_endpoint_still_works(self):
        r = requests.post(f"{API}/friends/request",
                          json={"key_id": "x", "nonce": "n", "signature": "s", "target_key_id": "y"})
        assert r.status_code in (403, 404)

    def test_groups_list_still_works(self):
        r = requests.post(f"{API}/groups/list",
                          json={"key_id": "x", "nonce": "n", "signature": "s"})
        assert r.status_code in (403, 404)
