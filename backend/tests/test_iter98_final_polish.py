"""iter98 — Tests finaux pour les dernières features de la wishlist :
- TypewriterEffect câblé dans Chat.js
- Vue interactive iframe sur l'œil création (LivePreviewPanel câblé dans Chat.js)
- Architecture admin bots community (CRUD)
"""
import os
import requests

BACKEND_URL = os.environ.get('BACKEND_URL') or 'http://localhost:8001'
API = f"{BACKEND_URL}/api"


class TestTypewriterEffectWired:
    """TypewriterEffect câblé dans Chat.js sur les messages AI _just_arrived."""

    def test_chat_imports_typewriter(self):
        content = open("/app/frontend/src/pages/Chat.js").read()
        assert "import TypewriterEffect" in content
        assert "chat-typewriter" in content
        assert "msg._just_arrived" in content
        # Skip pour Emergent qui rend code-par-code
        assert "(msg.ai_source || '').includes('emergent')" in content

    def test_ai_response_marks_just_arrived(self):
        content = open("/app/frontend/src/pages/Chat.js").read()
        assert "_just_arrived: true" in content


class TestCreationPreviewIframe:
    """Vue interactive iframe quand l'utilisatrice clique l'œil sur une création."""

    def test_chat_imports_live_preview(self):
        content = open("/app/frontend/src/pages/Chat.js").read()
        assert "import LivePreviewPanel" in content
        assert "showCreationPreview" in content
        assert "location.state?.openPreview" in content


class TestCommunityBots:
    """Architecture admin bots community façon Top.gg."""

    def test_endpoints_defined(self):
        src = open("/app/backend/server.py").read()
        assert "/community-bots/create" in src
        assert "/community-bots/list" in src
        assert "/community-bots/delete" in src
        assert "/community-bots/rate" in src
        assert "CommunityBotIn" in src
        assert "BotRateIn" in src

    def test_create_requires_creator_or_admin(self):
        src = open("/app/backend/server.py").read()
        assert 'if not (role == "creator" or sk == "admin")' in src
        assert "Réservé créa/admin" in src

    def test_delete_requires_creator(self):
        src = open("/app/backend/server.py").read()
        # Suppress doit utiliser _require_creator_signature
        assert "_require_creator_signature(payload.key_id, payload.nonce, payload.signature)" in src

    def test_endpoint_list_public(self):
        """GET /community-bots/list est public (pas d'auth requise)."""
        r = requests.get(f"{API}/community-bots/list")
        assert r.status_code == 200
        assert "bots" in r.json()

    def test_endpoint_create_requires_signature(self):
        r = requests.post(f"{API}/community-bots/create",
                          json={"key_id": "x", "nonce": "n", "signature": "s",
                                "name": "test", "description": "d", "prompt": "p"})
        # Sans clé valide → 403 (signature) ou 404 (clé inconnue)
        assert r.status_code in (403, 404)

    def test_rate_requires_signature(self):
        r = requests.post(f"{API}/community-bots/rate",
                          json={"key_id": "x", "nonce": "n", "signature": "s",
                                "bot_id": "b", "rating": 5})
        assert r.status_code in (403, 404)
