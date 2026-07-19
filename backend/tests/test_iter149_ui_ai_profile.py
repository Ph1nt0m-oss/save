"""iter149 — Injection profil IA + refonte Login/Landing + tutoriel interactif
+ badge Lecture seule + suppression journal anonymat staff.

Tests source-level et unitaires purs (pas de DB requise).
"""
import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


# -----------------------------------------------------------
# Task E — AI profile injection into system prompts
# -----------------------------------------------------------

def test_ai_profile_injector_module_exists():
    from utils import ai_profile_injector
    assert hasattr(ai_profile_injector, 'compose_system_prompt')
    assert hasattr(ai_profile_injector, 'load_profile')
    assert hasattr(ai_profile_injector, 'build_profile_fragment')


def test_build_profile_fragment_includes_all_fields():
    """Chaque champ configuré est présent dans le fragment généré."""
    from utils.ai_profile_injector import build_profile_fragment
    profile = {
        "writing_style": "chaleureux, structuré",
        "behavior": "toujours tutoyer",
        "domains": ["dev web", "cloud"],
        "limits": ["pas d'insultes"],
        "capabilities": ["répondre en JSON"],
        "allowed_tools": ["search"],
        "specializations": ["python", "typescript"],
        "custom_system_prompt": "Tu es UN AGENT SPÉCIALISÉ",
        "response_format": "markdown structuré",
        "reasoning_mode": "chain-of-thought interne",
    }
    frag = build_profile_fragment(profile)
    for tag in ("STYLE D'ÉCRITURE", "COMPORTEMENT", "DOMAINES", "LIMITES STRICTES",
                "CAPACITÉS AUTORISÉES", "OUTILS AUTORISÉS", "SPÉCIALISATIONS",
                "FORMAT DE RÉPONSE", "MODE DE RAISONNEMENT",
                "PROGRAMMATION SPÉCIFIQUE"):
        assert tag in frag, f"Tag manquant : {tag}"
    # Custom prompt en premier.
    assert "Tu es UN AGENT SPÉCIALISÉ" in frag


def test_build_profile_fragment_empty_returns_empty():
    from utils.ai_profile_injector import build_profile_fragment
    assert build_profile_fragment({}) == ""
    assert build_profile_fragment(None) == ""


def test_build_profile_fragment_partial_only_includes_set_fields():
    from utils.ai_profile_injector import build_profile_fragment
    frag = build_profile_fragment({"writing_style": "concis"})
    assert "STYLE D'ÉCRITURE : concis" in frag
    assert "COMPORTEMENT" not in frag
    assert "DOMAINES" not in frag


def test_compose_system_prompt_preserves_base_when_no_profile():
    """Si aucun profil configuré → base_prompt inchangé (couche 1 primaire)."""
    from utils.ai_profile_injector import compose_system_prompt

    class _MockDB:
        class ai_profiles:
            @staticmethod
            async def find_one(*_a, **_kw):
                return None
    base = "Tu es Caly."
    result = asyncio.run(compose_system_prompt(_MockDB(), "chat", base))
    assert result == base, "Aucun profil ne doit pas modifier le prompt"


def test_compose_system_prompt_appends_fragment_when_profile_exists():
    from utils.ai_profile_injector import compose_system_prompt

    class _MockDB:
        class ai_profiles:
            @staticmethod
            async def find_one(*_a, **_kw):
                return {"profile": {"writing_style": "punchy"}}
    base = "Tu es Caly."
    result = asyncio.run(compose_system_prompt(_MockDB(), "chat", base))
    assert result.startswith(base)
    assert "STYLE D'ÉCRITURE : punchy" in result


def test_compose_system_prompt_isolates_per_agent():
    """Deux agents avec des profils différents → chacun voit UNIQUEMENT le sien."""
    from utils.ai_profile_injector import compose_system_prompt

    class _MockDB:
        class ai_profiles:
            @staticmethod
            async def find_one(q, *_a, **_kw):
                aid = q.get("agent_id")
                if aid == "chat":
                    return {"profile": {"writing_style": "STYLE_CHAT"}}
                if aid == "dev":
                    return {"profile": {"writing_style": "STYLE_DEV"}}
                return None
    r_chat = asyncio.run(compose_system_prompt(_MockDB(), "chat", "BASE"))
    r_dev = asyncio.run(compose_system_prompt(_MockDB(), "dev", "BASE"))
    assert "STYLE_CHAT" in r_chat and "STYLE_DEV" not in r_chat
    assert "STYLE_DEV" in r_dev and "STYLE_CHAT" not in r_dev


def test_llm_entry_points_all_call_profile_injector():
    """Vérifie que TOUS les entry-points IA majeurs importent l'injecteur."""
    server = (BACKEND / "server.py").read_text()
    assert "from utils.ai_profile_injector import" in server, \
        "Chat pipeline principal doit importer l'injecteur"
    assert "load_profile" in server and "build_profile_fragment" in server

    caly = (BACKEND / "routes" / "caly_routes.py").read_text()
    assert "ai_profile_injector" in caly, "caly_routes doit injecter"

    community = (BACKEND / "routes" / "community_bots_routes.py").read_text()
    assert "ai_profile_injector" in community, "community_bots doit injecter"

    chat_agent = (BACKEND / "agents" / "chat_agent.py").read_text()
    assert "ai_profile_injector" in chat_agent, "chat_agent doit injecter"

    dev_agent = (BACKEND / "agents" / "dev_agent.py").read_text()
    assert "ai_profile_injector" in dev_agent, "dev_agent doit injecter"

    planner_agent = (BACKEND / "agents" / "planner_agent.py").read_text()
    assert "ai_profile_injector" in planner_agent, "planner_agent doit injecter"


