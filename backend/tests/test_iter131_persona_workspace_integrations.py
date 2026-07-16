"""iter131 — Tests des nouveaux endpoints : workspace, integrations, persona.

Tests source-level uniquement (ne dépendent pas d'un serveur running).
"""
import io
import os
import zipfile
from pathlib import Path

ROOT = Path("/app/backend")


def _read(p):
    return (ROOT / p).read_text(encoding="utf-8")


class TestWorkspaceRouter:
    def test_module_exists(self):
        assert (ROOT / "routes/workspace_routes.py").is_file()

    def test_factory_exposed(self):
        src = _read("routes/workspace_routes.py")
        assert "def build_workspace_router" in src
        assert "@router.get(\"/workspace/list/{project_id}\")" in src
        assert "@router.get(\"/workspace/download/{project_id}\")" in src

    def test_uses_agent_workspace_root(self):
        src = _read("routes/workspace_routes.py")
        assert "from agents.tools import WORKSPACE_ROOT" in src

    def test_zip_response(self):
        src = _read("routes/workspace_routes.py")
        assert "zipfile.ZipFile" in src
        assert "application/zip" in src

    def test_ownership_check(self):
        src = _read("routes/workspace_routes.py")
        assert "db.projects.find_one" in src
        assert "user_id" in src

    def test_registered_in_server(self):
        src = _read("server.py")
        assert "build_workspace_router" in src
        assert "from routes.workspace_routes import build_workspace_router" in src


class TestIntegrationsRouter:
    def test_module_exists(self):
        assert (ROOT / "routes/integrations_routes.py").is_file()

    def test_supported_integrations(self):
        src = _read("routes/integrations_routes.py")
        for iid in ("stripe", "google", "chatgpt"):
            assert f'"{iid}"' in src, f"integration {iid} missing"

    def test_creator_gated(self):
        src = _read("routes/integrations_routes.py")
        # Chaque endpoint doit appeler require_creator_signature
        assert src.count("require_creator_signature") >= 3

    def test_endpoints_registered(self):
        src = _read("routes/integrations_routes.py")
        for path in ("/private/integrations/status", "/private/integrations/save", "/private/integrations/test"):
            assert f'"{path}"' in src

    def test_registered_in_server(self):
        src = _read("server.py")
        assert "build_integrations_router" in src


class TestChatStreamPersonaPersistence:
    def test_persona_metadata_persisted(self):
        src = _read("routes/chat_advanced_routes.py")
        # Le doc utilisateur inclut désormais persona_id/pseudo/avatar/visible.
        assert "persona_id" in src
        assert "persona_pseudo" in src
        assert "persona_avatar" in src
        assert "visible_to_target" in src

    def test_manual_mode_persists_user_message(self):
        src = _read("routes/chat_advanced_routes.py")
        # Quand aiReplies=false, on doit créer un chat_messages.insert_one avant le silent_gen.
        idx_ai_replies_false = src.find("persona_ai_replies is False")
        assert idx_ai_replies_false != -1
        # Le bloc doit contenir un insert_one avec creator_manual=True.
        after = src[idx_ai_replies_false:idx_ai_replies_false + 3000]
        assert "chat_messages.insert_one" in after
        assert '"creator_manual": True' in after

    def test_silent_response_includes_persona(self):
        src = _read("routes/chat_advanced_routes.py")
        assert '"user_message_id"' in src
        assert '"reason": "creator_persona_silence"' in src


class TestAgentRegistryStillMounted:
    def test_route_present(self):
        src = _read("routes/chat_advanced_routes.py")
        assert '"/agents/registry"' in src


class TestFrontendWiring:
    def test_registry_page_exists(self):
        assert Path("/app/frontend/src/pages/PrivateAgentRegistry.js").is_file()

    def test_integrations_page_exists(self):
        assert Path("/app/frontend/src/pages/PrivateIntegrations.js").is_file()

    def test_routes_declared(self):
        src = Path("/app/frontend/src/App.js").read_text(encoding="utf-8")
        assert "/private/agent-registry" in src
        assert "/private/integrations" in src
        assert "PrivateAgentRegistry" in src
        assert "PrivateIntegrations" in src

    def test_dashboard_has_new_tiles(self):
        src = Path("/app/frontend/src/pages/Dashboard.js").read_text(encoding="utf-8")
        assert "creator-agent-registry-btn" in src
        assert "creator-integrations-btn" in src

    def test_chat_has_workspace_download(self):
        src = Path("/app/frontend/src/pages/Chat.js").read_text(encoding="utf-8")
        assert "chat-download-workspace-btn" in src
        assert "/workspace/list/" in src
        assert "/workspace/download/" in src

    def test_chat_persona_badge(self):
        src = Path("/app/frontend/src/pages/Chat.js").read_text(encoding="utf-8")
        assert "msg-persona-badge" in src
        assert "chat-avatar-user-persona" in src


def test_workspace_zip_shape(tmp_path):
    """Vérifie qu'un ZIP construit avec la même stratégie fonctionne (smoke)."""
    base = tmp_path / "proj_test"
    base.mkdir()
    (base / "hello.py").write_text("print('hello forge')\n")
    (base / "sub").mkdir()
    (base / "sub" / "data.txt").write_text("ok\n")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, names in os.walk(str(base)):
            for n in names:
                fp = os.path.join(root, n)
                arcname = os.path.relpath(fp, str(base))
                zf.write(fp, arcname=arcname)
        zf.writestr("README.md", "test")

    buf.seek(0)
    with zipfile.ZipFile(buf) as zf:
        names = sorted(zf.namelist())
    assert "README.md" in names
    assert "hello.py" in names
    assert "sub/data.txt" in names
