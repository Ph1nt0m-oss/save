"""iter142 / iter147 — Bots analyseurs et journal d'anonymat.

Architecture hybride EN DEUX COUCHES INDÉPENDANTES :
  - **Couche 1 (déterministe, PRIMAIRE, TOUJOURS active)** : règles
    locales rapides et fiables (spam patterns, flood, répétition,
    mots-clés suspects, copier-coller massif, mentions en rafale).
  - **Couche 2 (LLM Emergent, SECONDE PASSE, optionnelle)** : détecte
    le harcèlement subtil que les règles keyword-based manquent
    (ironie, moquerie, exclusion, insultes voilées).

RÈGLE ABSOLUE : la couche 2 ne remplace JAMAIS la couche 1. Les deux
analyses sont indépendantes et sont loguées séparément dans le rapport
final (`layer_local` + `layer_llm`). Un échec LLM ne pénalise jamais
l'analyse déterministe.

Rôle :
  - Analyse chaque message envoyé, calcule un score de suspicion 0-100
    combiné (max des deux couches).
  - Si > SUSPICION_THRESHOLD : marque le groupe comme "en état
    suspicion" → autorise le staff (modo/admin/créa) présent à activer
    temporairement le Mode Soleil (voir les vrais pseudos) pour ce
    groupe.
  - Dans un groupe SANS staff : émet une "demande d'intervention" visible
    par le groupe (notification anonyme "surveillance déclenchée, un
    membre du staff va être notifié").
"""
from __future__ import annotations

import os
import re
import asyncio
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# ------------------------------------------------------------------
# Règles locales — Couche 1
# ------------------------------------------------------------------

# Liste courte de mots-clés spam FR/EN — extensible via config plus tard.
SUSPICIOUS_KEYWORDS = {
    # spam / hameçonnage / arnaque
    "gagnez", "gratuit maintenant", "cliquez vite", "argent facile",
    "casino", "porn", "sex", "free bitcoin", "click here",
    # harcèlement basique
    "connard", "salope", "pute", "enculé", "va crever",
}

# Fenêtre de rafales : nombre max de messages par utilisateur dans les
# 30 dernières secondes.
FLOOD_WINDOW_SEC = 30
FLOOD_MAX = 6

# Répétition : si un même message contenu apparait ≥ REPEAT_THRESHOLD fois
# dans les 5 derniers messages d'un même auteur.
REPEAT_THRESHOLD = 3
REPEAT_LOOKBACK = 5

# Copier-coller massif : longueur brute > 800 chars et % de répétition
# de séquences internes > 40%.
MASSIVE_PASTE_LEN = 800

# Seuil global au-delà duquel on considère le message "suspect".
SUSPICION_THRESHOLD = 60

# Recent messages per (group_type, key_id) — used for flood/repeat.
# Kept in-memory ; non-persistent (redéploiement = reset).
_recent_by_user: Dict[Tuple[str, str], deque] = defaultdict(lambda: deque(maxlen=20))


def _keyword_score(content: str) -> int:
    lc = content.lower()
    hits = sum(1 for kw in SUSPICIOUS_KEYWORDS if kw in lc)
    return min(hits * 25, 60)  # jusqu'à 60


def _flood_score(group_type: str, key_id: str, now_ts: float) -> int:
    dq = _recent_by_user[(group_type, key_id)]
    # Purge les anciens.
    while dq and (now_ts - dq[0]) > FLOOD_WINDOW_SEC:
        dq.popleft()
    dq.append(now_ts)
    if len(dq) >= FLOOD_MAX:
        return 40
    if len(dq) >= FLOOD_MAX - 2:
        return 20
    return 0


_recent_content: Dict[Tuple[str, str], deque] = defaultdict(lambda: deque(maxlen=REPEAT_LOOKBACK))


def _repeat_score(group_type: str, key_id: str, content: str) -> int:
    dq = _recent_content[(group_type, key_id)]
    dq.append(content.strip().lower())
    count = sum(1 for c in dq if c == content.strip().lower())
    if count >= REPEAT_THRESHOLD:
        return 35
    return 0


def _paste_score(content: str) -> int:
    if len(content) < MASSIVE_PASTE_LEN:
        return 0
    # Rough compressibility heuristic — number of unique 20-char chunks.
    chunks = [content[i:i + 20] for i in range(0, len(content), 20)]
    if not chunks:
        return 0
    ratio = len(set(chunks)) / max(len(chunks), 1)
    if ratio < 0.4:
        return 40
    if ratio < 0.6:
        return 20
    return 0


def _mention_flood_score(content: str) -> int:
    """Trop de mentions @handle dans un seul message = spam probable."""
    mentions = re.findall(r"@[A-Za-z0-9_.-]{3,24}", content)
    if len(mentions) >= 6:
        return 30
    if len(mentions) >= 4:
        return 15
    return 0


