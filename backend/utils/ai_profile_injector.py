"""iter149 — Injecteur de profil IA dans les prompts système.

Charge le profil configuré par la Créa via `/api/agents/profile/save`
(collection `db.ai_profiles`) et le convertit en un fragment de prompt
système qui SURPLONGE le prompt par défaut de l'agent.

RÈGLES ABSOLUES :
  1. Chaque IA conserve sa PROPRE identité — le profil est isolé par
     `agent_id`. Aucun mélange entre agents.
  2. Si un `custom_system_prompt` est défini, il PRÉFIXE le prompt de
     base (il ne l'écrase pas totalement — le rôle de l'agent reste).
  3. Si aucun profil n'est enregistré → aucun ajout (comportement
     historique préservé).
  4. Champs pris en compte (voir ai_programming_routes.py — ALLOWED_FIELDS) :
       writing_style, behavior, domains, limits, capabilities,
       allowed_tools, specializations, custom_system_prompt,
       response_format, reasoning_mode, notes (notes = ignoré à l'exec).

Usage :

    from utils.ai_profile_injector import compose_system_prompt

    base_prompt = CALY_DEFAULT_SYSTEM_PROMPT
    final_prompt = await compose_system_prompt(db, "caly_help", base_prompt)
    chat = LlmChat(..., system_message=final_prompt)
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, Optional


# Cache in-memory optionnel — invalidé automatiquement à chaque save
# (car save() bump `updated_at`). Ici on lit directement à chaque appel
# pour rester simple : le coût MongoDB est négligeable et garantit la
# fraîcheur immédiate après édition.

def _fmt_list(items: Any) -> str:
    if not items:
        return ""
    if isinstance(items, str):
        return items.strip()
    if isinstance(items, (list, tuple, set)):
        cleaned = [str(x).strip() for x in items if str(x).strip()]
        return " · ".join(cleaned)
    return str(items)


def _build_profile_fragment(profile: Dict[str, Any]) -> str:
    """Traduit le profil enregistré en un bloc lisible pour le LLM.

    Chaque section est optionnelle : si le champ est vide, on ne l'ajoute
    pas — évite de polluer le prompt avec des lignes vides.
    """
    if not isinstance(profile, dict) or not profile:
        return ""
    lines = []
    # Le custom_system_prompt vient EN PREMIER (surcharge explicite Créa).
    custom = (profile.get("custom_system_prompt") or "").strip()
    if custom:
        lines.append(custom)
    # Puis les paramètres structurés (chaque IA a sa propre config).
    style = _fmt_list(profile.get("writing_style"))
    if style:
        lines.append(f"STYLE D'ÉCRITURE : {style}")
    behavior = _fmt_list(profile.get("behavior"))
    if behavior:
        lines.append(f"COMPORTEMENT : {behavior}")
    domains = _fmt_list(profile.get("domains"))
    if domains:
        lines.append(f"DOMAINES : {domains}")
    limits = _fmt_list(profile.get("limits"))
    if limits:
        lines.append(f"LIMITES STRICTES : {limits}")
    capabilities = _fmt_list(profile.get("capabilities"))
    if capabilities:
        lines.append(f"CAPACITÉS AUTORISÉES : {capabilities}")
    allowed_tools = _fmt_list(profile.get("allowed_tools"))
    if allowed_tools:
        lines.append(f"OUTILS AUTORISÉS : {allowed_tools}")
    specializations = _fmt_list(profile.get("specializations"))
    if specializations:
        lines.append(f"SPÉCIALISATIONS : {specializations}")
    response_format = _fmt_list(profile.get("response_format"))
    if response_format:
        lines.append(f"FORMAT DE RÉPONSE : {response_format}")
    reasoning_mode = _fmt_list(profile.get("reasoning_mode"))
    if reasoning_mode:
        lines.append(f"MODE DE RAISONNEMENT : {reasoning_mode}")
    if not lines:
        return ""
    return (
        "\n\n=== PROGRAMMATION SPÉCIFIQUE (configurée par la Créa) ===\n"
        + "\n".join(lines)
        + "\n=== FIN DE LA PROGRAMMATION SPÉCIFIQUE ==="
    )


async def load_profile(db, agent_id: str) -> Optional[Dict[str, Any]]:
    """Charge le profil courant. Renvoie None si absent ou base indispo."""
    if not agent_id:
        return None
    try:
        row = await db.ai_profiles.find_one({"agent_id": agent_id}, {"_id": 0})
    except Exception:  # DB indispo → aucune injection, aucun crash
        return None
    if not row:
        return None
    return row.get("profile") or {}


async def compose_system_prompt(
    db, agent_id: str, base_prompt: str,
    *,
    extra_agent_ids: Optional[Iterable[str]] = None,
) -> str:
    """Compose le prompt système final = base + IDENTITÉ REGISTRY + profil enregistré.

    Ordre d'assemblage (iter156 — chaque IA garde son rôle propre) :
      1. `base_prompt` = prompt de base du module (jamais écrasé)
      2. Fragment d'identité issu de `AGENT_REGISTRY[agent_id]` (défaut)
      3. Profil personnalisé configuré par la Créa (surcharge finale)

    Retour : prompt final (str). Si aucun profil configuré ET pas de fiche
    registry : renvoie `base_prompt` inchangé.
    """
    base = base_prompt or ""
    # Couche 2 — identité par défaut extraite de AGENT_REGISTRY.
    identity_frag = build_identity_fragment(agent_id)
    # Couche 3 — profil sur-mesure Créa.
    profile = await load_profile(db, agent_id)
    creator_frag = _build_profile_fragment(profile or {})
    return base + identity_frag + creator_frag


def build_identity_fragment(agent_id: str) -> str:
    """iter156 — Convertit la fiche d'identité `AGENT_REGISTRY[agent_id]`
    en fragment de prompt système. Ce fragment IMPOSE le rôle, l'expertise,
    le format et les outils propres à cet agent — même si la Créa n'a pas
    configuré de profil personnalisé pour ce modèle.

    Garantit qu'une IA spécialisée (Codex, Claude Fable, Grok Reasoning…)
    conserve son identité et ne se comporte PAS comme un ChatGPT générique.
    """
    if not agent_id:
        return ""
    try:
        from agents.registry import AGENT_REGISTRY
        card = AGENT_REGISTRY.get(agent_id)
    except Exception:
        card = None
    if not card:
        return ""
    lines = []
    name = card.get("name", agent_id)
    lines.append(f"IDENTITÉ DE L'AGENT : tu es **{name}** (id `{agent_id}`).")
    if card.get("objectif"):
        lines.append(f"OBJECTIF PROPRE : {card['objectif']}.")
    if card.get("expertise"):
        lines.append(f"EXPERTISE : {card['expertise']}.")
    if card.get("raisonnement"):
        lines.append(f"MODE DE RAISONNEMENT : {card['raisonnement']}.")
    if card.get("format"):
        lines.append(f"FORMAT DE RÉPONSE ATTENDU : {card['format']}.")
    outils = card.get("outils")
    if isinstance(outils, (list, tuple)) and outils:
        lines.append("OUTILS AUTORISÉS : " + " · ".join(str(o) for o in outils) + ".")
    if card.get("limites"):
        lines.append(f"LIMITES STRICTES : {card['limites']}.")
    lines.append(
        "RÈGLE ABSOLUE : conserve TON identité. Ne te comporte pas comme "
        "un chatbot générique. Reste dans ton rôle propre."
    )
    return (
        "\n\n=== IDENTITÉ D'AGENT (registry — NE PAS FUSIONNER) ===\n"
        + "\n".join(lines)
        + "\n=== FIN DE L'IDENTITÉ D'AGENT ==="
    )


async def compose_system_prompt_sync(profile: Dict[str, Any], base_prompt: str) -> str:
    """Variante purement synchrone quand le profil est déjà en main
    (utile pour les tests unitaires)."""
    frag = _build_profile_fragment(profile or {})
    return (base_prompt or "") + frag


def build_profile_fragment(profile: Dict[str, Any]) -> str:
    """Export synchrone pour tests et pour l'injection à chaud dans les
    fonctions déjà synchrones (rare — préférer compose_system_prompt)."""
    return _build_profile_fragment(profile or {})
