"""iter131 — Routes /workspace/* : téléchargement des fichiers créés par
Forge (Dev Agent) dans le workspace d'un projet.

Endpoints :
  - GET /workspace/list/{project_id}      : liste les fichiers workspace
  - GET /workspace/download/{project_id}  : ZIP téléchargeable

Sécurité : la session de l'appelant (get_current_user) doit posséder le
projet (`db.projects.find_one({project_id, user_id})`). Le workspace vit
sous /app/agent_workspaces/{safe_project_id}/ (voir agents/tools.py).
"""
import os
import io
import zipfile
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from fastapi.responses import StreamingResponse, JSONResponse

from agents.tools import WORKSPACE_ROOT


def _safe_project_dir(project_id: str) -> Optional[str]:
    if not project_id or "/" in project_id or ".." in project_id:
        return None
    return os.path.join(WORKSPACE_ROOT, project_id.replace("/", "_"))


def build_workspace_router(db, *, get_current_user):
    router = APIRouter()

    async def _ensure_owner(request: Request, project_id: str):
        user_id = await get_current_user(request)
        proj = await db.projects.find_one(
            {"project_id": project_id, "user_id": user_id}, {"_id": 0, "project_id": 1},
        )
        if not proj:
            raise HTTPException(status_code=404, detail="Projet introuvable.")
        return user_id

    @router.get("/workspace/list/{project_id}")
    async def workspace_list_files(request: Request, project_id: str):
        await _ensure_owner(request, project_id)
        base = _safe_project_dir(project_id)
        if not base or not os.path.isdir(base):
            return {"files": [], "count": 0, "bytes": 0}
        files, total = [], 0
        for root, _dirs, names in os.walk(base):
            for n in names:
                fp = os.path.join(root, n)
                try:
                    sz = os.path.getsize(fp)
                except OSError:
                    sz = 0
                total += sz
                files.append({"path": os.path.relpath(fp, base), "bytes": sz})
        files.sort(key=lambda x: x["path"])
        return {"files": files[:500], "count": len(files), "bytes": total}

    @router.get("/workspace/download/{project_id}")
    async def workspace_download(request: Request, project_id: str):
        await _ensure_owner(request, project_id)
        base = _safe_project_dir(project_id)
        if not base or not os.path.isdir(base):
            raise HTTPException(status_code=404, detail="Aucun fichier généré par Forge pour ce projet.")

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            total_bytes = 0
            for root, _dirs, names in os.walk(base):
                for n in names:
                    fp = os.path.join(root, n)
                    try:
                        sz = os.path.getsize(fp)
                        if total_bytes + sz > 50 * 1024 * 1024:  # 50 MB cap
                            continue
                        arcname = os.path.relpath(fp, base)
                        zf.write(fp, arcname=arcname)
                        total_bytes += sz
                    except Exception:
                        continue
            # Ajoute un README explicatif au ZIP.
            readme = (
                f"# Workspace Forge — projet {project_id}\n\n"
                "Ce ZIP contient les fichiers générés par l'agent Forge (Dev Agent) "
                "dans le sandbox de ce projet. Ces fichiers sont indépendants du code "
                "de CodeForge AI et sont sûrs à réutiliser dans ton propre projet.\n"
            )
            zf.writestr("README.md", readme)

        buf.seek(0)
        filename = f"forge-workspace-{project_id[:12]}.zip"
        return StreamingResponse(
            iter([buf.getvalue()]),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @router.post("/workspace/import/{project_id}")
    async def workspace_import(request: Request, project_id: str, file: UploadFile = File(...)):
        """iter132 — Ré-upload d'un ZIP Forge modifié.

        Le ZIP est extrait dans le workspace du projet (après effacement).
        Sécurité : ownership requis, path traversal bloqué, cap 50 MB.
        """
        await _ensure_owner(request, project_id)
        base = _safe_project_dir(project_id)
        if not base:
            raise HTTPException(status_code=400, detail="Identifiant projet invalide.")

        # Lit le fichier en mémoire (cap 50 MB).
        MAX = 50 * 1024 * 1024
        data = await file.read(MAX + 1)
        if len(data) > MAX:
            raise HTTPException(status_code=413, detail="ZIP trop volumineux (max 50 MB).")
        if not data:
            raise HTTPException(status_code=400, detail="Fichier vide.")

        try:
            zf = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile:
            raise HTTPException(status_code=400, detail="Fichier ZIP invalide.")

        # Vérifie qu'aucun membre n'utilise de path traversal.
        safe_members = []
        for m in zf.infolist():
            if m.is_dir():
                continue
            name = m.filename.replace("\\", "/")
            if name.startswith("/") or ".." in name.split("/"):
                continue
            if m.file_size > 10 * 1024 * 1024:  # 10 MB par fichier max
                continue
            safe_members.append(m)

        if not safe_members:
            raise HTTPException(status_code=400, detail="Aucun fichier valide dans le ZIP.")

        # Efface l'ancien workspace puis extrait proprement.
        os.makedirs(base, exist_ok=True)
        for root, _dirs, names in os.walk(base):
            for n in names:
                try:
                    os.remove(os.path.join(root, n))
                except OSError:
                    pass

        extracted = 0
        total_bytes = 0
        for m in safe_members:
            try:
                target = os.path.join(base, m.filename.replace("\\", "/"))
                # Résout et vérifie que target reste sous `base`.
                target_abs = os.path.realpath(target)
                base_abs = os.path.realpath(base)
                if not target_abs.startswith(base_abs + os.sep) and target_abs != base_abs:
                    continue
                os.makedirs(os.path.dirname(target_abs), exist_ok=True)
                if m.filename.endswith("/"):
                    continue
                with zf.open(m) as src, open(target_abs, "wb") as dst:
                    payload = src.read()
                    dst.write(payload)
                    total_bytes += len(payload)
                    extracted += 1
            except Exception:
                continue

        return {"imported": True, "files": extracted, "bytes": total_bytes, "project_id": project_id}

    return router
