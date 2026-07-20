"""iter156 — Chaque IA conserve son identité propre via `build_identity_fragment`.

Le fragment est injecté dans le prompt système APRÈS la base modulaire et
AVANT le profil personnalisé de la Créa. L'ordre garantit :
  1. Base = module d'origine (jamais écrasé).
  2. Identité registry = rôle/expertise/format/outils/limites de l'agent.
  3. Profil Créa = surcharges custom (optionnelles).
"""
import asyncio
from pathlib import Path

BACKEND = Path("/app/backend")


def test_build_identity_fragment_uses_registry_card():
    from utils.ai_profile_injector import build_identity_fragment
    frag = build_identity_fragment("gpt_5_5")
    assert "GPT 5.5" in frag, "Le nom de l'agent doit apparaître"
    assert "OBJECTIF PROPRE" in frag
    assert "EXPERTISE" in frag
    assert "FORMAT DE RÉPONSE ATTENDU" in frag
    # Règle absolue anti-fusion.
    assert "conserve TON identité" in frag
    assert "NE PAS FUSIONNER" in frag


def test_identity_fragment_differs_per_agent():
    """Deux agents doivent produire des identités DIFFÉRENTES."""
    from utils.ai_profile_injector import build_identity_fragment
    f_codex = build_identity_fragment("gpt_5_3_codex")
    f_fable = build_identity_fragment("claude_5_fable")
    f_planner = build_identity_fragment("planner")
    assert f_codex != f_fable != f_planner
    assert "code" in f_codex.lower() or "codex" in f_codex.lower()
    assert "narrat" in f_fable.lower() or "fable" in f_fable.lower() or "récit" in f_fable.lower()
    assert "planif" in f_planner.lower() or "archi" in f_planner.lower() or "plan" in f_planner.lower()


def test_identity_fragment_empty_for_unknown_agent():
    from utils.ai_profile_injector import build_identity_fragment
    assert build_identity_fragment("no_such_agent") == ""
    assert build_identity_fragment("") == ""


def test_compose_system_prompt_stacks_identity_and_profile():
    """Ordre attendu : base → identité → profil (surcharge finale)."""
    from utils.ai_profile_injector import compose_system_prompt

    class _MockDB:
        class ai_profiles:
            @staticmethod
            async def find_one(q, *_a, **_kw):
                if q.get("agent_id") == "gpt_5_3_codex":
                    return {"profile": {"writing_style": "MON_STYLE_CODEX"}}
                return None

    async def _run():
        r = await compose_system_prompt(_MockDB(), "gpt_5_3_codex", "BASE_TEXT")
        return r
    r = asyncio.run(_run())
    # base présent + identité + profil
    assert r.startswith("BASE_TEXT")
    assert "GPT 5.3 Codex" in r
    assert "MON_STYLE_CODEX" in r
    # L'ordre : identité AVANT profil (car profil = surcharge Créa finale).
    assert r.index("GPT 5.3 Codex") < r.index("MON_STYLE_CODEX")


def test_compose_system_prompt_returns_base_plus_identity_without_profile():
    """Sans profil configuré, on retourne base + identité seule."""
    from utils.ai_profile_injector import compose_system_prompt

    class _MockDB:
        class ai_profiles:
            @staticmethod
            async def find_one(*_a, **_kw):
                return None

    r = asyncio.run(compose_system_prompt(_MockDB(), "grok_4_20_reasoning", "BASE"))
    assert r.startswith("BASE")
    assert "Grok 4.20 Reasoning" in r
    assert "PROGRAMMATION SPÉCIFIQUE" not in r  # pas de profil


def test_all_entry_points_use_compose_system_prompt_iter156():
    """Tous les entry-points passent maintenant par compose_system_prompt
    qui inclut l'identité registry."""
    entries = [
        "backend/server.py",
        "backend/routes/caly_routes.py",
        "backend/routes/community_bots_routes.py",
        "backend/agents/chat_agent.py",
        "backend/agents/dev_agent.py",
        "backend/agents/planner_agent.py",
    ]
    for e in entries:
        src = (Path("/app") / e).read_text()
        assert "compose_system_prompt" in src, f"{e} doit appeler compose_system_prompt"


def test_two_agents_get_isolated_identities():
    """Contrat critique : jamais de fusion cross-agent."""
    from utils.ai_profile_injector import compose_system_prompt

    class _MockDB:
        class ai_profiles:
            @staticmethod
            async def find_one(*_a, **_kw):
                return None

    async def _run():
        r1 = await compose_system_prompt(_MockDB(), "dev", "BASE_DEV")
        r2 = await compose_system_prompt(_MockDB(), "planner", "BASE_PLAN")
        return r1, r2
    r1, r2 = asyncio.run(_run())
    assert "Forge" in r1 and "Archi" not in r1, "dev ne doit contenir QUE son identité"
    assert "Archi" in r2 and "Forge" not in r2, "planner ne doit contenir QUE son identité"


def test_dev_agent_progression_events_visible_to_user():
    """iter156 audit — Le dev_agent émet bien des événements opérationnels
    (analyse / recherche / fichiers / exécution / validation) et jamais de
    raisonnement interne privé."""
    src = (BACKEND / "agents" / "dev_agent.py").read_text()
    # 5 étapes visibles utilisateur.
    for evt in ('"status"', '"status_done"', '"search_done"', '"file_viewed"',
                '"file_created"', '"file_modified"', '"code_executed"',
                '"validation"'):
        assert evt in src, f"événement {evt} manquant"
    # Le prompt planner impose 'label' opérationnel court, pas de raisonnement privé.
    reg = (BACKEND / "agents" / "registry.py").read_text()
    assert 'pas de raisonnement privé' in reg
