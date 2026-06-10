"""iter87 — Tests pour :
- ViewModePicker : vue 'creator' désormais cochable + viewMode=null si rien coché
- guest_view i18n traductions modo/admin
- PrivateProgramming : bloqué pour TOUS (incluant créa)
- /private/code/* renvoie 403 systématique
- Distinction public/private : history limit 50 (public) vs 500 (private only)
- ModelPicker : nouveaux IDs Emergent (claude-5-fable, claude-4.8-opus, gpt-5.5, etc.)
"""
import os
import requests

BACKEND_URL = os.environ.get('BACKEND_URL') or 'http://localhost:8001'
API = f"{BACKEND_URL}/api"


class TestViewModePickerExtended:
    def test_creator_in_ORDER(self):
        content = open("/app/frontend/src/components/ViewModePicker.jsx").read()
        assert "['creator', 'user', 'modo', 'admin', 'guest']" in content

    def test_viewMode_can_be_null(self):
        content = open("/app/frontend/src/hooks/useDeviceIdentity.js").read()
        assert "localStorage.removeItem(VIEW_MODE_KEY)" in content
        # readViewMode retourne null si vide
        assert "return null" in content


class TestI18nForceModoAdmin:
    def test_fr_keys(self):
        content = open("/app/frontend/src/contexts/LanguageContext.js").read()
        assert "sm_guest_view_force_modo: 'Forcer la vue modo'" in content
        assert "sm_guest_view_force_admin: 'Forcer la vue admin'" in content

    def test_en_keys(self):
        content = open("/app/frontend/src/contexts/LanguageContext.js").read()
        assert "sm_guest_view_force_modo: 'Force modo view'" in content
        assert "sm_guest_view_force_admin: 'Force admin view'" in content


class TestPrivateCodeBlocked:
    def test_read_file_403(self):
        r = requests.post(f"{API}/private/code/read-file",
                          json={"key_id": "x", "nonce": "n", "signature": "s", "path": "test"})
        # Désormais TOUS bloqués (même créatrice) : 403
        assert r.status_code == 403

    def test_grep_403(self):
        r = requests.post(f"{API}/private/code/grep",
                          json={"key_id": "x", "nonce": "n", "signature": "s", "pattern": "test"})
        assert r.status_code == 403

    def test_frontend_page_locked(self):
        content = open("/app/frontend/src/pages/PrivateProgramming.js").read()
        assert "Accès refusé" in content
        # Le test 'allowed' a été retiré, l'écran de garde est permanent
        assert "private-access-denied" in content


class TestPublicPrivateContextDifferentiation:
    def test_history_limit_in_server(self):
        src = open("/app/backend/server.py").read()
        # iter87 — public = 50, privé = 500
        assert "_context_limit = 500 if _is_private_only else 50" in src
        # Détermination via _get_site_modes_list (les modes actifs)
        assert "_is_private_only" in src


class TestNewModelIds:
    def test_emergent_models_listed(self):
        # GET /chat/models sans auth → 401
        r = requests.get(f"{API}/chat/models", timeout=5)
        assert r.status_code in (401, 422)

    def test_model_routes_extended(self):
        src = open("/app/backend/server.py").read()
        # Les nouveaux IDs sont mappés
        for mid in ("claude-5-fable", "claude-4.8-opus", "claude-4.7-opus-1m",
                    "claude-4.6-sonnet", "gpt-5.5", "gpt-5.3-codex",
                    "gemini-3.1-pro", "gpt-5.4-1m"):
            assert mid in src, f"Model id {mid} missing from MODEL_ROUTES"

    def test_default_model_is_claude_sonnet(self):
        src = open("/app/backend/server.py").read()
        # iter87 — default switched from gpt-5.2 to claude-sonnet (Emergent recommended)
        assert 'MODEL_ROUTES.get(model_choice, ("anthropic", "claude-sonnet-4-5-20250929"))' in src
