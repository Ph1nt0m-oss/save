"""iter142 Batch 3 — Bots analyseurs et journal d'anonymat.

Architecture hybride :
  - Couche 1 : règles locales rapides et fiables (spam patterns, flood,
    répétition, mots-clés suspects, copier-coller massif).
  - Couche 2 : escalade vers Emergent LLM UNIQUEMENT lorsque la couche 1
    dépasse un seuil (peut ne PAS être active immédiatement — stub).

Rôle :
  - Analyse chaque message envoyé, calcule un score de suspicion 0-100.
  - Si > SUSPICION_THRESHOLD : marque le groupe comme "en état
    suspicion" → autorise le staff (modo/admin/créa) présent à activer
    temporairement le Mode Soleil (voir les vrais pseudos) pour ce
    groupe.
  - Dans un groupe SANS staff : émet une "demande d'intervention" visible
    par le groupe (notification anonyme "surveillance déclenchée, un
    membre du staff va être notifié").

Cette version n'intègre PAS encore l'appel LLM (Batch 3.b). Elle expose
les hooks nécessaires côté API pour que la Créa/staff puisse consulter
l'état + le journal.
"""
from __future__ import annotations

import re
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
    """Analyse locale du message. Retourne :
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
