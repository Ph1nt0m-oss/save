"""iter99 — Tests pour :
- BotsAdminPanel frontend câblé dans Dashboard (admin/créa only)
- Fix vue forcée invité : la créa peut toujours modifier guest_view même en simulation
"""
import os


class TestBotsAdminPanelFrontend:
    """Panel admin frontend pour community bots."""

    def test_component_exists(self):
        path = "/app/frontend/src/components/BotsAdminPanel.jsx"
        assert os.path.exists(path)
        content = open(path).read()
        assert "bots-admin-panel" in content
        assert "bots-new-btn" in content
        assert "bots-admin-close" in content
        assert "bot-name-input" in content
        assert "bot-prompt-input" in content
        assert "bot-save-btn" in content
        assert "bot-edit-" in content
        assert "bot-delete-" in content
        assert "bot-card-" in content
        # API endpoints utilisés
        assert "/community-bots/list" in content
        assert "/community-bots/create" in content
        assert "/community-bots/delete" in content
        # 5 kinds disponibles
        assert "assistance:" in content
        assert "animation:" in content
        assert "jeu:" in content
        assert "information:" in content
        assert "modération:" in content

    def test_dashboard_wires_bots_panel(self):
        content = open("/app/frontend/src/pages/Dashboard.js").read()
        assert "import BotsAdminPanel" in content
        assert "<BotsAdminPanel" in content
        assert "showBotsAdmin" in content
        assert "header-bots-admin-btn" in content
        # Conditionnel sur admin OU creator
        assert "device.staff_kind === 'admin'" in content
        assert "device.role === 'creator'" in content


class TestGuestViewForceFix:
    """Fix : la créa physique peut toujours modifier guest_view, même en simulation."""

    def test_site_mode_badge_no_view_mode_guard(self):
        content = open("/app/frontend/src/components/SiteModeBadge.jsx").read()
        # iter99 — La condition viewMode !== 'guest' a été retirée
        assert "viewMode !== 'guest'" not in content
        # Le commentaire de fix est présent
        assert "iter99 — Fix utilisatrice" in content
        assert "isCreator = role === 'creator'" in content
