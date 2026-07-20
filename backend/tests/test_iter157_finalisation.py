"""iter157 — Finalisation : Caly visible sur pages publiques (login/signup/landing)
+ audit AI identity chains + audit exécution agents avec progression visible.
"""
from pathlib import Path


REPO = Path("/app")
CALY = (REPO / "frontend/src/components/CalyChatbot.jsx").read_text()


def test_caly_visible_on_login_signup_landing():
    """Spec iter157 : Caly présente sur les pages où un visiteur non
    connecté peut avoir besoin d'aide."""
    # Les 3 routes utilisateur sont explicitement EXCLUES du hidden set.
    assert "'/login'" not in CALY
    assert "'/signup'" not in CALY
    # '/' n'est plus dans HIDDEN_ON (landing accessible aussi).
    idx = CALY.find('HIDDEN_ON = [')
    tail = CALY[idx: idx + 200]
    assert "'/'" not in tail


def test_caly_still_hidden_on_technical_screens():
    """Les écrans techniques (reset, verify, theft, sms) doivent
    rester sans Caly (workflow contraint)."""
    assert "'/reset-password'" in CALY
    assert "'/verify-email'" in CALY
    assert "'/theft-confirm'" in CALY
    assert "'/sms-login'" in CALY


def test_caly_system_prompt_remains_help_focused():
    """Caly doit conserver son rôle d'ASSISTANCE et jamais devenir un
    agent de génération de code."""
    assert "assistante d'aide à l'utilisation" in CALY
    assert "Tu ne crées PAS" in CALY


def test_ai_identity_chain_intact_iter156_regression():
    """Régression iter156 : compose_system_prompt reste branché dans les
    6 entry-points."""
    entries = [
        "backend/server.py",
        "backend/routes/caly_routes.py",
        "backend/routes/community_bots_routes.py",
        "backend/agents/chat_agent.py",
        "backend/agents/dev_agent.py",
        "backend/agents/planner_agent.py",
    ]
    for e in entries:
        src = (REPO / e).read_text()
        assert "compose_system_prompt" in src, f"{e} doit appeler compose_system_prompt"


def test_dev_agent_emits_progression_events():
    """Progression visible utilisateur (Emergent-style) : audit complet
    des événements émis par dev_agent."""
    src = (REPO / "backend/agents/dev_agent.py").read_text()
    for evt in ('status', 'status_done', 'search_done',
                'file_viewed', 'file_created', 'file_modified',
                'code_executed', 'validation'):
        assert f'"{evt}"' in src, f'événement "{evt}" manquant'


def test_no_private_reasoning_leaked_in_prompts():
    """Le prompt planner interdit d'exposer le raisonnement privé."""
    reg = (REPO / "backend/agents/registry.py").read_text()
    assert 'pas de raisonnement privé' in reg


def test_agent_registry_lists_all_supported_models():
    """Vérifie que l'inventaire des IA disponibles est bien peuplé."""
    reg = (REPO / "backend/agents/registry.py").read_text()
    # Chaque famille de modèle représentée.
    for aid in ('gpt_5_5', 'claude_4_6_sonnet', 'claude_5_fable',
                'gpt_5_3_codex', 'grok_4_20_reasoning', 'gemini_3_1_pro'):
        assert f'"{aid}"' in reg or f"'{aid}'" in reg, f"agent {aid} manquant dans le registry"


def test_full_regression_iter141_to_157_intact():
    """Verrouille les pré-requis structurels critiques."""
    # Ai profile injector présent + expose l'API attendue.
    inj = (REPO / "backend/utils/ai_profile_injector.py").read_text()
    for fn in ('build_identity_fragment', 'compose_system_prompt',
               'load_profile', 'build_profile_fragment'):
        assert f'def {fn}' in inj, f"fonction {fn} manquante"
    # Bot analyzer 2 couches (iter147).
    ba = (REPO / "backend/utils/bot_analyzer.py").read_text()
    assert 'analyze_message_combined' in ba
    # Mentions router (iter147).
    server = (REPO / "backend/server.py").read_text()
    assert 'build_mentions_router' in server
    # Unread router (iter150).
    assert 'build_unread_router' in server
    # Tutorial interactif via portal (iter153).
    tut = (REPO / "frontend/src/components/InteractiveTutorial.jsx").read_text()
    assert 'createPortal(tree, document.body)' in tut