def analyze_message(
    *, group_type: str, key_id: str, content: str, now_ts: Optional[float] = None,
) -> Dict[str, Any]:
    """iter142 — Analyse locale (COUCHE 1 DÉTERMINISTE PRIMAIRE).

    Toujours active. Retourne :
        {
          "score": 0-100,
          "suspicion": bool,
          "reasons": [str, ...],
          "layer": "local"
        }
    """
    import time
    if now_ts is None:
        now_ts = time.time()
    reasons: List[str] = []
    score = 0
    kw = _keyword_score(content)
    if kw:
        score += kw
        reasons.append("mots-clés suspects")
    fl = _flood_score(group_type, key_id, now_ts)
    if fl:
        score += fl
        reasons.append("rafale de messages")
    rp = _repeat_score(group_type, key_id, content)
    if rp:
        score += rp
        reasons.append("répétition")
    pa = _paste_score(content)
    if pa:
        score += pa
        reasons.append("copier-coller massif")
    mn = _mention_flood_score(content)
    if mn:
        score += mn
        reasons.append("mentions en rafale")
    score = min(score, 100)
    return {
        "score": score,
        "suspicion": score >= SUSPICION_THRESHOLD,
        "reasons": reasons,
        "layer": "local",
    }


# ------------------------------------------------------------------
# COUCHE 2 — Emergent LLM (harcèlement subtil)
# ------------------------------------------------------------------
# Cette couche est INDÉPENDANTE et n'annule jamais la couche 1.
# Elle détecte : ironie, moquerie, exclusion sociale, insultes voilées,
# menaces implicites, sarcasme méchant — patterns que les règles
# keyword-based manquent.

_LLM_ENABLED_DEFAULT = True  # peut être coupée via env CODEFORGE_LLM_MOD_DISABLED=1

_LLM_SYSTEM_PROMPT = (
    "Tu es un modérateur bot de chat, spécialisé dans la détection de "
    "HARCÈLEMENT SUBTIL en français et en anglais. Tu analyses UN SEUL "
    "message issu d'un tchat de groupe. Tu ne cherches PAS le spam ou "
    "les insultes directes (déjà couverts par une autre couche). "
    "Concentre-toi sur : moquerie, ironie méchante, exclusion, "
    "menaces voilées, sarcasme agressif, condescendance humiliante, "
    "harcèlement passif-agressif, insinuations. "
    "Réponds STRICTEMENT en JSON compact sur UNE ligne, sans prose : "
    "{\"is_suspicious\":true|false,\"score\":0-100,\"reasons\":[\"...\"]}. "
    "Le score doit refléter la gravité du harcèlement subtil détecté "
    "(0=aucun, 60=doute sérieux, 100=harcèlement clair). "
    "Si aucun signal subtil : is_suspicious=false, score<40, reasons=[]. "
    "Aucune explication en dehors du JSON."
)


async def _llm_analyze_subtle(content: str) -> Optional[Dict[str, Any]]:
    """Appelle Emergent LLM (Claude Sonnet 4.6) pour détecter le
    harcèlement subtil. Retourne le dict {is_suspicious, score, reasons}
    ou None si LLM indisponible / erreur.

    IMPORTANT : cette fonction ne lève JAMAIS d'exception vers l'appelant.
    """
    if os.environ.get("CODEFORGE_LLM_MOD_DISABLED", "").strip() in ("1", "true", "yes"):
        return None
    api_key = os.environ.get("EMERGENT_LLM_KEY", "").strip()
    if not api_key:
        return None
    # Message court → pas la peine d'appeler le LLM (bruit + coût).
    trimmed = (content or "").strip()
    if len(trimmed) < 8:
        return None
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(
            api_key=api_key,
            session_id=f"mod-{datetime.now(timezone.utc).timestamp()}",
            system_message=_LLM_SYSTEM_PROMPT,
        ).with_model("anthropic", "claude-sonnet-4-6")
        # send_message est utilisé volontairement ici (analyse ponctuelle,
        # PAS un chat utilisateur — pas de streaming attendu).
        msg = UserMessage(text=f"Message à analyser : «{trimmed[:1200]}»")
        # Timeout de sécurité 6s pour ne jamais bloquer l'envoi de message.
        raw = await asyncio.wait_for(chat.send_message(msg), timeout=6.0)
        text = (raw or "").strip()
        if not text:
            return None
        # Extract JSON (le modèle peut parfois ajouter un mini wrapper).
        import json as _json
        m = re.search(r"\{[^{}]*\}", text)
        blob = m.group(0) if m else text
        data = _json.loads(blob)
        is_sus = bool(data.get("is_suspicious", False))
        raw_score = data.get("score", 0)
        try:
            score = max(0, min(100, int(raw_score)))
        except (TypeError, ValueError):
            score = 0
        reasons = data.get("reasons") or []
        if not isinstance(reasons, list):
            reasons = [str(reasons)]
        reasons = [str(r)[:120] for r in reasons[:5]]
        return {
            "layer": "llm",
            "provider": "emergent:anthropic:claude-sonnet-4-6",
            "is_suspicious": is_sus,
            "score": score,
            "reasons": reasons,
        }
    except asyncio.TimeoutError:
        return {"layer": "llm", "error": "timeout"}
    except Exception as e:  # pragma: no cover — silent fail
        return {"layer": "llm", "error": str(e)[:120]}


