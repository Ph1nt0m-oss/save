"""iter148 — Sprint 3 : Fiches Programmation dédiées + Tutoriel +
routing fix + Intégrations UI + Langues.

Ces tests source-level valident la présence des routes, des composants
et la cohérence des liens dashboard → pages dédiées.
"""
from pathlib import Path


REPO = Path("/app")
APP_JS = (REPO / "frontend/src/App.js").read_text()
DASHBOARD = (REPO / "frontend/src/pages/Dashboard.js").read_text()


def test_tutorial_route_registered():
    assert '/tutorial' in APP_JS
    assert "import Tutorial from './pages/Tutorial'" in APP_JS


def test_tutorial_page_exists_with_required_steps():
    src = (REPO / "frontend/src/pages/Tutorial.js").read_text()
    for step_id in ('identity', 'groups', 'moderation', 'ai-programming',
                    'exports', 'integrations', 'languages'):
        assert f"id: '{step_id}'" in src, f"étape {step_id} manquante"
    # Data-testids clefs.
    assert 'tutorial-page' in src
    assert 'tutorial-progress' in src
    assert 'tutorial-progress-bar' in src
    assert 'tutorial-next' in src
    assert 'tutorial-prev' in src
    assert 'tutorial-finish' in src
    # Le composant LanguageToggle est intégré dans l'étape langues.
    assert 'LanguageToggle' in src


def test_ai_programming_route_conflict_resolved():
    """iter148 — Un seul mapping `/private/ai-programming` doit exister,
    et il doit pointer sur AIProgramming (le composant iter143), pas sur
    PrivateProgramming (qui gérait le site)."""
    # Count occurrences of the route.
    n = APP_JS.count('path="/private/ai-programming"')
    assert n == 1, f"Route dupliquée : {n} occurrences trouvées"
    # Et le mapping cible AIProgramming.
    idx = APP_JS.find('path="/private/ai-programming"')
    tail = APP_JS[idx: idx + 300]
    assert '<AIProgramming' in tail, "Route ai-programming doit rendre <AIProgramming />"


def test_all_sprint3_routes_present():
    for path in ('/private/caly-programming',
                 '/private/bots-programming',
                 '/private/site-programming',
                 '/private/ai-programming',
                 '/private/agent-registry',
                 '/private/integrations',
                 '/tutorial'):
        assert f'path="{path}"' in APP_JS, f"Route {path} manquante"


def test_dashboard_has_tutorial_button():
    assert 'header-tutorial-btn' in DASHBOARD
    assert "navigate('/tutorial')" in DASHBOARD
    assert 'GraduationCap' in DASHBOARD


def test_dashboard_sprint3_cards():
    """Cartes créa Sprint 3 : Caly, Bots, Site, IA, Mes IA, Intégrations."""
    for tid in ('creator-caly-prog-btn', 'creator-bots-prog-btn',
                'creator-private-site-btn', 'creator-private-ai-btn',
                'creator-agent-registry-btn', 'creator-integrations-btn'):
        assert tid in DASHBOARD, f"Carte {tid} manquante"


def test_dashboard_language_toggle_mounted():
    """Le sélecteur de langue est monté dans le header du dashboard."""
    assert 'LanguageToggle' in DASHBOARD


def test_language_context_supports_multiple_languages():
    src = (REPO / "frontend/src/contexts/LanguageContext.js").read_text()
    assert 'const translations' in src
    # Le fichier définit ` fr:`, ` en:`, ` es:` etc. avec un espace initial.
    from re import findall
    langs = findall(r"^ (fr|en|es|de|it|pt|nl|pl|ru|ja|zh|ar|hi|ko|tr|sv|hr|da|ur|bn):\s*\{",
                    src, flags=8)  # re.MULTILINE
    assert len(langs) >= 5, f"Trop peu de langues : {len(langs)}"


def test_integrations_page_covers_three_providers():
    src = (REPO / "frontend/src/pages/PrivateIntegrations.js").read_text()
    assert 'Stripe' in src
    assert 'Google' in src
    assert 'ChatGPT' in src or 'OpenAI' in src


def test_agent_registry_page_exists():
    src = (REPO / "frontend/src/pages/PrivateAgentRegistry.js").read_text()
    # C'est la vue "Mes IA" (registre agents).
    assert 'agents/registry' in src or 'AGENT_REGISTRY' in src or 'agent-registry' in src


def test_backend_ai_profile_endpoints_registered():
    server = (REPO / "backend/server.py").read_text()
    assert 'build_ai_programming_router' in server
    # Programmation ai-programming endpoints réellement montés.
    assert 'ai_programming_routes' in server


def test_backend_integrations_endpoints_registered():
    server = (REPO / "backend/server.py").read_text()
    assert 'integrations_routes' in server or 'build_integrations_router' in server
