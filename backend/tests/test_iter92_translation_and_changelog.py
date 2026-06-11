"""iter92 — Tests :
- Traduction dynamique des noms de tchats (/projects/translate-name)
- Endpoint changelog modifications (/private/changelog + /private/changelog/log)
- Auto-log lors changement site_mode
"""
import os
import requests

BACKEND_URL = os.environ.get('BACKEND_URL') or 'http://localhost:8001'
API = f"{BACKEND_URL}/api"


class TestProjectNameTranslation:
    """Endpoint /projects/translate-name avec cache MongoDB."""

    def test_endpoint_requires_auth(self):
        r = requests.post(f"{API}/projects/translate-name",
                          json={"project_id": "p", "target_lang": "en", "name": "Hello"})
        assert r.status_code == 401

    def test_invalidate_requires_auth(self):
        r = requests.post(f"{API}/projects/invalidate-name-cache?project_id=p")
        assert r.status_code == 401

    def test_endpoint_definition_present(self):
        src = open("/app/backend/server.py").read()
        assert "@api_router.post(\"/projects/translate-name\")" in src
        assert "project_name_translations" in src
        assert "iter92" in src


class TestPrivateChangelog:
    """Endpoint /private/changelog + /private/changelog/log + auto-log site_mode."""

    def test_changelog_requires_creator(self):
        r = requests.post(f"{API}/private/changelog",
                          json={"key_id": "x", "nonce": "n", "signature": "s"})
        assert r.status_code == 403

    def test_changelog_log_requires_creator(self):
        r = requests.post(f"{API}/private/changelog/log",
                          json={"key_id": "x", "nonce": "n", "signature": "s",
                                "category": "manual", "summary": "Test"})
        assert r.status_code == 403

    def test_helper_log_change_defined(self):
        src = open("/app/backend/server.py").read()
        assert "async def _log_change(" in src
        assert "codeforge_changelog" in src

    def test_site_mode_auto_logs(self):
        """set_site_mode doit appeler _log_change avec category='site_mode'."""
        src = open("/app/backend/server.py").read()
        assert "await _log_change(\n            \"site_mode\"" in src or '_log_change("site_mode"' in src


class TestFrontendIntegration:
    """Hook + composant frontend."""

    def test_hook_translated_project_name_exists(self):
        path = "/app/frontend/src/hooks/useTranslatedProjectName.js"
        assert os.path.exists(path)
        content = open(path).read()
        assert "useTranslatedProjectName" in content
        assert "translateProjectNameOnce" in content
        assert "invalidateLocalNameCache" in content
        assert "/projects/translate-name" in content
        assert "codeforge_chat_name_translations" in content

    def test_component_translated_project_name_exists(self):
        path = "/app/frontend/src/components/TranslatedProjectName.jsx"
        assert os.path.exists(path)
        content = open(path).read()
        assert "TranslatedProjectName" in content

    def test_dashboard_uses_translated_component(self):
        content = open("/app/frontend/src/pages/Dashboard.js").read()
        assert "TranslatedProjectName" in content
        assert "<TranslatedProjectName project={project}" in content

    def test_private_programming_has_changelog_panel(self):
        content = open("/app/frontend/src/pages/PrivateProgramming.js").read()
        assert "ChangelogPanel" in content
        assert "changelog-panel" in content
        assert "changelog-add-btn" in content
        assert "changelog-manual-input" in content
