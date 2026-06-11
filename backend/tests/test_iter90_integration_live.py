"""iter90 — Tests d'intégration LIVE contre l'URL publique (REACT_APP_BACKEND_URL).

Couvre la validation runtime:
- /system/ollama-status (public, 200)
- /chat/models?context=chat (auth requise, 13 online, 3 nouveaux badges)
- /ideas/clear sans signature → 403
"""
import os
import re
import requests

with open("/app/frontend/.env") as f:
    m = re.search(r"REACT_APP_BACKEND_URL=(.+)", f.read())
BACKEND_URL = (m.group(1).strip() if m else os.environ.get("BACKEND_URL", "http://localhost:8001"))
API = f"{BACKEND_URL}/api"

CRED_EMAIL = "test_dash_1777658375@gmail.com"
CRED_PWD = "Pass1234"


def _login_token():
    r = requests.post(f"{API}/auth/login", json={"email": CRED_EMAIL, "password": CRED_PWD}, timeout=20)
    if r.status_code != 200:
        return None
    return r.json().get("session_token")


class TestOllamaStatusLive:
    def test_public_ollama_status(self):
        r = requests.get(f"{API}/system/ollama-status", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "available" in d and isinstance(d["available"], bool)
        assert "models" in d and isinstance(d["models"], list)


class TestChatModelsLive:
    def test_models_list_has_13_with_new_badges(self):
        tok = _login_token()
        assert tok, "Login failed — credentials may have rotated"
        r = requests.get(f"{API}/chat/models?context=chat",
                         headers={"Authorization": f"Bearer {tok}"}, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        online = data.get("online", [])
        assert len(online) == 13, f"Expected 13 online models, got {len(online)}"
        ids = {m["id"]: m for m in online}
        assert "grok-4.3" in ids and ids["grok-4.3"]["badge"] == "Temps réel"
        assert "grok-4.20-reasoning" in ids and ids["grok-4.20-reasoning"]["badge"] == "Thinking"
        assert "lindy-flow" in ids and ids["lindy-flow"]["badge"] == "Workflow"
        assert ids["grok-4.3"]["provider"] == "xAI"
        assert ids["lindy-flow"]["provider"] == "Lindy"

    def test_models_chat_requires_auth(self):
        r = requests.get(f"{API}/chat/models?context=chat", timeout=15)
        assert r.status_code in (401, 403)


class TestIdeasClearLive:
    def test_clear_without_signature_403(self):
        r = requests.post(f"{API}/ideas/clear",
                          json={"key_id": "x", "nonce": "n", "signature": "s",
                                "scope": "all", "password": "Pass1234"}, timeout=15)
        assert r.status_code == 403

    def test_clear_invalid_scope_403_before_400(self):
        # Without sig the gate stops first
        r = requests.post(f"{API}/ideas/clear",
                          json={"key_id": "x", "nonce": "n", "signature": "s",
                                "scope": "bogus", "password": "Pass1234"}, timeout=15)
        assert r.status_code == 403


class TestSourceAuditIter90:
    """Audit code source pour les invariants P0."""

    def test_no_iter89_fallback_remnant(self):
        src = open("/app/backend/server.py").read()
        # Pas de mention du fallback device-only iter89
        assert "device-only" not in src.split("/ideas/clear")[-1][:2000] or \
               "compte device-only sans email/password" in src  # commentaire iter90 OK
        # Marker iter90 strict
        assert "iter90 — Strict bcrypt verify uniquement" in src
        # 412 path
        assert "n'a pas de mot de passe configuré" in src
        assert "status_code=412" in src
        # 428 path
        assert "status_code=428" in src
        # 403 password incorrect
        assert "Mot de passe incorrect" in src

    def test_password_path_uses_bcrypt_checkpw(self):
        src = open("/app/backend/server.py").read()
        # Extract /ideas/clear function body
        idx = src.find('@api_router.post("/ideas/clear")')
        body = src[idx: idx + 3500]
        assert "bcrypt.checkpw" in body
        # Pas de fallback "device-only accepte password"
        assert "compte device-only" not in body or "Crée-en un" in body  # message ok
