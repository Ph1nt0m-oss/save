"""iter93 — Tests :
- XAI_API_KEY câblée dans .env (clé fournie utilisatrice)
- LivePreviewPanel : composant + câblage Dashboard
"""
import os


class TestXaiKeyConfigured:
    """XAI_API_KEY présente dans backend/.env."""

    def test_xai_key_in_env(self):
        env = open("/app/backend/.env").read()
        assert "XAI_API_KEY=" in env
        # Pas la clé en dur, juste qu'elle commence par xai-
        for line in env.splitlines():
            if line.startswith("XAI_API_KEY="):
                key = line.split("=", 1)[1].strip()
                assert key.startswith("xai-"), "XAI key must start with 'xai-' prefix"
                assert len(key) > 50, "XAI key looks too short"
                break
        else:
            raise AssertionError("XAI_API_KEY line missing")

    def test_grok_helpers_detect_key(self):
        """Quand XAI_API_KEY est définie (via load_dotenv au boot backend),
        is_xai_available() retourne True."""
        # Lire .env, simuler le chargement
        env = open("/app/backend/.env").read()
        if "XAI_API_KEY=" in env:
            # On vérifie juste que le helper accepte la présence d'une variable
            os.environ.setdefault("XAI_API_KEY", "xai-test-placeholder")
            from grok_integration import is_xai_available
            assert is_xai_available() is True


class TestLivePreviewPanel:
    """Composant Live Preview iframe à la Emergent."""

    def test_component_exists(self):
        path = "/app/frontend/src/components/LivePreviewPanel.jsx"
        assert os.path.exists(path)
        content = open(path).read()
        # Data testids
        assert "live-preview-panel" in content
        assert "live-preview-iframe" in content
        assert "live-preview-reload" in content
        assert "live-preview-close" in content
        assert "live-preview-maximize" in content
        assert "live-preview-open-tab" in content
        assert "live-preview-path" in content
        # Hot reload mention
        assert "Hot reload" in content

    def test_dashboard_wires_live_preview(self):
        content = open("/app/frontend/src/pages/Dashboard.js").read()
        assert "import LivePreviewPanel" in content
        assert "showLivePreview" in content
        assert "header-live-preview-btn" in content
        # Bouton conditionnel sur device.role === 'creator'
        assert "device.role === 'creator'" in content


class TestRegressionIter92:
    """Régression iter92 : translate-name + changelog présents."""

    def test_translate_endpoint(self):
        src = open("/app/backend/server.py").read()
        assert "/projects/translate-name" in src
        assert "codeforge_changelog" in src
        assert "_log_change" in src
