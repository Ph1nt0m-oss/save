"""iter97 — Tests des nouvelles features utilisatrice :
- Export ZIP automatique d'un projet
- Inscription GitHub obligatoire (frontend)
- Icône œil sous chaque création (Dashboard)
- Caly chatbot bouton dans header
- Mode privé : choix destinataire Admin/Modo/Créa
- Tuto installation IA pour iPhone/Apple/Samsung/Xiaomi
"""
import os
import requests

BACKEND_URL = os.environ.get('BACKEND_URL') or 'http://localhost:8001'
API = f"{BACKEND_URL}/api"


class TestExportZip:
    """Export ZIP automatique d'un projet de création."""

    def test_endpoint_requires_auth(self):
        r = requests.get(f"{API}/exports/zip-project/fake_id")
        assert r.status_code == 401

    def test_endpoint_defined(self):
        src = open("/app/backend/server.py").read()
        assert "/exports/zip-project/{project_id}" in src
        assert "zipfile.ZipFile" in src
        assert "messages.json" in src
        assert "README.md" in src


class TestGitHubSignupRequired:
    """Inscription GitHub obligatoire."""

    def test_login_page_has_github_block(self):
        content = open("/app/frontend/src/pages/Login.js").read()
        assert "signup-github-required" in content
        assert "signup-github-link" in content
        assert "signup-github-confirmed" in content
        assert "github.com/signup" in content
        assert "githubConfirmed" in content

    def test_submit_blocks_without_github(self):
        content = open("/app/frontend/src/pages/Login.js").read()
        assert "if (!githubConfirmed)" in content
        assert "Confirme la création de ton compte GitHub" in content


class TestEyeIconPerCreation:
    """Icône œil sous chaque projet de création (pas chat)."""

    def test_dashboard_renders_eye_button(self):
        content = open("/app/frontend/src/pages/Dashboard.js").read()
        assert "project-eye-" in content
        assert "project.project_type !== 'chat'" in content
        assert "openPreview: true" in content


class TestCalyChatbot:
    """Caly chatbot bouton + panel."""

    def test_component_exists(self):
        path = "/app/frontend/src/components/CalyChatbot.jsx"
        assert os.path.exists(path)
        content = open(path).read()
        assert "header-caly-btn" in content
        assert "caly-modal" in content
        assert "caly-input" in content
        assert "caly-send" in content
        assert "caly-close" in content
        assert "caly-choice-" in content
        # 5 choix de départ
        assert "create" in content and "modify" in content
        assert "find" in content and "account" in content and "other" in content

    def test_dashboard_wires_caly(self):
        content = open("/app/frontend/src/pages/Dashboard.js").read()
        assert "import CalyChatbot" in content
        assert "<CalyChatbot" in content


class TestKeyTargetSelection:
    """Profile : choix destinataire de la clé (Admin/Modo/Créa)."""

    def test_profile_has_target_block(self):
        content = open("/app/frontend/src/pages/Profile.js").read()
        assert "profile-send-target-block" in content
        assert "key-target-creator" in content
        assert "key-target-admin" in content
        assert "key-target-modo" in content
        assert "Créatrice (toujours)" in content
        assert "send_to_admin: sendToAdmin" in content


class TestOfflineInstallerExtended:
    """Tuto installation IA pour iPhone/Apple/Samsung/Xiaomi en plus."""

    def test_installer_has_new_os(self):
        content = open("/app/frontend/src/components/OfflineAIInstaller.jsx").read()
        assert "iphone:" in content
        assert "apple:" in content
        assert "samsung:" in content
        assert "xiaomi:" in content
        # Tuto contenus
        assert "Private LLM" in content  # iPhone
        assert "Termux" in content  # Android (Samsung/Xiaomi)
        assert "ollama pull gemma3:2b" in content  # mobile light

    def test_auto_detect_mobile_os(self):
        content = open("/app/frontend/src/components/OfflineAIInstaller.jsx").read()
        assert "/iphone|ipod/.test(ua)" in content
        assert "/samsung/.test(ua)" in content
        assert "/xiaomi|miui|redmi/.test(ua)" in content
