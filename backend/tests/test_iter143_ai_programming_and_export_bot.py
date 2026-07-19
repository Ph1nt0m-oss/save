"""iter143 — Tests source-level pour :
 - AI Programming registry étendu (Emergent, Vexub, Claude, GPT, Grok, ...)
 - Endpoints /agents/profile/{get,save,versions,revert,list-all}
 - Bot validateur d'export : analyze_export_request + get_export_report
 - /exports/bot-report endpoint enrichi (header uniforme)
 - /exports/pending retourne public_handle
 - Icône historique dupliqué retiré de AccountsButton
"""
import sys
import inspect
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))


def test_registry_has_new_llms():
    from backend.agents.registry import AGENT_REGISTRY
    expected = {
        "emergent_llm", "vexub_video", "claude_5_fable", "gpt_5_5",
        "claude_4_8_opus", "claude_4_7_opus_1m", "claude_4_6_sonnet",
        "gpt_5_3_codex", "gemini_3_1_pro", "gpt_5_4_1m", "grok_4_3",
        "grok_4_20_reasoning", "lindy_flow", "ollama_offline",
        "bot_analyzer", "bot_export_validator",
    }
    have = set(AGENT_REGISTRY.keys())
    missing = expected - have
    assert not missing, f"IA manquantes du registre : {missing}"


def test_ai_programming_endpoints_defined():
    from backend.routes import ai_programming_routes
    src = inspect.getsource(ai_programming_routes.build_ai_programming_router)
    assert '/agents/profile/get' in src
    assert '/agents/profile/save' in src
    assert '/agents/profile/versions' in src
    assert '/agents/profile/revert' in src
    assert '/agents/profile/list-all' in src


def test_ai_programming_allowed_fields():
    from backend.routes.ai_programming_routes import ALLOWED_FIELDS
    expected = {
        "writing_style", "behavior", "domains", "limits", "capabilities",
        "allowed_tools", "specializations", "custom_system_prompt",
        "response_format", "reasoning_mode", "notes",
    }
    assert expected == ALLOWED_FIELDS


def test_ai_programming_creator_only():
    from backend.routes import ai_programming_routes
    src = inspect.getsource(ai_programming_routes.build_ai_programming_router)
    assert '_require_creator' in src
    assert 'creator' in src


def test_ai_programming_versioning_present():
    from backend.routes import ai_programming_routes
    src = inspect.getsource(ai_programming_routes.build_ai_programming_router)
    assert 'ai_profile_versions' in src
    assert 'archived_at' in src
    assert 'version_id' in src


def test_export_validator_bot_present():
    from backend.utils import export_validator_bot
    assert hasattr(export_validator_bot, 'analyze_export_request')
    assert hasattr(export_validator_bot, 'get_export_report')


def test_export_bot_report_endpoint_defined():
    from backend.routes import exports_routes
    src = inspect.getsource(exports_routes.build_exports_router) \
        if hasattr(exports_routes, 'build_exports_router') \
        else Path("/app/backend/routes/exports_routes.py").read_text()
    assert '/exports/bot-report' in src
    assert 'header' in src


def test_export_pending_returns_public_handle():
    content = Path("/app/backend/routes/exports_routes.py").read_text()
    assert 'public_handle' in content
    assert 'handle_by_email' in content


def test_export_request_triggers_bot():
    content = Path("/app/backend/routes/exports_routes.py").read_text()
    assert 'analyze_export_request' in content
    assert 'asyncio.create_task' in content or 'create_task' in content


def test_ai_programming_frontend_page_exists():
    p = Path("/app/frontend/src/pages/AIProgramming.js")
    assert p.exists()
    content = p.read_text()
    assert 'ai-prog-save' in content
    assert 'ai-prog-history' in content
    assert 'ai-prog-note' in content
    assert 'Programmation des IA' in content


def test_export_notifier_has_bot_report_button():
    p = Path("/app/frontend/src/components/ExportApprovalNotifier.jsx")
    content = p.read_text()
    assert 'exp-bot-report-btn' in content
    assert 'bot-report-summary' in content
    assert 'Identité publique' in content
    # Le champ device retiré (remplacé par public_handle).
    assert 'exp-field-device' not in content or 'exp-field-handle' in content
    assert 'exp-field-handle' in content


def test_accounts_button_removes_duplicate_export_icon():
    p = Path("/app/frontend/src/components/AccountsButton.jsx")
    content = p.read_text()
    # Le composant ExportRequestsHistoryButton n'est plus rendu dans le
    # header de AccountsButton (retiré iter143).
    assert '<ExportRequestsHistoryButton onClose={() => setOpen(false)} t={t} />' not in content


def test_app_routes_ai_programming():
    p = Path("/app/frontend/src/App.js")
    content = p.read_text()
    assert '/private/ai-programming' in content
    assert 'AIProgramming' in content


def test_registry_page_has_ai_programming_link():
    p = Path("/app/frontend/src/pages/PrivateAgentRegistry.js")
    content = p.read_text()
    assert 'registry-open-ai-programming' in content
    assert '/private/ai-programming' in content
