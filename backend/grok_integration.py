"""iter91 — Intégration xAI Grok réelle via API compatible OpenAI.

L'API xAI (https://api.x.ai/v1) est compatible avec le SDK openai Python.
Pour activer Grok réel :
  1) Aller sur https://console.x.ai/ → créer une clé API
  2) Ajouter `XAI_API_KEY=xai-...` dans /app/backend/.env
  3) Restart backend → les modèles `grok-4.3` et `grok-4.20-reasoning` répondront
     directement via l'API xAI au lieu du fallback claude-sonnet.

Si XAI_API_KEY n'est pas définie, `is_xai_available()` retourne False et le code
appelant doit fallback vers un autre provider.
"""
from __future__ import annotations

import os
import asyncio
from typing import Optional


def is_xai_available() -> bool:
    """True si XAI_API_KEY est définie dans l'environnement."""
    return bool(os.environ.get("XAI_API_KEY"))


async def grok_chat(
    prompt: str,
    model: str = "grok-4.3",
    system_message: str = "You are a helpful AI assistant.",
    timeout_sec: int = 60,
) -> str:
    """Envoie un prompt à Grok via l'API xAI (OpenAI-compatible).

    Args:
        prompt: Le message utilisateur.
        model: 'grok-4.3' ou 'grok-4.20-reasoning'.
        system_message: Le prompt système.
        timeout_sec: Timeout réseau.

    Returns:
        La réponse texte de Grok.

    Raises:
        RuntimeError si XAI_API_KEY manquante.
        Exception réseau / timeout si l'API ne répond pas.
    """
    api_key = os.environ.get("XAI_API_KEY")
    if not api_key:
        raise RuntimeError("XAI_API_KEY manquante — Grok non disponible.")

    # Import openai en lazy pour ne pas pénaliser le démarrage du backend si non utilisé.
    try:
        from openai import AsyncOpenAI
    except ImportError as e:
        raise RuntimeError(f"openai SDK requis pour Grok: {e}")

    client = AsyncOpenAI(
        api_key=api_key,
        base_url="https://api.x.ai/v1",
        timeout=float(timeout_sec),
    )

    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt},
                ],
            ),
            timeout=timeout_sec + 5,
        )
        if response.choices and len(response.choices) > 0:
            return response.choices[0].message.content or ""
        return ""
    except asyncio.TimeoutError:
        raise RuntimeError(f"Grok timeout après {timeout_sec}s")


def grok_model_id(short_name: str) -> Optional[str]:
    """Mappe un short name vers le model_id xAI réel."""
    mapping = {
        "grok-4.3": "grok-4.3",
        "grok-4.20-reasoning": "grok-4.20-reasoning",
    }
    return mapping.get(short_name)
