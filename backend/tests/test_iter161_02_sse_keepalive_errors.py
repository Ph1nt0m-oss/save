"""Chantier iter161 — Diagnostic + arrêt sécurisé (passe 3).

Tests obligatoires :
- /chat/stream émet un event SSE `error` STRUCTURÉ (code + done:true) en
  cas d'erreur Cloudflare / timeout / provider — pas un delta générique.
- Le backend émet des commentaires `: keepalive\n\n` toutes les 15s tant
  qu'aucun delta réel n'est arrivé → empêche l'ingress/Cloudflare de
  couper la connexion sur modèles lents (60-120s avant 1er token).
- Chat.js gère les codes classifiés (cloudflare, timeout, provider_error,
  rate_limit, auth_error, network) et arrête le spinner en même temps
  qu'il affiche l'erreur.
"""
from __future__ import annotations

from pathlib import Path


def test_backend_chat_stream_has_keepalive():
    """iter161 §diag — Le pipeline SSE doit émettre des keepalives tant
    qu'aucun delta n'est arrivé, pour empêcher l'ingress/Cloudflare de
    couper la connexion sur modèles lents (Claude Fable 5, GPT-5 complex)."""
    src = Path("/app/backend/routes/chat_advanced_routes.py").read_text(encoding="utf-8")
    assert ": keepalive\\n\\n" in src, (
        "Le SSE doit yielder des commentaires `: keepalive\\n\\n` pour "
        "empêcher le proxy de couper les connexions sur modèles lents."
    )
    assert "got_first_delta" in src, (
        "Doit tracker si un vrai delta est déjà passé, pour ne pulser "
        "qu'avant le premier token."
    )
    assert "wait_for" in src and "timeout=15" in src, (
        "Doit utiliser asyncio.wait_for(queue.get(), timeout=15) pour "
        "le battement de 15s."
    )


def test_backend_chat_stream_emits_structured_error():
    """iter161 §diag — En cas d'erreur backend, émettre un event SSE
    `{error: {code, message, http_status, provider}, done:true}`
    PAS un delta générique « service indisponible »."""
    src = Path("/app/backend/routes/chat_advanced_routes.py").read_text(encoding="utf-8")
    assert "classify_ai_error" in src, (
        "Le except Exception doit classifier l'erreur via ai_error_mapper."
    )
    assert "chat_stream_pipeline" in src, (
        "Le contexte de classification doit être tracé pour le diagnostic."
    )
    # Plus de fallback delta générique dans le flux agent.
    assert "service de chat est momentanément indisponible" not in src, (
        "Le fallback delta générique doit être remplacé par un event error structuré."
    )


def test_frontend_chat_handles_cloudflare_timeout_errors():
    """iter161 §diag — Chat.js doit mapper les codes serveur (cloudflare,
    timeout, provider_error, rate_limit, auth_error, network) en messages
    utilisateur localisés, et arrêter le spinner."""
    src = Path("/app/frontend/src/pages/Chat.js").read_text(encoding="utf-8")
    for code in ["cloudflare:", "timeout:", "provider_error:",
                 "rate_limit:", "auth_error:", "network:"]:
        assert code in src, f"Chat.js doit mapper le code {code!r} en message UI."
    assert "setAiRealState('error')" in src, (
        "L'état aiRealState doit passer en 'error' pour feedback visuel."
    )


def test_ai_error_mapper_classifies_cloudflare():
    """Le mapper doit détecter Cloudflare dans un payload HTML/body."""
    import sys
    sys.path.insert(0, "/app/backend")
    from utils.ai_error_mapper import classify_ai_error

    info = classify_ai_error(
        exc=None,
        raw_body="<!DOCTYPE html><html><body>cf-ray: xxx bad gateway cloudflare</body></html>",
        http_status=503,
        provider="anthropic", context="test",
    )
    assert info["code"] == "cloudflare", f"got {info['code']}"


def test_ai_error_mapper_classifies_timeout():
    import sys
    sys.path.insert(0, "/app/backend")
    from utils.ai_error_mapper import classify_ai_error
    info = classify_ai_error(
        exc=None, raw_body="gateway timeout",
        http_status=504, provider="openai", context="test",
    )
    assert info["code"] == "timeout"
