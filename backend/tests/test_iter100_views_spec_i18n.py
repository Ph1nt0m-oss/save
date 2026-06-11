"""iter100 — Tests pour :
- Endpoint /views/spec (matrice d'accès des vues)
- Hook useViewSpec frontend
- i18n nouvelles clés FR
"""
import os
import requests

BACKEND_URL = os.environ.get('BACKEND_URL') or 'http://localhost:8001'
API = f"{BACKEND_URL}/api"


class TestViewsSpec:
    def test_endpoint_public(self):
        r = requests.get(f"{API}/views/spec")
        assert r.status_code == 200
        d = r.json()
        assert "user" in d and "modo" in d and "admin" in d and "creator" in d

    def test_creator_sees_all(self):
        r = requests.get(f"{API}/views/spec")
        d = r.json()
        assert d["creator"]["see_programming"] is True
        assert d["creator"]["secret_key_access"] is True
        assert d["creator"]["see_bots_community"] is True

    def test_user_no_secret_access(self):
        r = requests.get(f"{API}/views/spec")
        d = r.json()
        assert d["user"]["see_programming"] is False
        assert d["user"]["secret_key_access"] is False
        assert d["user"]["see_poll_icon"] is False

    def test_modo_sees_staff_chat_not_admin(self):
        r = requests.get(f"{API}/views/spec")
        d = r.json()
        assert "staff" in d["modo"]["chats_visible"]
        assert "modo" in d["modo"]["chats_visible"]
        assert "admin" in d["modo"]["chats_hidden"]

    def test_admin_sees_admin_chat_not_modo(self):
        r = requests.get(f"{API}/views/spec")
        d = r.json()
        assert "admin" in d["admin"]["chats_visible"]
        assert "modo" in d["admin"]["chats_hidden"]
        assert d["admin"]["see_bots_community"] is True


class TestUseViewSpecHook:
    def test_hook_exists(self):
        path = "/app/frontend/src/hooks/useViewSpec.js"
        assert os.path.exists(path)
        content = open(path).read()
        assert "useViewSpec" in content
        assert "/views/spec" in content
        # Override programming pour role physique
        assert "isPhysicallyCreator" in content
        assert "canSeeProgramming" in content
        assert "canSeeBotsAdmin" in content


class TestI18nNewKeys:
    def test_fr_new_keys(self):
        content = open("/app/frontend/src/contexts/LanguageContext.js").read()
        assert "wizard_title:" in content
        assert "prog_ai_title:" in content
        assert "prog_site_title:" in content
        assert "view_user:" in content
        assert "view_modo:" in content
        assert "view_admin:" in content
        assert "view_creator:" in content
        assert "bots_community_title:" in content
        assert "caly_title:" in content
        assert "signup_github_required:" in content
        assert "private_mode_send_to:" in content
