"""iter129 — Helpers partagés du package agents (LLM, historique, langues).

Chantier iter161 §P0.1 — Mapping EXACT du modèle sélectionné par
l'utilisateur. L'ancienne logique « claude-* → claude-sonnet-4-5 », tout
le reste → gpt-4o-mini écrasait silencieusement le choix de l'utilisateur
et violait la règle « AI Truth ». La nouvelle version :
  • Mappe chaque identifiant frontend à son provider:model_id exact.
  • Lève AIModelUnavailable (501) pour les intégrations non branchées
    (emergent, vexub-video, lindy-flow) et pour grok-* si XAI_API_KEY
    n'est pas définie.
  • Interdit toute bascule silencieuse vers un autre provider.
"""
import os
import logging
import uuid
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

from fastapi import HTTPException

from orchestrator import _safe_json  # noqa: F401

logger = logging.getLogger(__name__)

LANG_LABELS = {
    "fr": "français", "en": "English", "es": "español", "pt": "português",
    "de": "Deutsch", "nl": "Nederlands", "ru": "русский",
    "zh": "中文（简体）", "zh-tw": "中文（繁體）", "hi": "हिन्दी", "ja": "日本語",
}


def lang_label(language: Optional[str]) -> str:
    return LANG_LABELS.get((language or "fr").lower(), "français")


# ---------------------------------------------------------------------------
# iter161 — MAPPING EXACT frontend_id → (provider, model_id).
# Toute entrée doit être le même id que celui envoyé par le ModelPicker.
# L'ordre déclaratif ici est la *source de vérité* unique pour /chat/stream,
# /ai/generate-complete-app et les tests.
# ---------------------------------------------------------------------------
MODEL_ROUTES: Dict[str, Tuple[str, str]] = {
    # OpenAI
    "gpt-5.2":         ("openai",    "gpt-5.2"),
    "gpt-5.1":         ("openai",    "gpt-5.1"),
    "gpt-5":           ("openai",    "gpt-5"),
    "gpt-5.5":         ("openai",    "gpt-5.5"),
    "gpt-5.4":         ("openai",    "gpt-5.4"),
    "gpt-5.4-1m":      ("openai",    "gpt-5.4-1m"),
    "gpt-5.3-codex":   ("openai",    "gpt-5.3-codex"),
    "o3":              ("openai",    "o3"),
    "gpt-4o":          ("openai",    "gpt-4o"),
    "gpt-4o-mini":     ("openai",    "gpt-4o-mini"),

    # Anthropic
    "claude-sonnet":        ("anthropic", "claude-sonnet-4-5-20250929"),
    "claude-sonnet-4.5":    ("anthropic", "claude-sonnet-4-5-20250929"),
    "claude-sonnet-4.6":    ("anthropic", "claude-sonnet-4-6"),
    "claude-sonnet-4.6-1m": ("anthropic", "claude-sonnet-4-6-1m"),
    "claude-4.5-sonnet":    ("anthropic", "claude-sonnet-4-5-20250929"),
    "claude-4.6-sonnet":    ("anthropic", "claude-sonnet-4-6"),
    "claude-4.6-sonnet-1m": ("anthropic", "claude-sonnet-4-6-1m"),
    "claude-opus":          ("anthropic", "claude-opus-4-5-20251101"),
    "claude-opus-4.5":      ("anthropic", "claude-opus-4-5-20251101"),
    "claude-opus-4.6":      ("anthropic", "claude-opus-4-6"),
    "claude-opus-4.6-1m":   ("anthropic", "claude-opus-4-6-1m"),
    "claude-opus-4.7":      ("anthropic", "claude-opus-4-7"),
    "claude-opus-4.7-1m":   ("anthropic", "claude-opus-4-7-1m"),
    "claude-opus-4.8":      ("anthropic", "claude-opus-4-8"),
    "claude-4.5-opus":      ("anthropic", "claude-opus-4-5-20251101"),
    "claude-4.6-opus":      ("anthropic", "claude-opus-4-6"),
    "claude-4.6-opus-1m":   ("anthropic", "claude-opus-4-6-1m"),
    "claude-4.7-opus":      ("anthropic", "claude-opus-4-7"),
    "claude-4.7-opus-1m":   ("anthropic", "claude-opus-4-7-1m"),
    "claude-4.8-opus":      ("anthropic", "claude-opus-4-8"),
    "claude-haiku":         ("anthropic", "claude-haiku-4-5-20251001"),
    "claude-fable":         ("anthropic", "claude-fable-5"),
    "claude-fable-5":       ("anthropic", "claude-fable-5"),
    "claude-5-fable":       ("anthropic", "claude-fable-5"),

    # Gemini
    "gemini-3-pro":   ("gemini", "gemini-3.1-pro-preview"),
    "gemini-3.1-pro": ("gemini", "gemini-3.1-pro-preview"),
    "gemini-3-flash": ("gemini", "gemini-3-flash-preview"),
    "gemini-2.5-pro": ("gemini", "gemini-2.5-pro"),

    # xAI (Grok) — requiert XAI_API_KEY côté backend
    "grok-4.3":            ("xai", "grok-4.3"),
    "grok-4.20-reasoning": ("xai", "grok-4.20-reasoning"),

    # ----- Intégrations déclarées mais SANS handler réel : erreur explicite -----
    "emergent":          ("emergent", "collab"),
    "emergent-collab":   ("emergent", "collab"),
    "vexub-video":       ("vexub",    "video"),
    "lindy-flow":        ("lindy",    "flow"),
}

