"""iter143 — Bot validateur d'export.

Analyse une demande d'export AVANT validation Créa. Produit un rapport
consultatif (jamais bloquant) que la Créa consulte via l'icône dédiée.

Le bot vérifie :
  1. Existence et cohérence du compte demandeur (device_keys).
  2. Existence et propriété du projet (projects.user_id === demandeur.email
     ou via device_keys.email match).
  3. Type d'export valide (ZIP/JSON/…).
  4. Historique des discussions liées au projet (chat_messages).
  5. Cohérence des données exportées vs permissions du rôle.

Retourne un JSON structuré :
{
  "ok": bool,             # aucun blocage détecté
  "anomalies": [...],     # liste d'anomalies concrètes
  "summary": "...",       # résumé lisible pour la Créa
  "layers": {
    "account": {...},
    "project": {...},
    "discussions": {...},
    "coherence": {...},
  }
}
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List


async def analyze_export_request(db, request_id: str) -> Dict[str, Any]:
    """Analyse complète asynchrone. Idempotent — écrit le rapport final
    dans la collection `export_bot_reports`."""
    req = await db.export_requests.find_one({"request_id": request_id}, {"_id": 0})
    if not req:
        return {"ok": False, "anomalies": ["Demande introuvable."], "summary": "Analyse impossible"}

    anomalies: List[str] = []
    layers: Dict[str, Any] = {}

    # 1) Compte du demandeur.
    dev = await db.device_keys.find_one({"key_id": req.get("key_id")}, {"_id": 0}) or {}
    if not dev:
        anomalies.append("Compte demandeur introuvable dans device_keys.")
    if dev.get("role") == "blocked":
        anomalies.append("Compte demandeur bloqué.")
    layers["account"] = {
        "key_id": req.get("key_id"),
        "role": dev.get("role"),
        "staff_kind": dev.get("staff_kind"),
        "pseudo": dev.get("pseudo") or dev.get("label"),
        "public_handle": dev.get("public_handle") or "",
        "email": dev.get("email"),
    }

    # 2) Projet.
    proj = await db.projects.find_one({"project_id": req.get("project_id")}, {"_id": 0}) or {}
    if not proj:
        anomalies.append("Projet introuvable.")
    proj_email = proj.get("email") or ""
    if dev.get("email") and proj_email and dev.get("email") != proj_email:
        # Match by user_id if present.
        if proj.get("user_id"):
            u = await db.users.find_one({"user_id": proj.get("user_id")}, {"_id": 0, "email": 1}) or {}
            if u.get("email") != dev.get("email"):
                anomalies.append("Le projet appartient à un email différent du demandeur.")
    layers["project"] = {
        "project_id": req.get("project_id"),
        "name": proj.get("name") or proj.get("project_name") or req.get("project_id"),
        "owner_email": proj_email or (dev.get("email") if proj else None),
        "created_at": proj.get("created_at"),
    }

    # 3) Type d'export.
    kind = (req.get("export_kind") or "").upper()
    if kind not in ("ZIP", "JSON", "TEXT", "TAR"):
        anomalies.append(f"Type d'export inhabituel : {kind or '—'}.")

    # 4) Discussions liées.
    chat_count = await db.chat_messages.count_documents({"project_id": req.get("project_id")})
    layers["discussions"] = {"count": chat_count}

    # 5) Cohérence rôle / permissions.
    if dev.get("role") == "pending":
        anomalies.append("Compte demandeur encore en attente d'approbation (pending).")

    ok = len(anomalies) == 0
    summary = (
        "Aucune anomalie détectée — export sûr à approuver."
        if ok else
        f"{len(anomalies)} anomalie(s) détectée(s) — voir détail."
    )
    layers["coherence"] = {"role_ok": dev.get("role") in ("approved", "creator")}

    report = {
        "request_id": request_id,
        "ok": ok,
        "anomalies": anomalies,
        "summary": summary,
        "layers": layers,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.export_bot_reports.update_one(
        {"request_id": request_id},
        {"$set": report},
        upsert=True,
    )
    return report


async def get_export_report(db, request_id: str) -> Dict[str, Any]:
    row = await db.export_bot_reports.find_one({"request_id": request_id}, {"_id": 0})
    if row:
        return row
    # Not yet computed → analyze on demand.
    return await analyze_export_request(db, request_id)