# -----------------------------------------------------------
# Task A / B — LoginAuxButtons layout replaces PreviewMenuButton
# -----------------------------------------------------------

def test_login_aux_buttons_component_exists():
    p = Path("/app/frontend/src/components/LoginAuxButtons.jsx")
    assert p.exists()
    src = p.read_text()
    assert "login-visit-account-btn" in src
    assert "login-view-picker-btn" in src
    assert "login-view-picker-dropdown" in src
    # Les 2 boutons ont flex-1 pour partager la largeur (spec A: mêmes
    # largeurs que Connexion et Inscription tabs).
    assert "flex-1" in src
    # Dropdown contient exactement 2 options (spec B) : rendu via template literal.
    assert "login-view-opt-${key}" in src
    # Les 2 clés attendues doivent exister.
    assert "key: 'user'" in src and "key: 'guest'" in src


def test_login_page_uses_login_aux_buttons_not_preview_menu():
    src = Path("/app/frontend/src/pages/Login.js").read_text()
    assert "LoginAuxButtons" in src
    # Import de PreviewMenuButton retiré.
    assert "import PreviewMenuButton" not in src


def test_landing_page_uses_login_aux_buttons_not_preview_menu():
    src = Path("/app/frontend/src/pages/Landing.js").read_text()
    assert "LoginAuxButtons" in src
    assert "import PreviewMenuButton" not in src


def test_preview_menu_button_removed():
    """L'ancien composant doit être supprimé (pas juste dépréciée)."""
    p = Path("/app/frontend/src/components/PreviewMenuButton.jsx")
    assert not p.exists(), "PreviewMenuButton.jsx doit être supprimé"


# -----------------------------------------------------------
# Task C — Anonymity journal staff removed
# -----------------------------------------------------------

def test_anonymity_journal_button_removed_from_dashboard():
    src = Path("/app/frontend/src/pages/Dashboard.js").read_text()
    assert "open-anonymity-journal-btn" not in src
    assert "<AnonymityJournalPanel" not in src
    assert "import AnonymityJournalPanel" not in src


# -----------------------------------------------------------
# Task D — Read-only badge always visible
# -----------------------------------------------------------

def test_view_simulation_banner_shows_read_only_badge_always():
    src = Path("/app/frontend/src/components/ViewSimulationBanner.jsx").read_text()
    # Le testid du badge doit exister.
    assert "read-only-badge" in src
    # Le badge s'affiche même pour la vue Créa (spec D).
    assert "isCreatorSelfView" in src
    assert "Lecture seule" in src
    # PLUS de garde `if (!viewMode || viewMode === 'creator') return null;`
    # (le composant renvoie maintenant un JSX pour tous les cas).
    assert "if (!viewMode || viewMode === 'creator') return null;" not in src


# -----------------------------------------------------------
# Task F — Interactive tutorial (auth + menu scopes)
# -----------------------------------------------------------

def test_interactive_tutorial_component_exists():
    p = Path("/app/frontend/src/components/InteractiveTutorial.jsx")
    assert p.exists()
    src = p.read_text()
    # Deux scopes distincts (auth + menu) — modifiables facilement.
    assert "auth:" in src and "menu:" in src
    # Piloté par étapes (index + progression persistante).
    assert "STORAGE_KEY_PREFIX" in src
    assert "codeforge_tuto_progress_v2" in src
    # Export du bouton public.
    assert "LaunchTutorialButton" in src
    # Data-testids clés.
    assert "tuto-overlay-" in src
    assert "tuto-bubble-" in src
    assert "tuto-next-" in src
    assert "tuto-prev-" in src


def test_login_page_mounts_launch_tutorial_auth():
    src = Path("/app/frontend/src/pages/Login.js").read_text()
    assert "LaunchTutorialButton" in src
    assert 'scope="auth"' in src


def test_landing_page_mounts_launch_tutorial_auth():
    src = Path("/app/frontend/src/pages/Landing.js").read_text()
    assert "LaunchTutorialButton" in src


def test_dashboard_uses_interactive_menu_tutorial():
    src = Path("/app/frontend/src/pages/Dashboard.js").read_text()
    assert "InteractiveTutorial" in src
    assert 'scope="menu"' in src
    assert "menuTutoOpen" in src


# -----------------------------------------------------------
# Regressions
# -----------------------------------------------------------

def test_iter147_mentions_route_still_registered():
    server = (BACKEND / "server.py").read_text()
    assert "build_mentions_router" in server


def test_iter147_bot_analyzer_two_layers_still_intact():
    from utils import bot_analyzer
    assert hasattr(bot_analyzer, 'analyze_message')
    assert hasattr(bot_analyzer, 'analyze_message_combined')
