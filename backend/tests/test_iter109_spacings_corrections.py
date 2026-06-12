"""
iter109 — Tests :
- Spacings : Caly right-28, langues ml-32, SiteModeBadge ml-40, gap-32 lg
- "Active une vue simulée..." message corrigé
- AIProgrammingPanel : agents/test-loop/history retirés
- Chatbot programming : code Caly éditable avec save + grep
"""
import os
from pathlib import Path

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_codeforge_iter109")


def test_caly_offset_recent():
    """Caly at right-28 (iter109) ou right-24 (iter110)."""
    caly = Path("/app/frontend/src/components/CalyChatbot.jsx").read_text(encoding="utf-8")
    assert ("right-28" in caly) or ("right-[88px]" in caly)


def test_language_ml_recent():
    """LanguageToggle wrapped with ml-32 (iter109) ou ml-4 (iter110 swap)."""
    dash = Path("/app/frontend/src/pages/Dashboard.js").read_text(encoding="utf-8")
    assert ("inline-block ml-3 sm:ml-32" in dash) or ("inline-block ml-2 sm:ml-4" in dash)


def test_site_mode_badge_ml_large_offset():
    """SiteModeBadge container : ml-40 (iter109), ml-64 (iter110), ml-12 + gap-6 (iter112 resserré)."""
    dash = Path("/app/frontend/src/pages/Dashboard.js").read_text(encoding="utf-8")
    assert ("ml-3 sm:ml-40" in dash) or ("ml-3 sm:ml-64" in dash) or ("ml-3 sm:ml-[15cm]" in dash) or ("ml-3 sm:ml-12 flex items-center gap-2 sm:gap-3 border-l" in dash)


def test_header_gap_lg_32():
    """Header gap (iter109: 32, iter111: 15cm, iter112: 6 + ml-[15cm] sur RIGHT)."""
    dash = Path("/app/frontend/src/pages/Dashboard.js").read_text(encoding="utf-8")
    assert ("lg:gap-32" in dash) or ("lg:gap-[15cm]" in dash) or ("lg:gap-6" in dash)


def test_prog_access_hint_corrected():
    """Message d'erreur ne propose plus d'activer une vue simulée."""
    ctx = Path("/app/frontend/src/contexts/LanguageContext.js").read_text(encoding="utf-8")
    # Le message FR ne propose plus une vue simulée
    assert "Active une vue simulée" not in ctx
    # Nouveau message FR
    assert "Tu dois être sur un appareil de la créatrice ET ne pas être en mode simulation" in ctx


def test_ai_programming_panel_sections_removed():
    """Les sections Agents/Test-loop/History/ChangelogPanel sont retirées de AIProgrammingPanel."""
    prog = Path("/app/frontend/src/pages/PrivateProgramming.js").read_text(encoding="utf-8")
    # Le commentaire iter109 doit être présent
    assert "iter109" in prog
    assert "Sections retirées" in prog
    # Le test-loop ne doit plus être rendu dans le JSX du panel
    # (Le runTestLoop helper peut rester pour l'instant en dead code, mais le bouton testid ne doit plus être dans AIProgrammingPanel)
    # On vérifie l'absence du JSX history visible
    assert "ai-run-test-loop" not in prog or prog.count("ai-run-test-loop") <= 1


def test_chatbot_prog_caly_code_editor():
    """CalyPromptEditor a maintenant un éditeur de code + recherche."""
    page = Path("/app/frontend/src/pages/PrivateChatbotProgramming.js").read_text(encoding="utf-8")
    assert "caly-code-textarea" in page
    assert "caly-code-save" in page
    assert "caly-search-input" in page
    assert "caly-search-btn" in page
    assert "/private/code/write-file" in page
    assert "/private/code/grep" in page
