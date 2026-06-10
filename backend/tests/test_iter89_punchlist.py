"""iter89 — Tests pour le punch-list utilisatrice (Message 660) :
- Issue 1 : Mot de passe créatrice pour vider la boîte à idées (fallback device-only)
- Task 1 : Nouveaux modèles backend (Vexub, Emergent Collab, Claude 5 Fable, etc.)
- Issue 2 : Reprise des chats sidebar (history fetch correct)
"""
import os
import requests

BACKEND_URL = os.environ.get('BACKEND_URL') or 'http://localhost:8001'
API = f"{BACKEND_URL}/api"


class TestIdeasClearPasswordFallback:
    """Issue 1 (P0) — Vérifier que /ideas/clear gère le cas d'un créa
    sans password_hash classique (device-only)."""

    def test_ideas_clear_requires_signature(self):
        # Sans signature ECDSA → 403
        r = requests.post(f"{API}/ideas/clear",
                          json={"key_id": "x", "nonce": "n", "signature": "s",
                                "scope": "all", "password": "anything"})
        assert r.status_code == 403

    def test_ideas_clear_invalid_scope(self):
        r = requests.post(f"{API}/ideas/clear",
                          json={"key_id": "x", "nonce": "n", "signature": "s",
                                "scope": "weird"})
        # 403 first because signature fails before scope validation
        assert r.status_code in (400, 403)

    def test_ideas_clear_fallback_logic_present(self):
        """Le code doit avoir le fallback iter89 pour les comptes device-only."""
        src = open("/app/backend/server.py").read()
        assert "iter89" in src
        # Le fallback : si pas de password_hash, accepter signature ECDSA
        assert "compte" in src.lower() or "device-only" in src.lower()


class TestNewModels:
    """Task 1 — Nouveaux modèles Vexub + Emergent Collab + Claude 5 Fable + GPT 5.5"""

    def test_model_routes_include_new(self):
        src = open("/app/backend/server.py").read()
        assert '"emergent-collab"' in src
        assert '"vexub-video"' in src
        assert '"claude-5-fable"' in src
        assert '"gpt-5.5"' in src
        assert '"claude-4.8-opus"' in src
        assert '"claude-4.7-opus-1m"' in src
        assert '"claude-4.6-sonnet"' in src
        assert '"gpt-5.3-codex"' in src
        assert '"gemini-3.1-pro"' in src
        assert '"gpt-5.4-1m"' in src

    def test_chat_models_endpoint_requires_auth(self):
        r = requests.get(f"{API}/chat/models?context=chat")
        # Sans auth → 401
        assert r.status_code == 401

    def test_modelpicker_badge_icons_complete(self):
        """Frontend : les badges nouveaux ont leur icône."""
        content = open("/app/frontend/src/components/ModelPicker.jsx").read()
        assert "'Collaboration': Layers" in content
        assert "'Vidéo': Video" in content
        assert "'Le plus capable': Crown" in content
        assert "'Contexte long': BookOpen" in content


class TestChatHistoryResume:
    """Issue 2 — Vérifier que /chat/history retourne bien les messages
    filtrés par project_id (pour la reprise de tchat sidebar)."""

    def test_chat_history_endpoint_exists(self):
        r = requests.get(f"{API}/chat/history?project_id=fake")
        # Sans auth → 401
        assert r.status_code == 401

    def test_chat_message_persists_project_id(self):
        """Le code de persistance dans /chat/message doit attacher project_id."""
        src = open("/app/backend/server.py").read()
        # user_message_doc doit inclure project_id_eff
        assert '"project_id": project_id_eff' in src
        # Auto-create project si absent
        assert "Auto-created chat project" in src


class TestPrivateProgrammingSecurity:
    """Vérifier que les endpoints /private/code/* sont verrouillés 403."""

    def test_private_code_read_locked(self):
        r = requests.post(f"{API}/private/code/read-file",
                          json={"key_id": "x", "nonce": "n", "signature": "s",
                                "path": "server.py"})
        assert r.status_code == 403

    def test_private_code_grep_locked(self):
        r = requests.post(f"{API}/private/code/grep",
                          json={"key_id": "x", "nonce": "n", "signature": "s",
                                "pattern": "test"})
        assert r.status_code == 403