# Providers sans intégration réelle : réponse 501 explicite, pas de fallback.
UNSUPPORTED_PROVIDERS = {"emergent", "vexub", "lindy"}


class AIModelUnavailable(HTTPException):
    """Levée quand le modèle sélectionné n'a pas de handler réel branché.

    Le frontend reçoit un 501 structuré avec `code`, `requested_model` et
    `provider` pour afficher une erreur honnête (pas de bascule silencieuse).
    """

    def __init__(self, *, code: str, requested_model: str, provider: str,
                 message: str, status_code: int = 501):
        super().__init__(status_code=status_code, detail={
            "code": code,
            "requested_model": requested_model,
            "provider": provider,
            "message": message,
        })


def resolve_model(requested: Optional[str], *, strict: bool = True) -> Tuple[str, str]:
    """Retourne (provider, model_id) EXACT pour l'id frontend demandé.

    `strict=True` (défaut) → lève AIModelUnavailable pour les providers
    non branchés (emergent, vexub, lindy) et pour grok-* sans XAI_API_KEY.
    `strict=False` → retourne tel quel (utilisé par les helpers internes
    qui ont besoin d'un modèle technique léger, ex. router gpt-4o-mini).
    """
    r = (requested or "").strip().lower()
    if not r:
        # Pas de modèle demandé — défaut raisonnable Anthropic Sonnet 4.5.
        return ("anthropic", "claude-sonnet-4-5-20250929")

    route = MODEL_ROUTES.get(r)
    if route is None:
        if strict:
            raise AIModelUnavailable(
                code="ai_model_unknown",
                requested_model=r,
                provider="unknown",
                message=f"Modèle « {r} » inconnu. Choisis un modèle supporté dans la liste.",
            )
        return ("anthropic", "claude-sonnet-4-5-20250929")

    provider, model_id = route
    if not strict:
        return provider, model_id

    if provider in UNSUPPORTED_PROVIDERS:
        raise AIModelUnavailable(
            code="ai_integration_not_configured",
            requested_model=r,
            provider=provider,
            message=(
                f"Intégration {provider} non configurée — ce modèle n'a pas "
                f"de handler réel branché. Choisis OpenAI, Anthropic, Gemini "
                f"ou Grok (si XAI_API_KEY définie)."
            ),
        )
    if provider == "xai" and not os.environ.get("XAI_API_KEY"):
        raise AIModelUnavailable(
            code="ai_grok_key_missing",
            requested_model=r,
            provider="xai",
            message=(
                "Grok (xAI) sélectionné mais XAI_API_KEY absente du backend. "
                "Ajoute une clé xAI dans /app/backend/.env pour activer ce modèle."
            ),
        )
    return provider, model_id


