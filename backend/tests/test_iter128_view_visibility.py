"""iter128 — Visibilité des outils par rôle/vue (image 1-5 utilisatrice).

Vérifie au niveau source que :
  - `useViewSpec` expose les nouveaux flags (canSeeAccountsButton,
    canSeeMegaphone, canSeeExports, canSeeRobotBots, canSeeAdminProgsCards,
    canSeeQuickWizard, canSeeCreatorProgsCards, canRenameFromAccountsPanel,
    canForceVisitorFromAccountsPanel, canExcludeFromAccountsPanel,
    canBanFromAccountsPanel, canDeleteFromAccountsPanel).
  - Dashboard.js wraps les cards admin/wizard/creator dans des conditions.
  - Landing.js et Login.js ne montent plus `<AccountsButton />` ni le
    sélecteur de vue (`hideViewModePicker`).
  - CalyChatbot masque la bulle sur les routes publiques (/, /login,
    /signup, /reset-password, ...).
  - UserMenu accepte la prop `hideEmailAndProfile`.
"""
from __future__ import annotations
from pathlib import Path


FRONT = Path("/app/frontend/src")


def _read(p):
    return (FRONT / p).read_text(encoding="utf-8")


def test_useViewSpec_exposes_new_flags():
    src = _read("hooks/useViewSpec.js")
    for flag in [
        "canSeeAccountsButton",
        "canSeeMegaphone",
        "canSeeExports",
        "canSeeIdeasLightbulb",
        "canSeeRobotBots",
        "canSeeAdminProgsCards",
        "canSeeQuickWizard",
        "canSeeCreatorProgsCards",
        "canRenameFromAccountsPanel",
        "canForceVisitorFromAccountsPanel",
        "canExcludeFromAccountsPanel",
        "canBanFromAccountsPanel",
        "canDeleteFromAccountsPanel",
    ]:
        assert flag in src, f"flag manquant : {flag}"


def test_dashboard_uses_view_gating():
    src = _read("pages/Dashboard.js")
    # Cards admin (Caly + Bots) conditionnelles
    assert "canSeeAdminProgsCards" in src
    # Wizard conditionnel
    assert "canSeeQuickWizard" in src
    # Cards créa (site + IA) conditionnelles
    assert "canSeeCreatorProgsCards" in src
    # AccountsButton conditionnel
    assert "canSeeAccountsButton" in src
    # Crown ViewModePicker masqué via prop
    assert "hideViewModePicker" in src
    # Exports conditionnels
    assert "canSeeExports" in src
    # Megaphone conditionnel
    assert "canSeeMegaphone" in src
    # UserMenu reçoit hideEmailAndProfile
    assert "hideEmailAndProfile" in src


def test_landing_removes_accounts_and_creator_picker():
    src = _read("pages/Landing.js")
    # Plus de <AccountsButton .../>
    assert "<AccountsButton" not in src
    # CreatorToolbar avec hideViewModePicker
    assert "hideViewModePicker" in src


def test_login_removes_accounts_and_creator_message():
    src = _read("pages/Login.js")
    # Plus de <AccountsButton /> (header)
    assert "<AccountsButton" not in src
    # Plus de <MessageButton variant="icon" /> (creator-only msg)
    assert 'MessageButton variant="icon"' not in src


def test_caly_chatbot_hides_on_public_routes():
    src = _read("components/CalyChatbot.jsx")
    assert "useLocation" in src
    assert "HIDDEN_ON" in src
    assert "'/login'" in src
    assert "'/signup'" in src


def test_user_menu_supports_hide_email_and_profile():
    src = _read("components/UserMenu.jsx")
    assert "hideEmailAndProfile" in src


def test_creator_toolbar_supports_hide_view_mode_picker():
    src = _read("components/CreatorToolbar.jsx")
    assert "hideViewModePicker" in src


def test_account_visit_view_filters_tabs_for_limited_roles():
    src = _read("components/AccountVisitView.jsx")
    assert "targetIsLimited" in src


def test_accounts_button_gates_actions_by_role():
    src = _read("components/AccountsButton.jsx")
    # Visit retiré pour TOUS les rôles
    assert "canVisit = vs.canVisitAccountFromList" in src
    # Action gating
    assert "canRename" in src
    assert "canForceVisitor" in src
    assert "canExclude" in src
    assert "canBan" in src
    assert "canDelete" in src
