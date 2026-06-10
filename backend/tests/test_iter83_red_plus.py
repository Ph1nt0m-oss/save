"""iter83 — Tests pour les nouvelles features 'rouge++' :
- C11 site_mode multi-checkbox (modes=[...])
- Bug multi-device 'demande fantôme' (auto-expire 90s)
- C7 orchestrateur multi-agents (planner/critic/arbiter)
- /chat/orchestrate endpoints
"""
import os
import requests

BACKEND_URL = os.environ.get('BACKEND_URL') or 'http://localhost:8001'
API = f"{BACKEND_URL}/api"


class TestSiteMode_Multi:
    def test_get_site_mode_returns_modes_list(self):
        r = requests.get(f"{API}/system/site-mode")
        assert r.status_code == 200
        data = r.json()
        assert "mode" in data
        assert "modes" in data
        assert isinstance(data["modes"], list)
        assert len(data["modes"]) >= 1

    def test_put_site_mode_unsigned_rejected(self):
        # Sans signature créatrice → 403/404/422
        r = requests.put(f"{API}/system/site-mode",
                         json={"modes": ["public", "staff"], "key_id": "ghost", "nonce": "n1", "signature": "s"})
        assert r.status_code in (400, 403, 404, 422)

    def test_put_site_mode_invalid_mode_rejected(self):
        r = requests.put(f"{API}/system/site-mode",
                         json={"modes": ["invalid_mode"], "key_id": "ghost", "nonce": "n1", "signature": "s"})
        # 400 (mode invalide) ou 403/404 (signature) selon ordre des gates
        assert r.status_code in (400, 403, 404)

    def test_modes_list_normalization(self):
        """Lecture de code : _normalize_modes + _device_matches_mode existent."""
        import importlib
        srv = importlib.import_module('server')
        src = open(srv.__file__).read()
        assert "_normalize_modes" in src
        assert "_device_matches_mode" in src
        # Les 7 modes valides présents
        assert '"public"' in src
        assert '"staff"' in src
        assert '"admin"' in src
        assert '"modo"' in src


class TestSessionPendingAutoExpire:
    def test_endpoint_exists(self):
        r = requests.get(f"{API}/auth/session-pending")
        # Sans cookie/token : 401
        assert r.status_code in (401, 403)

    def test_stale_threshold_90s_documented(self):
        import importlib
        srv = importlib.import_module('server')
        src = open(srv.__file__).read()
        assert "stale_threshold" in src
        # Auto-expire pending → expired
        assert '"status": "expired"' in src
        assert "iter83" in src and "fantôme" in src


class TestChatOrchestrate:
    def test_endpoint_exists_requires_auth(self):
        r = requests.post(f"{API}/chat/orchestrate",
                          json={"message": "Bonjour", "language": "fr"}, timeout=5)
        # Sans auth : 401
        assert r.status_code in (401, 422)

    def test_stream_endpoint_exists(self):
        r = requests.post(f"{API}/chat/orchestrate-stream",
                          json={"message": "Bonjour"}, timeout=5)
        assert r.status_code in (401, 422)

    def test_orchestrator_module_imports(self):
        from orchestrator import orchestrate, orchestrate_stream, _execute_python, _safe_json
        assert callable(orchestrate)
        assert callable(orchestrate_stream)
        # Sanity on safe_json
        assert _safe_json('{"a": 1}') == {"a": 1}
        assert _safe_json('garbage') == {}
        assert _safe_json('```json\n{"x": 2}\n```') == {"x": 2}

    def test_execute_python_sandbox(self):
        from orchestrator import _execute_python
        # Code basique
        r = _execute_python("print(2+2)", timeout=4)
        assert r.get("ok") is True
        assert "4" in r.get("stdout", "")
        # Code banni
        r2 = _execute_python("import os; os.system('echo x')", timeout=4)
        assert r2.get("ok") is False
        # Timeout
        r3 = _execute_python("import time; time.sleep(10)", timeout=1)
        assert r3.get("ok") is False


class TestRegressionNoBreak:
    def test_site_mode_legacy_str_still_works(self):
        """Old client envoyant `mode: "public"` doit encore marcher."""
        r = requests.put(f"{API}/system/site-mode",
                         json={"mode": "public", "key_id": "ghost", "nonce": "n1", "signature": "s"})
        # 403/404 attendu sur signature mais pas 422 (validation pydantic OK)
        assert r.status_code in (400, 403, 404)