async def analyze_message_combined(
    *, group_type: str, key_id: str, content: str,
    now_ts: Optional[float] = None,
    call_llm: bool = True,
) -> Dict[str, Any]:
    """iter147 — Analyse combinée en 2 couches INDÉPENDANTES.

    Retourne :
        {
          "layer_local": {score, suspicion, reasons, layer:'local'},
          "layer_llm":   {is_suspicious, score, reasons, layer:'llm', ...} | None,
          "combined_score": int(max),
          "suspicion": bool,        # true si l'une OU l'autre couche déclenche
          "reasons": [str, ...],     # concaténation préfixée [règle]/[llm]
        }

    RÈGLE ABSOLUE : `layer_local` est TOUJOURS calculé et n'est jamais
    dégradé par la couche 2. La couche 2 est purement additive.
    """
    local = analyze_message(
        group_type=group_type, key_id=key_id, content=content, now_ts=now_ts,
    )
    llm_result: Optional[Dict[str, Any]] = None
    if call_llm:
        llm_result = await _llm_analyze_subtle(content)
    # Score combiné = max des deux (pas de mélange qui masquerait un signal).
    local_score = int(local.get("score", 0))
    llm_score = 0
    if llm_result and "score" in llm_result:
        llm_score = int(llm_result.get("score", 0))
    combined = max(local_score, llm_score)
    reasons: List[str] = []
    for r in local.get("reasons") or []:
        reasons.append(f"[règle] {r}")
    if llm_result and llm_result.get("is_suspicious") and (llm_result.get("reasons") or []):
        for r in llm_result["reasons"]:
            reasons.append(f"[llm] {r}")
    suspicion = bool(
        local.get("suspicion")
        or (llm_result and llm_result.get("is_suspicious") and llm_score >= SUSPICION_THRESHOLD)
    )
    return {
        "layer_local": local,
        "layer_llm": llm_result,
        "combined_score": combined,
        "suspicion": suspicion,
        "reasons": reasons,
    }


# ------------------------------------------------------------------
# Journal d'anonymat — activations Nuit/Soleil (Créa only view)
# ------------------------------------------------------------------

async def log_mode_change(
    db, *, actor_key_id: str, mode: str, enabled: bool,
    actor_pseudo: Optional[str] = None,
    actor_public_handle: Optional[str] = None,
    actor_role: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
) -> None:
    """Enregistre un changement Nuit/Soleil/Anonyme dans le journal.

    Consultable via /social/anonymity-journal (créa only).
    """
    await db.anonymity_journal.insert_one({
        "actor_key_id": actor_key_id,
        "actor_pseudo": actor_pseudo,
        "actor_public_handle": actor_public_handle,
        "actor_role": actor_role,
        "mode": mode,  # 'anonymous' | 'sun_mode' | 'auto_sun'
        "enabled": bool(enabled),
        "context": context or {},
        "ts": datetime.now(timezone.utc).isoformat(),
    })


# ------------------------------------------------------------------
# État "suspicion active" par groupe — utilisé pour autoriser le
# Mode Soleil au staff qui le demande.
# ------------------------------------------------------------------

async def mark_group_suspicion(db, *, group_type: str, analysis: Dict[str, Any],
                                sender_key_id: str) -> None:
    """Marque un groupe comme sous surveillance active (TTL 10 min)."""
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    await db.group_suspicion.update_one(
        {"group_type": group_type},
        {"$set": {
            "group_type": group_type,
            "last_analysis": analysis,
            "last_sender_key_id": sender_key_id,
            "active_until": (now + timedelta(minutes=10)).isoformat(),
            "updated_at": now.isoformat(),
        }},
        upsert=True,
    )


async def is_group_under_suspicion(db, *, group_type: str) -> bool:
    row = await db.group_suspicion.find_one(
        {"group_type": group_type}, {"_id": 0, "active_until": 1},
    )
    if not row:
        return False
    try:
        active_until = datetime.fromisoformat(row["active_until"])
    except Exception:
        return False
    return active_until > datetime.now(timezone.utc)
