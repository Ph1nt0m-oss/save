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

from fastapi import APIRouter, HTTPException, Request
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

    return router
