"""iter90 — Tests pour le punch-list correctif (Message 662) :
- P0 STRICT : /ideas/clear DOIT utiliser bcrypt verify uniquement (pas de fallback)
- Nouveaux modèles : Grok 4.3 + Grok 4.20 Reasoning + Lindy Flow
- Mode hors-ligne : composant OfflineAIInstaller existe et /system/ollama-status répond
"""
import os
import requests

BACKEND_URL = os.environ.get('BACKEND_URL') or 'http://localhost:8001'
API = f"{BACKEND_URL}/api"


class TestIdeasClearStrictPassword:
    """P0 — /ideas/clear DOIT exiger STRICTEMENT le password du compte créa.
    Le fallback "device-only accepte tout password" introduit en iter89 a été
    RETIRÉ en iter90 (régression sécurité signalée par utilisatrice).
    """

    def test_iter89_fallback_removed(self):
        """Le code 'fallback device-only' iter89 ne doit plus exister."""
        src = open("/app/backend/server.py").read()
        # iter89 fallback string doit être absent
        assert "compte\n            # device-only" not in src
        # Le marker iter90 strict doit être présent
        assert "iter90 — Strict bcrypt verify uniquement" in src
        # 412 quand pas de password_hash (message clair)
        assert "n'a pas de mot de passe configuré" in src

    def test_ideas_clear_403_without_sig(self):
        r = requests.post(f"{API}/ideas/clear",
                          json={"key_id": "x", "nonce": "n", "signature": "s",
                                "scope": "all", "password": "Pass1234"})
        assert r.status_code == 403


class TestNewModelsIter90:
    """Grok 4.3 + Grok 4.20 Reasoning + Lindy Flow"""

    def test_model_routes_grok_lindy(self):
        src = open("/app/backend/server.py").read()
        assert '"grok-4.3"' in src
        assert '"grok-4.20-reasoning"' in src
        assert '"lindy-flow"' in src
        # Provider mapping
        assert '("xai",      "grok-4.3")' in src
        assert '("lindy",    "flow")' in src

    def test_chat_models_list_has_new(self):
        """Liste UI exposée dans /chat/models contient les 3 nouveaux."""
        src = open("/app/backend/server.py").read()
        assert '"id": "grok-4.3"' in src
        assert '"id": "grok-4.20-reasoning"' in src
        assert '"id": "lindy-flow"' in src
        # Badges
        assert '"badge": "Temps réel"' in src
        assert '"badge": "Workflow"' in src

    def test_modelpicker_icons_iter90(self):
        content = open("/app/frontend/src/components/ModelPicker.jsx").read()
        # iter90 icons
        assert "'Temps réel': Radio" in content
        assert "'Workflow': Workflow" in content


class TestOfflineInstaller:
    """Mode hors-ligne : composant + endpoint backend."""

    def test_ollama_status_endpoint(self):
        r = requests.get(f"{API}/system/ollama-status")
        assert r.status_code == 200
        data = r.json()
        assert "available" in data
        assert isinstance(data.get("models"), list)

    def test_offline_installer_component_exists(self):
        path = "/app/frontend/src/components/OfflineAIInstaller.jsx"
        assert os.path.exists(path)
        content = open(path).read()
        # Tabs OS (via template literal — la chaîne `offline-installer-os-` apparaît)
        assert "offline-installer-os-" in content
        assert "{ id: 'mac'" in content
        assert "{ id: 'windows'" in content
        assert "{ id: 'linux'" in content
        # Recheck button
        assert "offline-installer-recheck" in content
        # Auto-detection
        assert "ollama-status" in content
        # Install command
        assert "ollama pull gemma3:4b" in content

    def test_chat_page_wires_installer(self):
        chat = open("/app/frontend/src/pages/Chat.js").read()
        assert "OfflineAIInstaller" in chat
        assert "showOfflineInstaller" in chat
        assert "chat-offline-installer-btn" in chat


class TestRegressionIter89:
    """Régression iter89 — toujours présent."""

    def test_chat_history_loading_state(self):
        chat = open("/app/frontend/src/pages/Chat.js").read()
        assert "historyLoading" in chat
        assert "chat-history-loading" in chat
        assert "chat-empty-state" in chat

    def test_emergent_collab_vexub_still_present(self):
        src = open("/app/backend/server.py").read()
        assert '"emergent-collab"' in src
        assert '"vexub-video"' in src
        assert '"claude-5-fable"' in src
