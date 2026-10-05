"""Chantier iter161 — Routage réel des IA online + bascule Création.

Tests obligatoires :
- resolve_model respecte EXACTEMENT le modèle demandé (plus de bascule
  silencieuse vers gpt-4o-mini / claude-sonnet-4.5).
- Les providers sans handler (emergent, vexub, lindy) lèvent 501 explicite.
- xAI sans XAI_API_KEY lève 501 ai_grok_key_missing.
- /chat/stream détecte une demande de création d'app et renvoie
  action=redirect_to_create (pas de bavardage Forge).
- L'event agent du pipeline expose provider+model_id+model_label pour que
  le badge affiche le vrai modèle (pas "Caly").
- chat_agent n'écrit plus "Tu es Caly" dans son prompt système.
"""
from __future__ import annotations

import os
import json
import uuid
import secrets
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import requests
from pymongo import MongoClient


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

# Rend accessible le package `agents` du backend pour les tests unitaires.
BACKEND_DIR = Path("/app/backend")
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


@pytest.fixture
def mongo():
    cli = MongoClient(MONGO_URL)
    yield cli[DB_NAME]
    cli.close()


@pytest.fixture
def session(mongo):
    uid = f"TEST_u161_{uuid.uuid4().hex[:8]}"
    token = f"TEST_sess_{secrets.token_urlsafe(24)}"
    mongo.user_sessions.insert_one({
        "user_id": uid, "session_token": token,
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    mongo.users.insert_one({
        "id": uid, "email": f"{uid}@test.local",
        "role": "approved", "created_at": datetime.now(timezone.utc).isoformat(),
    })
    yield {"user_id": uid, "token": token,
           "headers": {"Authorization": f"Bearer {token}"}}
    for coll in ("user_sessions", "users", "projects", "chat_messages"):
        mongo[coll].delete_many({"user_id": uid})


# ----------------------------------------------------------------------------
# §P0.1 — resolve_model respecte le choix utilisateur (plus de downgrade)
# ----------------------------------------------------------------------------

def test_resolve_model_claude_fable_5_exact():
    """iter161 §P0.1 — Claude 5 Fable doit router vers claude-fable-5, PAS vers sonnet-4.5."""
    from agents.common import resolve_model
    provider, model_id = resolve_model("claude-5-fable")
    assert provider == "anthropic", f"Expected anthropic, got {provider}"
    assert model_id == "claude-fable-5", (
        f"BUG CRITIQUE: Claude 5 Fable mal routé — got {model_id} "
        f"(ancien bug: downgrade vers claude-sonnet-4-5-20250929)"
    )


def test_resolve_model_gpt_5_5_exact():
    """GPT-5.5 doit router vers openai:gpt-5.5, PAS vers gpt-4o-mini."""
    from agents.common import resolve_model
    provider, model_id = resolve_model("gpt-5.5")
    assert provider == "openai"
    assert model_id == "gpt-5.5", (
        f"BUG CRITIQUE: GPT-5.5 mal routé — got {model_id} "
        f"(ancien bug: tout non-claude non-gemini → gpt-4o-mini)"
    )


def test_resolve_model_claude_opus_48_exact():
    from agents.common import resolve_model
    provider, model_id = resolve_model("claude-4.8-opus")
    assert (provider, model_id) == ("anthropic", "claude-opus-4-8")


def test_resolve_model_gemini_31_pro_exact():
    """Gemini 3.1 Pro doit router vers gemini-3.1-pro-preview, PAS vers gemini-3-flash."""
    from agents.common import resolve_model
    provider, model_id = resolve_model("gemini-3.1-pro")
    assert provider == "gemini"
    assert "pro" in model_id, (
        f"BUG CRITIQUE: Gemini 3.1 Pro downgradé — got {model_id}"
    )


def test_resolve_model_gpt_5_3_codex_exact():
    from agents.common import resolve_model
    assert resolve_model("gpt-5.3-codex") == ("openai", "gpt-5.3-codex")


def test_resolve_model_claude_47_opus_1m_exact():
    from agents.common import resolve_model
    assert resolve_model("claude-4.7-opus-1m") == ("anthropic", "claude-opus-4-7-1m")


def test_resolve_model_claude_46_sonnet_exact():
    from agents.common import resolve_model
    assert resolve_model("claude-4.6-sonnet") == ("anthropic", "claude-sonnet-4-6")


# ----------------------------------------------------------------------------
# §P0.1 — Providers sans handler → 501 ai_integration_not_configured
# ----------------------------------------------------------------------------

def test_resolve_model_emergent_raises_501():
    """iter161 §P0.1 — Emergent sans handler → erreur explicite, pas de fallback."""
    from agents.common import resolve_model, AIModelUnavailable
    with pytest.raises(AIModelUnavailable) as exc:
        resolve_model("emergent")
    assert exc.value.status_code == 501
    assert exc.value.detail["code"] == "ai_integration_not_configured"
    assert exc.value.detail["provider"] == "emergent"


def test_resolve_model_vexub_raises_501():
    from agents.common import resolve_model, AIModelUnavailable
    with pytest.raises(AIModelUnavailable) as exc:
        resolve_model("vexub-video")
    assert exc.value.detail["code"] == "ai_integration_not_configured"
    assert exc.value.detail["provider"] == "vexub"


def test_resolve_model_lindy_raises_501():
    from agents.common import resolve_model, AIModelUnavailable
    with pytest.raises(AIModelUnavailable) as exc:
        resolve_model("lindy-flow")
    assert exc.value.detail["code"] == "ai_integration_not_configured"


def test_resolve_model_grok_without_key_raises_501(monkeypatch):
    """iter161 §P0.1 — Grok sans XAI_API_KEY → erreur explicite."""
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    from agents.common import resolve_model, AIModelUnavailable
    with pytest.raises(AIModelUnavailable) as exc:
        resolve_model("grok-4.3")
    assert exc.value.detail["code"] == "ai_grok_key_missing"


def test_resolve_model_grok_with_key_ok(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "sk-fake-test-key")
    from agents.common import resolve_model
    assert resolve_model("grok-4.3") == ("xai", "grok-4.3")


def test_resolve_model_unknown_raises_501():
    from agents.common import resolve_model, AIModelUnavailable
    with pytest.raises(AIModelUnavailable) as exc:
        resolve_model("totally-made-up-model-xyz")
    assert exc.value.detail["code"] == "ai_model_unknown"


def test_resolve_model_non_strict_fallbacks_silently():
    """Mode non-strict (helpers internes router) : pas d'exception."""
    from agents.common import resolve_model
    provider, model_id = resolve_model("emergent", strict=False)
    assert provider == "emergent"  # Pas de 501 en non-strict.


# ----------------------------------------------------------------------------
# §P0.2 — Détection "demande de création d'app" (shortcut Chat → /create)
# ----------------------------------------------------------------------------

def test_is_create_app_request_positives():
    from agents.router_agent import is_create_app_request
    assert is_create_app_request("Tu peux me faire une application de foot ?")
    assert is_create_app_request("Crée-moi un site de rencontres")
    assert is_create_app_request("J'aimerais un jeu de puzzle")
    assert is_create_app_request("fais-moi une application mobile pour la cuisine")
    assert is_create_app_request("peux-tu me développer un outil de calcul")


def test_is_create_app_request_negatives():
    from agents.router_agent import is_create_app_request
    assert not is_create_app_request("Salut, comment ça va ?")
    assert not is_create_app_request("Hello !")
    assert not is_create_app_request("Explique-moi la gravité")
    assert not is_create_app_request("Résume ce document")
    assert not is_create_app_request("C'est parti !")
    assert not is_create_app_request("non je te demande de la créer")  # trop court/vague


# ----------------------------------------------------------------------------
# §P1.1 — chat_agent n'est plus "Caly"
# ----------------------------------------------------------------------------

def test_chat_agent_prompt_not_caly():
    """iter161 §P1.1 — Le prompt système CHAT_AGENT_SYSTEM ne doit PAS commencer
    par 'Tu es Caly'. Caly est réservé au widget flottant uniquement."""
    from agents.registry import CHAT_AGENT_SYSTEM
    assert not CHAT_AGENT_SYSTEM.lstrip().startswith("Tu es Caly"), (
        "BUG: chat_agent se présente encore comme Caly — doit être neutre."
    )
    assert "NE t'appelles PAS Caly" in CHAT_AGENT_SYSTEM, (
        "Le prompt doit explicitement interdire l'identité Caly."
    )


def test_engine_exposes_real_model_in_agent_event():
    """L'event {agent} doit contenir provider+model_id+model_label pour
    que le badge frontend affiche le vrai modèle (pas 'Caly')."""
    import inspect
    from agents import engine
    src = inspect.getsource(engine)
    assert "provider" in src and "model_id" in src and "model_label" in src, (
        "engine.py doit yielder un event agent avec provider/model_id/model_label."
    )
    assert "friendly_model_label" in src, "Le label humain doit être calculé."


def test_friendly_model_label_examples():
    from agents.common import friendly_model_label
    assert friendly_model_label("anthropic", "claude-fable-5") == "Claude 5 Fable"
    assert friendly_model_label("openai", "gpt-5.5") == "GPT 5.5"
    assert friendly_model_label("gemini", "gemini-3.1-pro-preview") == "Gemini 3.1 Pro"


# ----------------------------------------------------------------------------
# §P0.1 — /chat/stream respecte le modèle & remonte erreur SSE
# ----------------------------------------------------------------------------

def test_chat_stream_emergent_returns_ssse_error(session):
    """iter161 §P0.1 — Envoi en /chat/stream avec model=emergent doit renvoyer
    un event SSE {error: {code: ai_integration_not_configured}} au lieu de
    router silencieusement vers un autre modèle."""
    resp = requests.post(
        f"{API}/chat/stream",
        json={"message": "test routing emergent",
              "mode": "online", "language": "fr",
              "model": "emergent"},
        headers=session["headers"], stream=True, timeout=30,
    )
    assert resp.status_code == 200, f"SSE endpoint doit répondre 200, got {resp.status_code}"
    body = b""
    for chunk in resp.iter_content(chunk_size=512):
        body += chunk
        if b'"done":true' in body or b'"done": true' in body:
            break
        if len(body) > 20000:
            break
    text = body.decode("utf-8", errors="replace")
    assert '"error"' in text or '"action":"redirect_to_create"' in text or '"action": "redirect_to_create"' in text, (
        f"Attendu erreur explicite OU redirection, got: {text[:600]!r}"
    )
    if '"error"' in text:
        assert "ai_integration_not_configured" in text, (
            f"Code d'erreur attendu ai_integration_not_configured, got: {text[:600]!r}"
        )


def test_chat_stream_create_app_redirects(session):
    """iter161 §P0.2 — « Tu peux me faire une appli de foot » depuis Chat
    doit renvoyer action=redirect_to_create (pas de bavardage Forge)."""
    resp = requests.post(
        f"{API}/chat/stream",
        json={"message": "Tu peux me faire une application de foot ?",
              "mode": "online", "language": "fr",
              "model": "claude-5-fable"},
        headers=session["headers"], stream=True, timeout=30,
    )
    assert resp.status_code == 200
    body = b""
    for chunk in resp.iter_content(chunk_size=512):
        body += chunk
        if b"redirect_to_create" in body:
            break
        if len(body) > 10000:
            break
    text = body.decode("utf-8", errors="replace")
    assert "redirect_to_create" in text, (
        f"Attendu redirect_to_create, got: {text[:600]!r}"
    )


# ----------------------------------------------------------------------------
# §P0.1 — /ai/generate-complete-app refuse emergent/vexub/lindy (501)
# ----------------------------------------------------------------------------

def test_generate_complete_app_emergent_rejected(session):
    """iter161 §P0.1 — Création avec model=emergent doit renvoyer 501
    ai_integration_not_configured, pas un template silencieux."""
    r = requests.post(
        f"{API}/ai/generate-complete-app",
        json={"description": "une app simple", "mode": "online",
              "language": "fr", "model": "emergent"},
        headers=session["headers"], timeout=15,
    )
    assert r.status_code == 501, f"Attendu 501, got {r.status_code}: {r.text[:300]}"
    body = r.json()
    detail = body.get("detail", {})
    assert detail.get("code") == "ai_integration_not_configured"
    assert detail.get("provider") == "emergent"


# ----------------------------------------------------------------------------
# §P1.2 — Frontend : bandeau « L'IA écrit » caché pendant le streaming
# ----------------------------------------------------------------------------

def test_frontend_chat_hides_ai_typing_indicator_during_stream():
    src = Path("/app/frontend/src/pages/Chat.js").read_text(encoding="utf-8")
    # L'indicateur doit être conditionné à aiRealState !== 'streaming'.
    assert "aiRealState !== 'streaming'" in src, (
        "Chat.js doit cacher la bulle quand les tokens arrivent."
    )
    # Et il ne doit plus mentionner "chat-ai-status-label" (ancienne étiquette texte).
    assert "chat-ai-status-label" not in src, (
        "L'ancienne étiquette texte 'L'IA écrit' doit avoir disparu."
    )


def test_frontend_chat_uses_model_label_from_backend():
    src = Path("/app/frontend/src/pages/Chat.js").read_text(encoding="utf-8")
    assert "agent_model_label" in src, (
        "Chat.js doit stocker le label modèle du backend (iter161)."
    )
    assert "redirect_to_create" in src, (
        "Chat.js doit gérer la bascule vers /create pour les demandes d'app."
    )
    assert "ai_integration_not_configured" in src or "evt.error" in src, (
        "Chat.js doit afficher une erreur UI pour ai_integration_not_configured."
    )


def test_frontend_create_accepts_prefill_prompt():
    src = Path("/app/frontend/src/pages/Create.js").read_text(encoding="utf-8")
    assert "prefillPrompt" in src, "Create.js doit accepter prefillPrompt."
    assert "autoStartedRef" in src, "Create.js doit auto-lancer la génération quand prefill."
    assert "elapsedSec" in src, "Create.js doit afficher un chrono pendant la génération."
