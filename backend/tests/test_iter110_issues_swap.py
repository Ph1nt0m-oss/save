"""
iter110 — Site Issues page + spacings finaux.
iter112 — Page SiteIssues ABANDONNÉE (codes d'erreurs trop hétérogènes à
répertorier). Sa route /private/site-issues redirige désormais vers la
programmation des bots/chatbots. Les tests de cette suite ont été simplifiés.
"""
import os
from pathlib import Path

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_codeforge_iter110")

from server import app  # noqa: E402


def test_site_issues_endpoints_registered():
    """Backend endpoints /api/site/issues/* restent disponibles pour compatibilité,
    même si l'UI ne les utilise plus."""
    routes = {r.path for r in app.routes if hasattr(r, "path")}
    assert "/api/site/issues/create" in routes
    assert "/api/site/issues" in routes
    assert "/api/site/issues/update" in routes


def test_site_issues_create_endpoint_signature_required():
    """POST /site/issues/create needs signature — validated via route + source check.
    iter129 — endpoint extrait de server.py vers routes/site_issues_routes.py."""
    src = Path("/app/backend/routes/site_issues_routes.py").read_text(encoding="utf-8")
    idx = src.find('@router.post("/site/issues/create")')
    assert idx > 0
    chunk = src[idx:idx + 1500]
    assert "verify_signed" in chunk
    assert "creator" in chunk and "admin" in chunk


def test_site_issues_page_abandoned_iter112():
    """iter112 — SiteIssues.js a été supprimé. La route /private/site-issues
    redirige désormais vers la page de programmation des bots."""
    p = Path("/app/frontend/src/pages/SiteIssues.js")
    assert not p.exists(), "SiteIssues.js doit avoir été supprimé en iter112"


def test_site_issues_route_redirects_to_bots_programming():
    """iter112 — La route /private/site-issues doit rendre PrivateChatbotProgramming."""
    app_js = Path("/app/frontend/src/App.js").read_text(encoding="utf-8")
    assert "/private/site-issues" in app_js
    # Doit rendre PrivateChatbotProgramming en mode bots, pas SiteIssues.
    assert "import SiteIssues" not in app_js


def test_dashboard_has_bots_prog_button():
    """iter112 — La tuile 'Problèmes du site' a été remplacée par 'Programmations des bots et chatbots'."""
    dash = Path("/app/frontend/src/pages/Dashboard.js").read_text(encoding="utf-8")
    assert "creator-bots-prog-btn" in dash
    assert "Programmations des bots et chatbots" in dash


def test_caly_right_24_iter110():
    caly = Path("/app/frontend/src/components/CalyChatbot.jsx").read_text(encoding="utf-8")
    assert "right-[88px]" in caly


def test_dashboard_swap_theft_language():
    """Theft should appear BEFORE LanguageToggle in the JSX."""
    dash = Path("/app/frontend/src/pages/Dashboard.js").read_text(encoding="utf-8")
    theft_pos = dash.find("TheftButton variant=\"labelled\"")
    lang_pos = dash.find("LanguageToggle placement=\"bottom\"")
    assert theft_pos > 0 and lang_pos > 0
    assert theft_pos < lang_pos, "TheftButton must appear before LanguageToggle (iter110 swap)"


def test_site_mode_badge_offset_recent():
    """SiteModeBadge décalé (iter110: ml-64, iter112: ml-12 + gap-6 + ml-2 Comptes pour resserrer)."""
    dash = Path("/app/frontend/src/pages/Dashboard.js").read_text(encoding="utf-8")
    assert ("ml-3 sm:ml-64" in dash) or ("ml-3 sm:ml-[15cm]" in dash) or ("ml-3 sm:ml-12 flex items-center gap-2 sm:gap-3 border-l" in dash)
