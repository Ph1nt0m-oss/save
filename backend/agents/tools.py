"""iter129 — Outils du Dev Agent (Forge).

Écritures confinées à l'espace de travail du projet :
/app/agent_workspaces/{project_id}/  (sandbox par projet — jamais le code du site).
Lectures repo + grep + sandbox Python réutilisés depuis orchestrator.py.
"""
import os
import difflib
from typing import Any, Dict

from orchestrator import _read_file_safe, _grep_safe, _execute_python  # noqa: F401

WORKSPACE_ROOT = "/app/agent_workspaces"


def _workspace_path(project_id: str, rel_path: str):
    base = os.path.join(WORKSPACE_ROOT, (project_id or "global").replace("/", "_"))
    if not rel_path or rel_path.startswith(("/", "\\")) or ".." in rel_path.split("/"):
        return None, base
    full = os.path.normpath(os.path.join(base, rel_path))
    if not full.startswith(base + os.sep):
        return None, base
    return full, base


def workspace_write(project_id: str, rel_path: str, content: str) -> Dict[str, Any]:
    """Crée ou modifie un fichier dans le workspace du projet, avec diff avant/après."""
    full, _base = _workspace_path(project_id, rel_path)
    if not full:
        return {"ok": False, "error": "invalid_path", "path": rel_path}
    content = content or ""
    before = None
    if os.path.isfile(full):
        try:
            with open(full, "r", encoding="utf-8", errors="replace") as f:
                before = f.read()
        except Exception:
            before = None
    try:
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        return {"ok": False, "error": str(e)[:200], "path": rel_path}
    action = "modified" if before is not None else "created"
    diff_lines = list(difflib.unified_diff(
        (before or "").splitlines(), content.splitlines(),
        fromfile=f"a/{rel_path}", tofile=f"b/{rel_path}", lineterm="",
    ))
    added = sum(1 for l in diff_lines if l.startswith("+") and not l.startswith("+++"))
    removed = sum(1 for l in diff_lines if l.startswith("-") and not l.startswith("---"))
    return {
        "ok": True, "action": action, "path": rel_path,
        "before": (before or "")[:30000] if before is not None else None,
        "after": content[:30000],
        "diff": "\n".join(diff_lines)[:30000],
        "lines_added": added, "lines_removed": removed,
        "bytes": len(content.encode("utf-8")),
    }


def workspace_read(project_id: str, rel_path: str) -> Dict[str, Any]:
    full, _base = _workspace_path(project_id, rel_path)
    if not full or not os.path.isfile(full):
        return {"ok": False, "error": "not_found", "path": rel_path}
    try:
        with open(full, "r", encoding="utf-8", errors="replace") as f:
            return {"ok": True, "path": rel_path, "content": f.read()[:60000]}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200], "path": rel_path}


def workspace_list(project_id: str) -> Dict[str, Any]:
    _full, base = _workspace_path(project_id, "x")
    files = []
    if os.path.isdir(base):
        for root, _dirs, names in os.walk(base):
            for n in names:
                files.append(os.path.relpath(os.path.join(root, n), base))
    return {"ok": True, "files": sorted(files)[:200]}
