"""iter131 — Live end-to-end tests against the running backend.

Validates:
  - 6 new endpoints are registered & require auth/signature
  - GET /api/agents/registry returns 13 agents with expected fields
  - GET /api/workspace/list/{unknown_pid} returns 404 "Projet introuvable."
  - persona_override is IGNORED for non-creator users (no persona_* on user msg)
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://no-code-builder-25.preview.emergentagent.com").rstrip("/")
EMAIL = "test_dash_1777658375@gmail.com"
PASSWORD = "Pass1234"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=15)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text[:200]}"
    tok = r.json().get("session_token")
    assert tok, "No session_token in login response"
    return tok


@pytest.fixture(scope="module")
def auth_headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# --- Section 1 : unauthenticated access ---
class TestUnauthenticatedAccess:
    def test_agents_registry_401(self):
        r = requests.get(f"{BASE_URL}/api/agents/registry", timeout=10)
        assert r.status_code == 401

    def test_workspace_list_401(self):
        r = requests.get(f"{BASE_URL}/api/workspace/list/proj_x", timeout=10)
        assert r.status_code == 401

    def test_workspace_download_401(self):
        r = requests.get(f"{BASE_URL}/api/workspace/download/proj_x", timeout=10)
        assert r.status_code == 401

    def test_integrations_status_403(self):
        r = requests.post(f"{BASE_URL}/api/private/integrations/status",
                          json={"key_id": "x", "nonce": "x", "signature": "x"}, timeout=10)
        assert r.status_code == 403

    def test_integrations_save_403(self):
        r = requests.post(f"{BASE_URL}/api/private/integrations/save",
                          json={"key_id": "x", "nonce": "x", "signature": "x",
                                "integration_id": "stripe", "values": {}}, timeout=10)
        assert r.status_code == 403

    def test_integrations_test_403(self):
        r = requests.post(f"{BASE_URL}/api/private/integrations/test",
                          json={"key_id": "x", "nonce": "x", "signature": "x",
                                "integration_id": "stripe"}, timeout=10)
        assert r.status_code == 403


# --- Section 2 : /agents/registry authenticated ---
class TestAgentsRegistry:
    REQUIRED_FIELDS = {"id", "name", "objectif", "expertise", "raisonnement", "format", "outils", "limites", "module"}

    def test_registry_returns_13_agents(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/agents/registry", headers=auth_headers, timeout=10)
        assert r.status_code == 200
        data = r.json()
        agents = data if isinstance(data, list) else data.get("agents", [])
        assert isinstance(agents, list)
        assert len(agents) == 13, f"expected 13 agents, got {len(agents)}"

    def test_registry_agent_fields(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/agents/registry", headers=auth_headers, timeout=10)
        agents = r.json() if isinstance(r.json(), list) else r.json().get("agents", [])
        for a in agents:
            missing = self.REQUIRED_FIELDS - set(a.keys())
            assert not missing, f"agent {a.get('id')} missing fields {missing}"


# --- Section 3 : /workspace/list on non-owned project ---
class TestWorkspaceOwnership:
    def test_list_unknown_project_returns_404(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/workspace/list/proj_never_existed_zzz",
                         headers=auth_headers, timeout=10)
        assert r.status_code == 404
        assert "introuvable" in r.text.lower()

    def test_download_unknown_project_returns_404(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/workspace/download/proj_never_existed_zzz",
                         headers=auth_headers, timeout=10)
        assert r.status_code == 404


# --- Section 4 : persona_override IGNORED for non-creator ---
class TestPersonaIgnoredForNonCreator:
    @pytest.fixture(scope="class")
    def project_id(self, auth_headers):
        r = requests.post(f"{BASE_URL}/api/projects", headers=auth_headers,
                          json={"name": "TEST_iter131_persona_live", "description": "persona ignore"},
                          timeout=15)
        assert r.status_code in (200, 201)
        pid = r.json().get("project_id") or r.json().get("id")
        assert pid
        return pid

    def test_chat_stream_ignores_persona_override(self, auth_headers, project_id):
        payload = {
            "project_id": project_id,
            "message": "Bonjour, comment vas-tu ?",
            "persona_override": {
                "id": "creator",
                "customPseudo": "Alice",
                "customAvatar": "https://example.com/a.png",
                "aiReplies": True,
                "visible": True,
            },
        }
        r = requests.post(f"{BASE_URL}/api/chat/stream", headers=auth_headers, json=payload,
                          timeout=30, stream=True)
        assert r.status_code == 200
        # Consume the SSE
        body = b""
        for chunk in r.iter_content(chunk_size=1024):
            body += chunk
            if b'"done": true' in body:
                break
        assert b'"done": true' in body

    def test_no_persona_metadata_on_user_msg(self, auth_headers, project_id):
        # Wait for insert flush
        import time
        time.sleep(1)
        r = requests.get(f"{BASE_URL}/api/chat/history",
                         params={"project_id": project_id},
                         headers=auth_headers, timeout=15)
        assert r.status_code == 200
        data = r.json()
        msgs = data.get("messages") if isinstance(data, dict) else data
        assert msgs, "no messages in history"
        user_msgs = [m for m in msgs if m.get("role") == "user"]
        assert user_msgs, "no user message found"
        for m in user_msgs:
            assert not m.get("persona_id"), f"persona_id leaked: {m.get('persona_id')}"
            assert not m.get("persona_pseudo"), f"persona_pseudo leaked: {m.get('persona_pseudo')}"
            assert not m.get("persona_avatar"), f"persona_avatar leaked: {m.get('persona_avatar')}"
