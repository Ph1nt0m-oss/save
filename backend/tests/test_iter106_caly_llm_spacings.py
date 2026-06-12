"""
iter106 — Tests pour Caly LLM + spacings + read-file full + truncation removed.
"""
import os
from pathlib import Path

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_codeforge_iter106")

from server import app  # noqa: E402


def test_caly_ask_endpoint_registered():
    routes = {r.path for r in app.routes if hasattr(r, "path")}
    assert "/api/caly/ask" in routes
    assert "/api/caly/config" in routes


def test_caly_default_system_prompt_present():
    src = Path("/app/backend/server.py").read_text(encoding="utf-8")
    assert "CALY_DEFAULT_SYSTEM_PROMPT" in src
    assert "Tu es Caly" in src


def test_caly_config_endpoint_registered():
    """GET /api/caly/config doit être enregistré (validé via curl externe car
    TestClient + Motor a un conflit de loop connu)."""
    routes = {r.path for r in app.routes if hasattr(r, "path")}
    assert "/api/caly/config" in routes


def test_read_file_endpoint_uses_full_read():
    """server.py call should pass full_read=True for the creator."""
    src = Path("/app/backend/server.py").read_text(encoding="utf-8")
    assert "_read_file_safe(payload.path, full_read=True)" in src


def test_orchestrator_supports_full_read():
    orch = Path("/app/backend/orchestrator.py").read_text(encoding="utf-8")
    assert "full_read: bool = False" in orch
    assert "if full_read:" in orch


def test_caly_offset_set():
    """Caly est à un offset right (~3 ou 7cm selon iter)."""
    caly = Path("/app/frontend/src/components/CalyChatbot.jsx").read_text(encoding="utf-8")
    assert any(rw in caly for rw in ("right-64", "right-36", "right-44"))
    assert "right-5 z-" not in caly


def test_caly_uses_new_endpoint():
    """CalyChatbot.jsx doit appeler /caly/ask au lieu de /chat/message."""
    caly = Path("/app/frontend/src/components/CalyChatbot.jsx").read_text(encoding="utf-8")
    assert "/caly/ask" in caly


def test_dashboard_spacings_increased():
    """Dashboard.js doit avoir des gaps plus larges (iter106 → iter107 ml-24)."""
    dash = Path("/app/frontend/src/pages/Dashboard.js").read_text(encoding="utf-8")
    assert "lg:gap-16" in dash or "lg:gap-12" in dash
    # iter106 ml-12 ou iter107 ml-24
    assert ("ml-3 sm:ml-12" in dash) or ("ml-3 sm:ml-24" in dash)
