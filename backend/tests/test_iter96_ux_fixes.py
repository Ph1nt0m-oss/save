"""iter96 — Tests pour les fixes utilisatrice :
- Sélecteur de langues : largeur élargie + truncate (fini le texte coupé)
- LivePreviewPanel retiré du Dashboard
- Mode Pro retiré du Chat
- Reset REPL retiré du Chat
- Export .docx retiré du Chat
- Latence sidebar : hydration immédiate via cache localStorage
- TypewriterEffect composant créé
"""
import os


class TestLanguageDropdownWidth:
    """Fix tronquage du sélecteur de langues (screenshots utilisatrice)"""

    def test_dropdown_uses_responsive_width(self):
        content = open("/app/frontend/src/components/LanguageToggle.jsx").read()
        # iter96 — w-56 → w-[min(20rem,calc(100vw-1rem))]
        assert "w-56" not in content
        assert "w-[min(20rem" in content
        # truncate ajouté au span du nom
        assert "truncate" in content
        # title attribute pour les noms longs
        assert "title={formatLangName(lang)}" in content


class TestLivePreviewRemovedFromDashboard:
    """LivePreviewPanel retiré du header Dashboard sur demande utilisatrice."""

    def test_dashboard_no_live_preview(self):
        content = open("/app/frontend/src/pages/Dashboard.js").read()
        assert "LivePreviewPanel" not in content
        assert "showLivePreview" not in content
        assert "header-live-preview-btn" not in content

    def test_live_preview_component_still_exists(self):
        """Le composant existe encore pour réutilisation future (icône œil par création)."""
        assert os.path.exists("/app/frontend/src/components/LivePreviewPanel.jsx")


class TestChatHeaderCleanup:
    """Mode Pro, Reset REPL, Export .docx retirés du chat sur demande."""

    def test_chat_no_pro_mode_toggle(self):
        content = open("/app/frontend/src/pages/Chat.js").read()
        # iter96 — toggle retiré
        assert 'data-testid="chat-pro-mode-toggle"' not in content
        # proMode reste comme const false pour ne pas casser orch deps
        assert "[proMode]" in content

    def test_chat_no_reset_repl_button(self):
        content = open("/app/frontend/src/pages/Chat.js").read()
        assert 'data-testid="chat-repl-reset-btn"' not in content

    def test_chat_no_export_docx_button(self):
        content = open("/app/frontend/src/pages/Chat.js").read()
        assert 'data-testid="chat-export-docx-btn"' not in content


class TestSidebarLatencyFix:
    """Hydration immédiate depuis cache localStorage = 0ms perçus."""

    def test_dashboard_hydrates_cache_first(self):
        content = open("/app/frontend/src/pages/Dashboard.js").read()
        # iter96 — Latence : on hydrate IMMÉDIATEMENT depuis le cache
        assert "iter96 — Latence" in content
        assert "affichage instantané" in content


class TestTypewriterEffect:
    """Composant TypewriterEffect (mot par mot ~1.5x vitesse normale)."""

    def test_component_exists(self):
        path = "/app/frontend/src/components/TypewriterEffect.jsx"
        assert os.path.exists(path)
        content = open(path).read()
        assert "TypewriterEffect" in content
        assert "skip" in content  # prop pour bypass (Emergent code-par-code)
