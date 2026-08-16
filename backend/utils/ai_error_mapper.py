"""iter158.7 — Chantier 4 : AI Error Mapper (canonique).

Classifie une exception ou une réponse HTTP échouée en une catégorie précise
avec un `code` machine, une `severity`, un `i18n_key` pour l'UI, et un
`log_detail` pour les logs techniques.

Catégories reconnues :
    - cloudflare        : Cloudflare 5xx, page HTML, "bad gateway", "gateway timeout"
    - ollama_offline    : Ollama absent (localhost:11434 non joignable) ou modèle manquant
    - ollama_error      : Ollama joignable mais renvoie une erreur applicative
    - timeout           : asyncio.TimeoutError, requests.Timeout, TimeoutError, HTTP 504
    - json_invalid      : JSONDecodeError ou réponse non-JSON attendue en JSON
    - auth_error        : 401/403 fournisseur (clé API absente/invalide)
    - rate_limit        : 429 fournisseur, quota dépassé
    - provider_error    : 500 fournisseur (Anthropic, OpenAI...) non-Cloudflare
    - network           : ConnectionError, DNS, socket
    - unknown           : tout le reste

L'appelant DOIT logger `log_detail` (technique brut) via `logger.warning/error`
et retourner à l'utilisateur `{error_code, i18n_key, message_fr}` — jamais
la trace brute (spec CDC : « ne pas masquer une erreur réelle derrière un
message générique »).
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Dict, Optional, Union

# Regex de détection (case-insensitive)
_CF_RE = re.compile(
    r"cloudflare|<!doctype|<html|cf-ray|bad gateway|gateway time|service unavailable",
    re.IGNORECASE,
)
_OLLAMA_OFFLINE_RE = re.compile(
    r"ollama.*not.*available|connection refused|11434|no such host|localhost:11434|ollama absent|ollama unreachable",
    re.IGNORECASE,
)
_OLLAMA_MODEL_MISSING_RE = re.compile(
    r"model.*not found|pull the model|model.*missing|not.*downloaded",
    re.IGNORECASE,
)


def _to_str(x: Any) -> str:
    try:
        return str(x) if x is not None else ""
    except Exception:
        return ""


def classify_ai_error(
    exc: Optional[BaseException] = None,
    *,
    http_status: Optional[int] = None,
    raw_body: Any = None,
    provider: Optional[str] = None,
    context: Optional[str] = None,
) -> Dict[str, Any]:
    """Retourne un dict standardisé :
      {
        code:        "cloudflare" | "ollama_offline" | "ollama_error" |
                     "timeout" | "json_invalid" | "auth_error" | "rate_limit" |
                     "provider_error" | "network" | "unknown"
        i18n_key:    "ai_err_<code>"
        message_fr:  "Message fallback en français"
        severity:    "warning" | "error" | "critical"
        log_detail:  "..." (trace brute, à logger côté serveur, PAS à l'UI)
        http_status: int|None (rétro-info)
        provider:    str|None
      }
    """
    log_parts = []
    if provider:
        log_parts.append(f"provider={provider}")
    if context:
        log_parts.append(f"ctx={context}")
    if http_status is not None:
        log_parts.append(f"status={http_status}")
    if exc is not None:
        log_parts.append(f"exc={type(exc).__name__}: {_to_str(exc)[:400]}")
    raw_str = _to_str(raw_body)[:800]
    if raw_str:
        log_parts.append(f"body={raw_str}")
    log_detail = " | ".join(log_parts)

    # 1) Timeout — priorité haute (souvent avant même d'avoir un body)
    if exc is not None:
        if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
            return _mk("timeout", 504, log_detail, provider)
        # httpx / requests timeout classes (sans les importer)
        cn = type(exc).__name__.lower()
        if "timeout" in cn:
            return _mk("timeout", 504, log_detail, provider)
        if "jsondecode" in cn or "json.decoder" in _to_str(exc).lower():
            return _mk("json_invalid", http_status, log_detail, provider)
        if "connection" in cn and "refused" in _to_str(exc).lower():
            # Ollama local absent
            if "11434" in _to_str(exc) or (provider or "").lower() == "ollama":
                return _mk("ollama_offline", None, log_detail, provider)
            return _mk("network", None, log_detail, provider)
        if isinstance(exc, ConnectionError):
            return _mk("network", None, log_detail, provider)

    if http_status == 504:
        return _mk("timeout", 504, log_detail, provider)

    # 2) Cloudflare — détection par body OU status ambigus
    if raw_str and _CF_RE.search(raw_str):
        return _mk("cloudflare", http_status or 503, log_detail, provider)

    # 3) Ollama-spécifique
    if raw_str and (provider or "").lower() == "ollama":
        if _OLLAMA_MODEL_MISSING_RE.search(raw_str):
            return _mk("ollama_error", http_status, log_detail, provider)
        return _mk("ollama_error", http_status, log_detail, provider)
    if raw_str and _OLLAMA_OFFLINE_RE.search(raw_str):
        return _mk("ollama_offline", None, log_detail, provider)

    # 4) Auth
    if http_status in (401, 403):
        return _mk("auth_error", http_status, log_detail, provider)

    # 5) Rate limit
    if http_status == 429:
        return _mk("rate_limit", 429, log_detail, provider)

    # 6) JSON invalide (autre origine)
    if raw_str and http_status and 200 <= http_status < 300:
        # Réponse HTTP OK mais body non-JSON attendu
        try:
            json.loads(raw_str)
        except Exception:
            return _mk("json_invalid", http_status, log_detail, provider)

    # 7) Provider error (5xx hors CF)
    if http_status and 500 <= http_status < 600:
        return _mk("provider_error", http_status, log_detail, provider)

    # 8) Client error 4xx
    if http_status and 400 <= http_status < 500:
        return _mk("provider_error", http_status, log_detail, provider)

    return _mk("unknown", http_status, log_detail, provider)


def _mk(code: str, status: Optional[int], log_detail: str,
        provider: Optional[str]) -> Dict[str, Any]:
    return {
        "code": code,
        "i18n_key": f"ai_err_{code}",
        "message_fr": _FR_MESSAGES.get(code, _FR_MESSAGES["unknown"]),
        "severity": _SEVERITY.get(code, "error"),
        "log_detail": log_detail,
        "http_status": status,
        "provider": provider,
    }


# Messages FR fallback (utilisés si le client n'a pas d'i18n dispo).
_FR_MESSAGES = {
    "cloudflare": ("Le service IA est momentanément surchargé côté Cloudflare. "
                   "Réessaie dans quelques instants — ta demande n'a pas été perdue."),
    "ollama_offline": ("Ollama n'est pas joignable (mode offline). Vérifie que "
                       "l'application locale Ollama est bien démarrée sur ta machine "
                       "et que le modèle est installé."),
    "ollama_error": ("Ollama a répondu avec une erreur. Vérifie que le modèle "
                     "demandé est disponible (`ollama pull …`)."),
    "timeout": ("La réponse de l'IA a mis trop de temps à arriver (timeout). "
                "Réessaie ; si le problème persiste, allège ta demande."),
    "json_invalid": ("L'IA a renvoyé une réponse dans un format inattendu. "
                     "Réessaie — le prompt sera re-soumis."),
    "auth_error": ("Clé d'accès IA absente ou invalide côté serveur. "
                   "Contacte le créateur — aucune action de ton côté n'est nécessaire."),
    "rate_limit": ("Trop de requêtes IA récemment (rate limit du fournisseur). "
                   "Réessaie dans une minute."),
    "provider_error": ("Le fournisseur IA a répondu avec une erreur temporaire. "
                       "Réessaie dans quelques instants."),
    "network": ("Problème de connexion réseau côté serveur pour joindre l'IA. "
                "Réessaie ; si le problème persiste, préviens le créateur."),
    "unknown": ("Une erreur est survenue pendant la génération. "
                "Réessaie dans un instant."),
}

_SEVERITY = {
    "cloudflare": "warning",
    "ollama_offline": "warning",
    "ollama_error": "warning",
    "timeout": "warning",
    "json_invalid": "warning",
    "auth_error": "critical",  # ne doit jamais arriver en prod
    "rate_limit": "warning",
    "provider_error": "error",
    "network": "error",
    "unknown": "error",
}


__all__ = ["classify_ai_error"]
