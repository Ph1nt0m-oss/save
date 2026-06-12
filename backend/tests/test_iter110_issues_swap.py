"""
iter110 — Site Issues page + spacings finaux.
"""
import os
from pathlib import Path

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_codeforge_iter110")

from server import app  # noqa: E402


def test_site_issues_endpoints_registered():
    routes = {r.path for r in app.routes if hasattr(r, "path")}
    assert "/api/site/issues/create" in routes
    assert "/api/site/issues" in routes
    assert "/api/site/issues/update" in routes


def test_site_issues_create_endpoint_signature_required():
    """POST /site/issues/create needs signature — validated via route + source check."""
    src = Path("/app/backend/server.py").read_text(encoding="utf-8")
    idx = src.find('@api_router.post("/site/issues/create")')
    assert idx > 0
    chunk = src[idx:idx + 1500]
    assert "_verify_signed" in chunk
    assert "creator" in chunk and "admin" in chunk


def test_site_issues_list_endpoint_registered():
    """GET /api/site/issues registered (validated via curl externally — Motor/TestClient loop conflict)."""
    routes = {r.path for r in app.routes if hasattr(r, "path")}
    assert "/api/site/issues" in routes


def test_site_issues_page_exists():
    p = Path("/app/frontend/src/pages/SiteIssues.js")
    assert p.exists()
    c = p.read_text(encoding="utf-8")
    assert "issue-create-form" in c
    assert "/site/issues/create" in c


def test_site_issues_route_wired():
    app_js = Path("/app/frontend/src/App.js").read_text(encoding="utf-8")
    assert "import SiteIssues" in app_js
    assert "/private/site-issues" in app_js


def test_dashboard_has_issues_button():
    dash = Path("/app/frontend/src/pages/Dashboard.js").read_text(encoding="utf-8")
    assert "creator-issues-btn" in dash
    assert "AlertTriangle" in dash


def test_caly_right_24_iter110():
    caly = Path("/app/frontend/src/components/CalyChatbot.jsx").read_text(encoding="utf-8")
    assert "right-24" in caly


def test_dashboard_swap_theft_language():
    """Theft should appear BEFORE LanguageToggle in the JSX."""
    dash = Path("/app/frontend/src/pages/Dashboard.js").read_text(encoding="utf-8")
    theft_pos = dash.find("TheftButton variant=\"labelled\"")
    lang_pos = dash.find("LanguageToggle placement=\"bottom\"")
    assert theft_pos > 0 and lang_pos > 0
    assert theft_pos < lang_pos, "TheftButton must appear before LanguageToggle (iter110 swap)"


def test_site_mode_badge_ml_64():
    """SiteModeBadge décalé encore plus à gauche (iter110)."""
    dash = Path("/app/frontend/src/pages/Dashboard.js").read_text(encoding="utf-8")
    assert "ml-3 sm:ml-64" in dash
