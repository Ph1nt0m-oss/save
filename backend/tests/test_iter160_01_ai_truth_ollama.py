"""Chantier iter160 — Vérité du routage IA + détection Ollama côté user.

Tests obligatoires du §13 :
- IA sans handler → erreur explicite (501 ai_integration_not_configured)
- Grok sans XAI_API_KEY → erreur explicite (501 ai_grok_key_missing)
- Backend retourne requested_model + model_used
- Pas de fallback silencieux
- Détection Ollama déplacée côté navigateur
- Message offline exact
- Exemption Créa/Admin
"""
from __future__ import annotations

import os
import uuid
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import requests
from pymongo import MongoClient


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")
FRONT = Path("/app/frontend/src")
BACK = Path("/app/backend")


def _r(p: Path) -> str:
    return p.read_text(encoding="utf-8")


@pytest.fixture
def mongo():
    cli = MongoClient(MONGO_URL)
    yield cli[DB_NAME]
    cli.close()


@pytest.fixture
def session(mongo):
    uid = f"TEST_u160_{uuid.uuid4().hex[:8]}"
    token = f"TEST_sess_{secrets.token_urlsafe(24)}"
    mongo.user_sessions.insert_one({
        "user_id": uid, "session_token": token,
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    yield uid, token
    mongo.user_sessions.delete_many({"session_token": token})


def _h(t): return {"Authorization": f"Bearer {t}"}


# ---------------------------------------------------------------------------
# §2+§3 — IA sans handler réel → erreur explicite, pas de fallback
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("model_key,expected_code", [
    ("emergent-collab", "ai_integration_not_configured"),
    ("vexub-video",     "ai_integration_not_configured"),
    ("lindy-flow",      "ai_integration_not_configured"),
])
def test_unsupported_providers_return_501_explicit_error(session, model_key, expected_code):
    """Vexub / Lindy / Emergent-Collab doivent renvoyer 501 avec un payload
    `code=ai_integration_not_configured` + `requested_model` + `provider`."""
    _, token = session
    r = requests.post(
        f"{API}/chat/message",
        headers=_h(token),
        json={"message": "test", "mode": "online", "model": model_key, "language": "fr"},
        timeout=15,
    )
    assert r.status_code == 501, f"Attendu 501, reçu {r.status_code} : {r.text[:200]}"
    body = r.json()
    detail = body.get("detail", {})
    if isinstance(detail, str):
        pytest.fail(f"detail devrait être un objet structuré, reçu string : {detail}")
    assert detail.get("code") == expected_code
    assert detail.get("requested_model") == model_key


def test_grok_without_key_returns_explicit_error(session):
    """Si XAI_API_KEY absente, grok-4.3 doit renvoyer 501 ai_grok_key_missing."""
    _, token = session
    # Vérifie qu'il n'y a pas de XAI_API_KEY avant.
    if os.environ.get("XAI_API_KEY"):
        pytest.skip("XAI_API_KEY présente — ce test suppose son absence.")
    r = requests.post(
        f"{API}/chat/message",
        headers=_h(token),
        json={"message": "test", "mode": "online", "model": "grok-4.3", "language": "fr"},
        timeout=15,
    )
    assert r.status_code == 501
    detail = r.json().get("detail", {})
    assert detail.get("code") == "ai_grok_key_missing"
    assert detail.get("provider") == "xai"


def test_backend_response_contains_requested_and_used_model(session):
    """Une réponse réussie doit inclure `requested_model` + `model_used`."""
    _, token = session
    r = requests.post(
        f"{API}/chat/message",
        headers=_h(token),
        json={"message": "Bonjour", "mode": "online", "model": "claude-sonnet", "language": "fr"},
        timeout=60,
    )
    # Peut être 200 (succès) ou 502 (quota) — dans les 2 cas pas de fallback.
    if r.status_code == 200:
        ai = r.json().get("ai_response", {})
        assert "requested_model" in ai
        assert "model_used" in ai
        assert ai["requested_model"] == "claude-sonnet"
        # model_used doit refléter ce qui a répondu réellement.
        assert ai["model_used"]
        # Pas de bascule silencieuse : si model_used commence par emergent:,
        # le provider doit être anthropic (le modèle choisi).
        if ai["model_used"].startswith("emergent:"):
            parts = ai["model_used"].split(":")
            assert parts[1] == "anthropic", f"Fallback silencieux détecté : {ai['model_used']}"
    elif r.status_code in (501, 502):
        detail = r.json().get("detail", {})
        assert detail.get("requested_model") == "claude-sonnet"


# ---------------------------------------------------------------------------
# §3 — Pas de fallback cascade dans le code
# ---------------------------------------------------------------------------

def test_backend_removed_fallback_chain_in_chat_stream():
    """Le fallback_chain de /chat/stream (7 modèles) doit être supprimé.
    `ordered_chain = [primary]` doit être unique."""
    src = _r(BACK / "server.py")
    assert "ordered_chain = [primary]" in src
    # Les anciennes lignes comme ("anthropic", "claude-sonnet-4-5-20250929") dans
    # fallback_chain ne doivent plus être enchaînées.
    assert "fallback_chain = [" not in src.replace("# fallback_chain", "")


def test_backend_removed_cascade_in_create():
    """CREATE : la cascade de 7 modèles disparaît aussi."""
    src = _r(BACK / "server.py")
    assert "ordered_gen_chain = [(provider, model_id)]" in src
    # L'ancien `generation_chain` à 8 entrées ne doit plus exister comme loop.
    assert "generation_chain = [" not in src


# ---------------------------------------------------------------------------
# §8 — Détection Ollama côté navigateur (CORS user agent)
# ---------------------------------------------------------------------------

def test_frontend_chat_detects_ollama_via_browser_fetch():
    src = _r(FRONT / "pages/Chat.js")
    assert "fetch('http://localhost:11434/api/tags'" in src
    assert "AbortSignal.timeout(3000)" in src
    # Plus de passage par le proxy backend pour la détection active.
    # On garde /api/system/ollama-status comme info de diagnostic mais la
    # décision de verrou vient du fetch direct.
    pos_fetch = src.find("fetch('http://localhost:11434/api/tags'")
    pos_check = src.find("const check =")
    assert pos_check < pos_fetch < pos_check + 2000


def test_frontend_create_detects_ollama_via_browser_fetch():
    src = _r(FRONT / "pages/Create.js")
    assert "fetch('http://localhost:11434/api/tags'" in src


def test_offline_installer_uses_browser_fetch():
    src = _r(FRONT / "components/OfflineAIInstaller.jsx")
    assert "fetch('http://localhost:11434/api/tags'" in src


# ---------------------------------------------------------------------------
# §9 — gemma3:4b reconnu
# ---------------------------------------------------------------------------

def test_frontend_recommends_gemma3_4b_and_variants():
    """La whitelist côté client doit inclure gemma3:4b, deepseek-r1:7b, llama3.2."""
    src = _r(FRONT / "pages/Chat.js")
    for m in ("gemma3:4b", "gemma3:2b", "deepseek-r1:7b", "llama3.2:3b"):
        assert f"'{m}'" in src, f"Modèle {m} manquant de la whitelist Chat"


# ---------------------------------------------------------------------------
# §11 — Exemption Créa / Admin
# ---------------------------------------------------------------------------

def test_chat_exempts_creator_and_admin():
    """Chat.js : si device.role==='creator' ou staff_kind==='admin',
    le verrou offline est désactivé (jamais appliqué)."""
    src = _r(FRONT / "pages/Chat.js")
    assert "isCreatorOrAdmin" in src
    assert "device?.role === 'creator'" in src or "r === 'creator'" in src
    assert "staff_kind === 'admin'" in src or "sk === 'admin'" in src
    # offlineLocked composé AVEC exemption.
    assert "const offlineLocked = mode === 'offline' && !ollamaAvailable && !isCreatorOrAdmin" in src


def test_create_exempts_creator_and_admin():
    src = _r(FRONT / "pages/Create.js")
    assert "isCreatorOrAdmin" in src
    assert "device?.role === 'creator'" in src
    assert "device?.staff_kind === 'admin'" in src


# ---------------------------------------------------------------------------
# §12 — Message offline EXACT
# ---------------------------------------------------------------------------

def test_offline_message_exact_wording():
    """Le banner doit utiliser EXACTEMENT :
    « IA locale non détectée. Tout a été bloqué et se déverouillera lorsque la détection est réussie. »"""
    src = _r(FRONT / "pages/Chat.js")
    assert "IA locale non détectée. Tout a été bloqué et se déverouillera lorsque la détection est réussie." in src
    # L'ancien message doit avoir disparu.
    assert "verrouillées jusqu'à détection réussie" not in src


# ---------------------------------------------------------------------------
# §7 — Caly n'est jamais mélangée avec le routage IA utilisateur
# ---------------------------------------------------------------------------

def test_caly_prompt_scope_isolated():
    """Caly reste uniquement /caly/*. Le prompt /chat/stream interdit
    explicitement de se présenter comme Caly."""
    src = _r(BACK / "server.py")
    assert "Tu NE t'appelles PAS Caly" in src
    # L'ancienne version « Tu es **Caly** » n'est plus dans /chat/stream.
    chat_stream_prompt_pos = src.find("Chantier iter159.2 §3 — Prompt système MODEL-NEUTRAL")
    assert chat_stream_prompt_pos > 0


# ---------------------------------------------------------------------------
# §13 — HTTPException ne doit pas être swallowed par le wrapper externe
# ---------------------------------------------------------------------------

def test_backend_http_exception_bubbles_up_not_caught():
    """Les HTTPException levées par le routage IA ne doivent pas être
    attrapées par le except Exception générique."""
    src = _r(BACK / "server.py")
    # Marqueur : present dans le code ajouté iter160.
    assert "iter160 §3 — Erreur explicite IA remontée avec son payload structuré" in src
    # Le except générique du handler est précédé par un `except HTTPException: raise`.
    pos = src.find("iter160 §3 — Erreur explicite IA")
    assert "except HTTPException:" in src[max(0, pos - 300):pos]