def friendly_model_label(provider: str, model_id: str) -> str:
    """Libellé humain pour affichage frontend (badge au-dessus des messages)."""
    labels = {
        "gpt-5.5":        "GPT 5.5",
        "gpt-5.4":        "GPT 5.4",
        "gpt-5.4-1m":     "GPT 5.4 (1M)",
        "gpt-5.3-codex":  "GPT 5.3 Codex",
        "gpt-5.2":        "GPT 5.2",
        "gpt-5.1":        "GPT 5.1",
        "gpt-5":          "GPT 5",
        "gpt-4o":         "GPT 4o",
        "gpt-4o-mini":    "GPT 4o mini",
        "o3":             "o3",
        "claude-fable-5":              "Claude 5 Fable",
        "claude-sonnet-4-5-20250929":  "Claude 4.5 Sonnet",
        "claude-sonnet-4-6":           "Claude 4.6 Sonnet",
        "claude-sonnet-4-6-1m":        "Claude 4.6 Sonnet (1M)",
        "claude-opus-4-5-20251101":    "Claude 4.5 Opus",
        "claude-opus-4-6":             "Claude 4.6 Opus",
        "claude-opus-4-6-1m":          "Claude 4.6 Opus (1M)",
        "claude-opus-4-7":             "Claude 4.7 Opus",
        "claude-opus-4-7-1m":          "Claude 4.7 Opus (1M)",
        "claude-opus-4-8":             "Claude 4.8 Opus",
        "claude-haiku-4-5-20251001":   "Claude 4.5 Haiku",
        "gemini-3.1-pro-preview":  "Gemini 3.1 Pro",
        "gemini-3-flash-preview":  "Gemini 3 Flash",
        "gemini-2.5-pro":          "Gemini 2.5 Pro",
        "grok-4.3":            "Grok 4.3",
        "grok-4.20-reasoning": "Grok 4.20 Reasoning",
    }
    return labels.get(model_id, f"{provider}:{model_id}")


def format_history(history: Optional[List[Dict[str, Any]]], max_chars: int = 2600) -> str:
    """Formate l'historique de conversation pour la mémoire des agents."""
    if not history:
        return ""
    lines = []
    for m in history[-12:]:
        role = "Utilisateur" if m.get("role") == "user" else "Assistant"
        content = (m.get("content") or "").strip().replace("\n", " ")
        if content:
            lines.append(f"{role}: {content[:400]}")
    text = "\n".join(lines)
    return text[-max_chars:]


async def llm_json(system: str, prompt: str, *, session_id: str,
                   provider: str = "anthropic", model_id: str = "claude-sonnet-4-5") -> Dict[str, Any]:
    """Appel one-shot avec parsing JSON tolérant.

    iter158.7 — Chantier 4 : classifie précisément l'erreur (Cloudflare,
    Ollama, timeout, JSON invalide, provider) et log le `log_detail`
    technique tout en retournant un dict avec `_error_code` pour permettre
    aux appelants de propager la catégorie à l'UI.
    """
    key = os.environ.get("EMERGENT_LLM_KEY")
    if not key:
        return {"_error_code": "auth_error"}
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(api_key=key, session_id=f"{session_id}_{uuid.uuid4().hex[:6]}",
                       system_message=system).with_model(provider, model_id)
        out = await chat.send_message(UserMessage(text=prompt))
        return _safe_json(str(out or ""))
    except Exception as e:
        try:
            from utils.ai_error_mapper import classify_ai_error
            info = classify_ai_error(e, provider=provider, context="agents.llm_json")
            logger.warning(f"agents llm_json failure [{info['code']}]: {info['log_detail']}")
            return {"_error_code": info["code"]}
        except Exception:
            logger.warning(f"agents llm_json failure: {e}")
            return {"_error_code": "unknown"}


async def stream_llm(system: str, prompt: str, *, session_id: str,
                     provider: str, model_id: str) -> AsyncIterator[str]:
    """Streaming natif token-par-token via emergentintegrations.

    iter158.7 — Chantier 4 : en cas d'erreur pendant le stream, log précis
    de la catégorie (Cloudflare, timeout, JSON, provider…). L'erreur est
    ré-levée pour que l'endpoint SSE puisse la traduire pour l'UI.
    """
    from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta, StreamDone
    chat = LlmChat(api_key=os.environ.get("EMERGENT_LLM_KEY"),
                   session_id=session_id, system_message=system).with_model(provider, model_id)
    try:
        async for event in chat.stream_message(UserMessage(text=prompt)):
            if isinstance(event, TextDelta):
                if event.content:
                    yield event.content
            elif isinstance(event, StreamDone):
                break
    except Exception as e:
        try:
            from utils.ai_error_mapper import classify_ai_error
            info = classify_ai_error(e, provider=provider, context="agents.stream_llm")
            logger.warning(f"agents stream_llm failure [{info['code']}]: {info['log_detail']}")
        except Exception:
            logger.warning(f"agents stream_llm failure: {e}")
        raise
