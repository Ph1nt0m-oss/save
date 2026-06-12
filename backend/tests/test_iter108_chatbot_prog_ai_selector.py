"""
iter108 — Tests for chatbot programming page + AI selector + spacings.
"""
import os
from pathlib import Path

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_codeforge_iter108")


def test_chatbot_programming_page_exists():
    """New page file must exist."""
    p = Path("/app/frontend/src/pages/PrivateChatbotProgramming.js")
    assert p.exists()
    content = p.read_text(encoding="utf-8")
    assert "CalyPromptEditor" in content
    assert "BotsCommunityList" in content
    assert "/caly/config" in content


def test_chatbot_programming_route_wired():
    """App.js must declare the route /private/chatbot-programming."""
    app = Path("/app/frontend/src/App.js").read_text(encoding="utf-8")
    assert "import PrivateChatbotProgramming" in app
    assert "/private/chatbot-programming" in app


def test_dashboard_has_chatbot_prog_button():
    """Dashboard.js has the new card button."""
    dash = Path("/app/frontend/src/pages/Dashboard.js").read_text(encoding="utf-8")
    assert "creator-chatbot-prog-btn" in dash
    assert "/private/chatbot-programming" in dash
    assert "MessageCircleQuestion" in dash


def test_ai_programming_panel_has_selector():
    """PrivateProgramming.js : AIProgrammingPanel has the AI selector."""
    prog = Path("/app/frontend/src/pages/PrivateProgramming.js").read_text(encoding="utf-8")
    assert "ai-code-selector" in prog
    assert "ai-code-selector-dropdown" in prog
    assert "AI_CODE_FILES" in prog
    # All AIs configured
    for ai in ("orchestrator", "claude", "gemini", "grok", "gpt", "lindy", "locale", "caly"):
        assert f"{ai}:" in prog or f"'{ai}'" in prog


def test_caly_right_32_iter108():
    """Caly at right-32 (~7cm to right by 1cm)."""
    caly = Path("/app/frontend/src/components/CalyChatbot.jsx").read_text(encoding="utf-8")
    assert "right-32" in caly


def test_language_5cm_right_separate():
    """LanguageToggle wrapped in span with ml-12."""
    dash = Path("/app/frontend/src/pages/Dashboard.js").read_text(encoding="utf-8")
    assert "iter108" in dash
    # The wrap with ml around LanguageToggle
    assert 'inline-block ml-3 sm:ml-12' in dash


def test_site_mode_badge_3cm_more_left():
    """CreatorToolbar uses larger gap-8 between SiteModeBadge and rest."""
    ct = Path("/app/frontend/src/components/CreatorToolbar.jsx").read_text(encoding="utf-8")
    assert "sm:gap-8" in ct
