"""iter129 — Tests du système multi-agents spécialisés (agents/).

Couvre : registre d'identités, interdiction de fusion des personnalités,
outils workspace (diff avant/après), router heuristique, câblage /chat/stream
et endpoint /agents/registry.
"""
import os
import shutil
from pathlib import Path

import pytest

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_codeforge_iter129")

from agents.registry import (  # noqa: E402
    AGENT_REGISTRY, get_agent_card,
    CHAT_AGENT_SYSTEM, DEV_PLANNER_SYSTEM, DEV_RESPONDER_SYSTEM,
    PLANNER_AGENT_SYSTEM, ROUTER_SYSTEM,
)
from agents.tools import workspace_write, workspace_read, workspace_list, WORKSPACE_ROOT  # noqa: E402
from agents.router_agent import route_message  # noqa: E402
from agents.common import resolve_model, format_history, lang_label  # noqa: E402

TEST_PROJECT = "pytest_iter129_ws"


@pytest.fixture(autouse=True)
def _cleanup_workspace():
    yield
    shutil.rmtree(os.path.join(WORKSPACE_ROOT, TEST_PROJECT), ignore_errors=True)


# ----- Registre / fiches d'identité ----------------------------------------

def test_registry_contains_all_site_ais():
    """Analyse obligatoire : chaque IA du site a sa fiche d'identité."""
    expected = {"router", "chat", "dev", "planner", "caly_help", "app_builder",
                "orchestrator", "wizard", "ocr_device", "attachment_analyst",
                "translator", "enhancement_advisor", "community_bots"}
    assert expected.issubset(set(AGENT_REGISTRY.keys()))


def test_registry_cards_complete():
    """Chaque fiche : nom, objectif, expertise, raisonnement, format, outils, limites."""
    for aid, card in AGENT_REGISTRY.items():
        for field in ("name", "objectif", "expertise", "raisonnement",
                      "format", "outils", "limites", "module"):
            assert card.get(field) is not None, f"{aid} manque {field}"


def test_no_personality_fusion():
    """Interdiction de fusion : chaque agent du pipeline a son PROPRE prompt système."""
    prompts = [CHAT_AGENT_SYSTEM, DEV_PLANNER_SYSTEM, DEV_RESPONDER_SYSTEM,
               PLANNER_AGENT_SYSTEM, ROUTER_SYSTEM]
    assert len(set(prompts)) == len(prompts), "Prompts systèmes dupliqués = fusion interdite"
    # Spécialisations distinctes vérifiables
    assert "Caly" in CHAT_AGENT_SYSTEM and "code" in CHAT_AGENT_SYSTEM.lower()
    assert "Forge" in DEV_RESPONDER_SYSTEM and "[État]" in DEV_RESPONDER_SYSTEM
    assert "Archi" in PLANNER_AGENT_SYSTEM and "PAS de code" in PLANNER_AGENT_SYSTEM


def test_dev_responder_mandatory_format():
    for section in ("[État]", "[Actions réalisées]", "[Fichiers/Ressources utilisées]",
                    "[Résultat]", "[Prochaines étapes]"):
        assert section in DEV_RESPONDER_SYSTEM


def test_get_agent_card_fallback():
    assert get_agent_card("unknown_xyz")["id"] == "chat"
    assert get_agent_card("dev")["name"] == "Forge"


# ----- Outils workspace (sandbox par projet) --------------------------------

def test_workspace_write_create_then_modify_with_diff():
    r1 = workspace_write(TEST_PROJECT, "src/mod.py", "def f():\n    return 1\n")
    assert r1["ok"] and r1["action"] == "created" and r1["lines_added"] == 2
    r2 = workspace_write(TEST_PROJECT, "src/mod.py", "def f():\n    return 2\n")
    assert r2["ok"] and r2["action"] == "modified"
    assert "@@" in r2["diff"] and "-    return 1" in r2["diff"] and "+    return 2" in r2["diff"]
    assert r2["before"] is not None and "return 1" in r2["before"]
    assert "return 2" in r2["after"]


def test_workspace_read_and_list():
    workspace_write(TEST_PROJECT, "a/b.txt", "hello")
    assert workspace_read(TEST_PROJECT, "a/b.txt")["content"] == "hello"
    assert "a/b.txt" in workspace_list(TEST_PROJECT)["files"]


def test_workspace_rejects_escapes():
    assert not workspace_write(TEST_PROJECT, "../evil.py", "x")["ok"]
    assert not workspace_write(TEST_PROJECT, "/abs/path.py", "x")["ok"]
    assert not Path("/app/agent_workspaces/evil.py").exists()


# ----- Router (heuristiques, sans LLM) --------------------------------------

def test_router_heuristics():
    import asyncio
    assert asyncio.run(route_message("Salut, ça va ?")) == "chat"
    assert asyncio.run(route_message("Corrige le bug dans le module API")) == "dev"
    assert asyncio.run(route_message("Planifie la roadmap de mon projet")) == "planner"
    assert asyncio.run(route_message("")) == "chat"


# ----- Helpers ---------------------------------------------------------------

def test_resolve_model_mapping():
    assert resolve_model("claude-fable") == ("anthropic", "claude-sonnet-4-5-20250929")
    assert resolve_model("gemini-3") == ("gemini", "gemini-3-flash-preview")
    assert resolve_model("gpt-5.2") == ("openai", "gpt-4o-mini")
    assert resolve_model(None) == ("openai", "gpt-4o-mini")


def test_format_history_memory():
    hist = [{"role": "user", "content": "Bonjour"}, {"role": "assistant", "content": "Salut !"}]
    out = format_history(hist)
    assert "Utilisateur: Bonjour" in out and "Assistant: Salut !" in out
    assert lang_label("en") == "English" and lang_label(None) == "français"


# ----- Câblage routes ---------------------------------------------------------

def test_chat_stream_uses_pipeline_and_registry_endpoint():
    src = Path("/app/backend/routes/chat_advanced_routes.py").read_text(encoding="utf-8")
    assert "from agents import run_pipeline" in src
    assert "agent_events" in src
    assert '@router.get("/agents/registry")' in src


def test_agents_registry_route_registered():
    from server import app
    routes = {r.path for r in app.routes if hasattr(r, "path")}
    assert "/api/agents/registry" in routes
    assert "/api/chat/stream" in routes


def test_frontend_agent_activity_log_wired():
    log = Path("/app/frontend/src/components/AgentActivityLog.jsx").read_text(encoding="utf-8")
    assert "agent-activity-log" in log and "DiffView" in log
    chat = Path("/app/frontend/src/pages/Chat.js").read_text(encoding="utf-8")
    assert "AgentActivityLog" in chat and "evt.agent" in chat and "agent_events" in chat
