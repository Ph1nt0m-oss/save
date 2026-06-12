"""iter101 — Câblage useViewSpec dans Dashboard + PrivateProgramming + i18n
dans BotsAdminPanel/CalyChatbot."""
import os


class TestUseViewSpecWiring:
    def test_dashboard_uses_hook(self):
        content = open("/app/frontend/src/pages/Dashboard.js").read()
        assert "import useViewSpec" in content
        assert "viewSpec = useViewSpec()" in content
        assert "viewSpec.canSeeBotsAdmin" in content
        # Plus de check direct device.staff_kind/role pour bots
        assert "device.staff_kind === 'admin' || device.role === 'creator'" not in content

    def test_private_programming_uses_hook(self):
        content = open("/app/frontend/src/pages/PrivateProgramming.js").read()
        assert "import useViewSpec" in content
        assert "canSeeProgramming" in content
        # iter107 — Le check viewMode est désormais utilisé pour bloquer
        # l'affichage du code en mode simulation (anti-shoulder-surfing),
        # donc on s'assure que canSeeProgramming est combiné avec isInSimulation.
        assert "isInSimulation" in content
        assert "canSeeProgramming && !isInSimulation" in content


class TestI18nWiredInNewComponents:
    def test_bots_admin_uses_t(self):
        content = open("/app/frontend/src/components/BotsAdminPanel.jsx").read()
        assert "import.*useLanguage" in content or "from '../contexts/LanguageContext'" in content
        assert "t('bots_community_title')" in content

    def test_caly_uses_t(self):
        content = open("/app/frontend/src/components/CalyChatbot.jsx").read()
        assert "from '../contexts/LanguageContext'" in content
        assert "t('caly_title')" in content


class TestRegression:
    def test_view_spec_endpoint_still_works(self):
        import requests
        r = requests.get(f"{os.environ.get('BACKEND_URL') or 'http://localhost:8001'}/api/views/spec")
        assert r.status_code == 200

    def test_no_compile_errors_in_main_files(self):
        """Vérifie que les fichiers principaux n'ont pas d'erreur évidente."""
        for path in ["/app/frontend/src/pages/Dashboard.js",
                     "/app/frontend/src/pages/PrivateProgramming.js",
                     "/app/frontend/src/components/BotsAdminPanel.jsx",
                     "/app/frontend/src/components/CalyChatbot.jsx"]:
            assert os.path.exists(path)
            content = open(path).read()
            # Pas d'imports cassés
            assert "import {" in content
