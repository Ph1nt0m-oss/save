"""iter129 — Helpers partagés du package agents (LLM, historique, langues)."""
import os
import logging
import uuid
from typing import Any, AsyncIterator, Dict, List, Optional

from orchestrator import _safe_json  # noqa: F401

logger = logging.getLogger(__name__)

LANG_LABELS = {
    "fr": "français", "en": "English", "es": "español", "pt": "português",
    "de": "Deutsch", "nl": "Nederlands", "ru": "русский",
    "zh": "中文（简体）", "zh-tw": "中文（繁體）", "hi": "हिन्दी", "ja": "日本語",
}


def lang_label(language: Optional[str]) -> str:
    return LANG_LABELS.get((language or "fr").lower(), "français")


def resolve_model(requested: Optional[str]):
    """Même mapping que /chat/stream historique — préférence utilisateur respectée."""
    r = (requested or "").strip().lower()
    if r.startswith("claude") or "anthropic" in r:
        return "anthropic", "claude-sonnet-4-5-20250929"
    if r.startswith("gemini"):
        return "gemini", "gemini-3-flash-preview"
    return "openai", "gpt-4o-mini"


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
    """Appel one-shot avec parsing JSON tolérant."""
    key = os.environ.get("EMERGENT_LLM_KEY")
    if not key:
        return {}
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(api_key=key, session_id=f"{session_id}_{uuid.uuid4().hex[:6]}",
                       system_message=system).with_model(provider, model_id)
        out = await chat.send_message(UserMessage(text=prompt))
        return _safe_json(str(out or ""))
    except Exception as e:
        logger.warning(f"agents llm_json failure: {e}")
        return {}


async def stream_llm(system: str, prompt: str, *, session_id: str,
                     provider: str, model_id: str) -> AsyncIterator[str]:
    """Streaming natif token-par-token via emergentintegrations."""
    from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta, StreamDone
    chat = LlmChat(api_key=os.environ.get("EMERGENT_LLM_KEY"),
                   session_id=session_id, system_message=system).with_model(provider, model_id)
    async for event in chat.stream_message(UserMessage(text=prompt)):
        if isinstance(event, TextDelta):
            if event.content:
                yield event.content
        elif isinstance(event, StreamDone):
            break
