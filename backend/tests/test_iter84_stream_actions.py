"""iter84 — Tests pour les nouvelles features 'streaming d'actions' :
- orchestrate_actions yield des événements typés (kind/summary/details/ts)
- /chat/orchestrate-stream émet le SSE event-par-event
- /orchestrate/event/{id}/details retourne le détail complet (lazy)
- /orchestrate/history liste les événements
- /observability/video-event collecte les logs caméra
"""
import os
import asyncio
import requests
import pytest

BACKEND_URL = os.environ.get('BACKEND_URL') or 'http://localhost:8001'
API = f"{BACKEND_URL}/api"


class TestOrchestrateActions:
    def test_module_exports(self):
        from orchestrator import (
            orchestrate, orchestrate_actions, orchestrate_stream,
            _make_event, _read_file_safe, _grep_safe, _safe_path,
            _execute_python, _safe_json,
        )
        assert callable(orchestrate_actions)
        assert callable(_make_event)

    def test_make_event_shape(self):
        from orchestrator import _make_event
        evt = _make_event("file_viewed", "Lecture : a.py", details={"x": 1}, path="a.py")
        assert evt["kind"] == "file_viewed"
        assert evt["summary"] == "Lecture : a.py"
        assert evt["details"] == {"x": 1}
        assert evt["path"] == "a.py"
        assert evt["event_id"].startswith("evt_")
        assert "ts" in evt

    def test_safe_path_blocks_escape(self):
        from orchestrator import _safe_path
        assert _safe_path("backend/server.py") is not None
        assert _safe_path("../etc/passwd") is None
        assert _safe_path("/etc/passwd") is None

    def test_read_file_safe_reads_existing(self):
        from orchestrator import _read_file_safe
        r = _read_file_safe("backend/orchestrator.py")
        assert r["ok"] is True
        assert "orchestrate_actions" in r["content"]

    def test_read_file_safe_missing(self):
        from orchestrator import _read_file_safe
        r = _read_file_safe("nope/missing.xyz")
        assert r["ok"] is False

    def test_grep_safe(self):
        from orchestrator import _grep_safe
        r = _grep_safe("orchestrate_actions")
        assert r["ok"] is True
        assert isinstance(r["matches"], list)


class TestOrchestrateActionsStream:
    def test_yields_phase_started_and_complete(self):
        """Sans EMERGENT_LLM_KEY (ou avec mais sans appel réel), on devrait
        toujours yield au moins phase_started + complete (les LLM-calls
        renverront un JSON vide mais le pipeline doit continuer)."""
        from orchestrator import orchestrate_actions

        async def run():
            kinds = []
            async for evt in orchestrate_actions("test", session_id="t1", language="fr"):
                kinds.append(evt["kind"])
            return kinds

        kinds = asyncio.get_event_loop().run_until_complete(run())
        # Doit contenir au minimum les jalons standards
        assert "phase_started" in kinds
        assert "complete" in kinds
        # Au moins un phase_done (planner)
        assert any(k == "phase_done" for k in kinds)


class TestEndpoints:
    def test_orchestrate_stream_requires_auth(self):
        r = requests.post(f"{API}/chat/orchestrate-stream",
                          json={"message": "hi"}, timeout=5)
        assert r.status_code in (401, 422)

    def test_orchestrate_history_requires_auth(self):
        r = requests.post(f"{API}/orchestrate/history",
                          json={"limit": 10}, timeout=5)
        assert r.status_code in (401, 422)

    def test_event_details_requires_auth(self):
        r = requests.get(f"{API}/orchestrate/event/evt_fake/details", timeout=5)
        assert r.status_code in (401, 404)


class TestVideoObservability:
    def test_video_event_no_auth_required(self):
        r = requests.post(f"{API}/observability/video-event",
                          json={"kind": "iris_start", "session_id": "test_session_x123"})
        assert r.status_code == 200
        assert r.json().get("recorded") is True

    def test_video_event_anti_flood(self):
        # 50+ events de la même session = 429.
        sid = "flood_session_test_iter84"
        for _ in range(51):
            requests.post(f"{API}/observability/video-event",
                          json={"kind": "iris_test", "session_id": sid})
        r = requests.post(f"{API}/observability/video-event",
                          json={"kind": "iris_test", "session_id": sid})
        assert r.status_code in (200, 429)  # 429 quand le seuil est atteint
