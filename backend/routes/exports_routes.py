"""iter121 — Routes /exports/* extraites de server.py (5 endpoints).

  - POST /exports/request        (any device — ask for export approval)
  - POST /exports/decide         (creator only — approve/reject)
  - POST /exports/pending        (creator only — list pending)
  - GET  /exports/zip-project/{project_id}  (logged-in user — ZIP own project)
  - POST /exports/status         (user-side polling)

Helpers injectés : verify_signed, require_creator_signature, get_current_user.
"""
from __future__ import annotations

import io
import json as _json
import uuid
import zipfile
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from models.auth_signatures import CreatorSigIn as _CreatorSigIn, SignedIn


class ExportRequestIn(SignedIn):
    project_id: str
    export_kind: str   # "apk" | "exe" | "zip+github" | "source"


class ExportStatusIn(SignedIn):
    request_id: Optional[str] = None
    project_id: Optional[str] = None
    export_kind: Optional[str] = None


def build_exports_router(db, *, verify_signed, require_creator_signature, get_current_user):
    router = APIRouter()

    @router.post("/exports/request")
    async def exports_request(payload: ExportRequestIn):
        """Any non-creator device — request export approval."""
        dev = await verify_signed(payload.key_id, payload.nonce, payload.signature)
        if dev.get("role") == "creator":
            return {"approved": True, "auto": True}
        # Check for an existing pending/approved entry to avoid duplicates.
        existing = await db.export_requests.find_one({
            "key_id": payload.key_id,
            "project_id": payload.project_id,
            "export_kind": payload.export_kind,
            "status": {"$in": ["pending", "approved"]},
        }, {"_id": 0})
        if existing:
            return {
                "approved": existing["status"] == "approved",
                "status": existing["status"],
                "request_id": existing["request_id"],
            }
        doc = {
            "request_id": f"er_{uuid.uuid4().hex[:14]}",
            "key_id": payload.key_id,
            "label": dev.get("pseudo") or dev.get("label"),
            "project_id": payload.project_id,
            "export_kind": payload.export_kind,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.export_requests.insert_one(doc)
        return {"approved": False, "status": "pending", "request_id": doc["request_id"]}

    @router.post("/exports/decide")
    async def exports_decide(payload: _CreatorSigIn):
        await require_creator_signature(payload.key_id, payload.nonce, payload.signature)
        body = payload.model_dump() if hasattr(payload, "model_dump") else {}
        req_id = body.get("request_id")
        decision = body.get("decision")  # "approve" | "reject"
        if not req_id or decision not in ("approve", "reject"):
            raise HTTPException(status_code=400, detail="request_id + decision (approve|reject) requis.")
        new_status = "approved" if decision == "approve" else "rejected"
        r = await db.export_requests.update_one(
            {"request_id": req_id, "status": "pending"},
            {"$set": {"status": new_status, "decided_at": datetime.now(timezone.utc).isoformat()}},
        )
        if not r.matched_count:
            raise HTTPException(status_code=404, detail="Demande introuvable.")

        # iter126 — Lot 2 #6 : invisible GitHub transfer pipeline.
        # Fire-and-forget; failures don't block the decision.
        if decision == "approve":
            try:
                from services.github_storage import transfer_on_approve  # noqa: WPS433
                req_row = await db.export_requests.find_one({"request_id": req_id}, {"_id": 0})
                if req_row:
                    proj = await db.projects.find_one(
                        {"project_id": req_row.get("project_id")},
                        {"_id": 0, "user_id": 1},
                    )
                    if proj:
                        await transfer_on_approve(
                            db, user_id=proj["user_id"], project_id=req_row["project_id"],
                        )
            except Exception:
                # Silencieux : ne JAMAIS exposer l'existence du storage invisible.
                pass

        return {"success": True, "status": new_status}

    @router.post("/exports/pending")
    async def exports_pending(payload: _CreatorSigIn):
        """Creator-only — list pending export requests.

        iter125 — Enriched with `pseudo`, `device_label` (OCR-detected device
        name), and `project_name` so the créa modal can display friendly
        fields rather than raw IDs.
        """
        await require_creator_signature(payload.key_id, payload.nonce, payload.signature)
        rows = (
            await db.export_requests.find({"status": "pending"}, {"_id": 0})
            .sort("created_at", -1)
            .to_list(length=200)
        )

        # Enrich: lookup pseudo + label from device_keys ; project_name from projects.
        key_ids = list({r.get("key_id") for r in rows if r.get("key_id")})
        proj_ids = list({r.get("project_id") for r in rows if r.get("project_id")})
        dev_map = {}
        if key_ids:
            async for d in db.device_keys.find(
                {"key_id": {"$in": key_ids}},
                {"_id": 0, "key_id": 1, "pseudo": 1, "label": 1, "device_capture": 1, "role": 1, "staff_kind": 1},
            ):
                dev_map[d["key_id"]] = d
        proj_map = {}
        if proj_ids:
            async for p in db.projects.find(
                {"project_id": {"$in": proj_ids}},
                {"_id": 0, "project_id": 1, "name": 1},
            ):
                proj_map[p["project_id"]] = p

        for r in rows:
            dev = dev_map.get(r.get("key_id")) or {}
            r["pseudo"] = dev.get("pseudo") or r.get("label") or ""
            # device_capture is the OCR-detected device name shown everywhere
            # (e.g. "iPhone 14 Pro" or "Linux · Chrome"). Fallback to label.
            dc = dev.get("device_capture") or {}
            r["device_label"] = (
                dc.get("device_name")
                or dc.get("model")
                or dev.get("label")
                or ""
            )
            proj = proj_map.get(r.get("project_id")) or {}
            r["project_name"] = proj.get("name") or r.get("project_id", "")
            # iter134 — Rôle du device cible pour permettre à la créa de
            # basculer en simulation identique à AccountsButton.onVisitAccount.
            r["target_role"] = dev.get("role")
            r["target_staff_kind"] = dev.get("staff_kind")
        return {"requests": rows}

    @router.get("/exports/zip-project/{project_id}")
    async def export_project_zip(request: Request, project_id: str):
        """Génère un ZIP du projet : metadata + historique chat + fichiers générés."""
        user_id = await get_current_user(request)
        project = await db.projects.find_one(
            {"project_id": project_id, "user_id": user_id}, {"_id": 0},
        )
        if not project:
            raise HTTPException(status_code=404, detail="Projet introuvable.")
        messages = (
            await db.chat_messages.find(
                {"project_id": project_id, "user_id": user_id}, {"_id": 0}
            )
            .sort("timestamp", 1)
            .to_list(length=10000)
        )
        # Genere le ZIP en mémoire
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("project.json", _json.dumps(project, indent=2, default=str, ensure_ascii=False))
            zf.writestr("messages.json", _json.dumps(messages, indent=2, default=str, ensure_ascii=False))
            readme = (
                f"# {project.get('name') or 'Projet CodeForge'}\n\n"
                f"Export généré le {datetime.now(timezone.utc).isoformat()}\n\n"
                f"## Contenu\n"
                f"- project.json : métadonnées du projet\n"
                f"- messages.json : historique complet des échanges IA\n"
                f"- {len(messages)} messages au total\n\n"
                f"## Note\n"
                f"Le push GitHub se fait automatiquement à chaque création via on_commit_real.\n"
            )
            zf.writestr("README.md", readme)
        buf.seek(0)
        safe_name = (project.get("name") or project_id).replace("/", "_")[:50]
        return Response(
            content=buf.read(),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="codeforge_{safe_name}.zip"'},
        )

    @router.post("/exports/status")
    async def exports_status(payload: ExportStatusIn):
        """User-side polling — current status of a pending export request."""
        await verify_signed(payload.key_id, payload.nonce, payload.signature)
        q = {"key_id": payload.key_id}
        if payload.request_id:
            q["request_id"] = payload.request_id
        elif payload.project_id and payload.export_kind:
            q["project_id"] = payload.project_id
            q["export_kind"] = payload.export_kind
        else:
            raise HTTPException(status_code=400, detail="request_id ou (project_id+export_kind) requis.")
        row = await db.export_requests.find_one(q, {"_id": 0}, sort=[("created_at", -1)])
        if not row:
            return {"status": "none"}
        return {"status": row["status"], "request_id": row["request_id"]}

    return router
