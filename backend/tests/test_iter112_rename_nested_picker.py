"""iter112 — Tests pour : renommage tuiles Caly/Bots, suppression SiteIssues,
sidebar nested visuel (parent_chat_id), picker d'export multi-projets,
ajustements spacings (gap-6 + ml-[15cm] sur CreatorToolbar)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DASH = (ROOT / "frontend" / "src" / "pages" / "Dashboard.js").read_text()
APP = (ROOT / "frontend" / "src" / "App.js").read_text()
PCP = (ROOT / "frontend" / "src" / "pages" / "PrivateChatbotProgramming.js").read_text()


# ---------------------------------------------------------------------- Renaming


def test_caly_tile_renamed():
    """Tuile 'Programmation de Caly' présente avec testid creator-caly-prog-btn."""
    assert "creator-caly-prog-btn" in DASH
    assert "Programmation de Caly" in DASH
    assert "Chatbot assistant virtuel" in DASH
    assert "/private/caly-programming" in DASH


def test_bots_tile_replaces_issues():
    """Tuile 'Programmations des bots et chatbots' remplace 'Problèmes du site'."""
    assert "creator-bots-prog-btn" in DASH
    assert "Programmations des bots et chatbots" in DASH
    assert "/private/bots-programming" in DASH
    # L'ancienne tuile 'Problèmes du site' doit avoir disparu.
    assert "creator-issues-btn" not in DASH
    assert "Problèmes du site" not in DASH


def test_site_issues_page_deleted():
    """iter112 — Page SiteIssues.js abandonnée."""
    p = Path("/app/frontend/src/pages/SiteIssues.js")
    assert not p.exists()


def test_app_routes_caly_and_bots():
    """App.js wire deux routes distinctes : /private/caly-programming et /private/bots-programming."""
    assert "/private/caly-programming" in APP
    assert "/private/bots-programming" in APP
    # L'ancienne /private/site-issues doit pointer vers PrivateChatbotProgramming en mode bots.
    assert 'mode="bots"' in APP


def test_chatbot_programming_accepts_mode_prop():
    """PrivateChatbotProgramming.js accepte un prop mode='caly'|'bots' (sans tabs)."""
    assert "mode = 'caly'" in PCP
    assert "Programmation de Caly" in PCP
    assert "Programmations des bots et chatbots" in PCP
    # Les anciens tabs doivent avoir disparu.
    assert "chatbot-prog-tab-caly" not in PCP
    assert "chatbot-prog-tab-bots" not in PCP


# ---------------------------------------------------------------------- Sidebar nested


def test_sidebar_groups_projects_by_parent_chat():
    """La sidebar regroupe les enfants sous leur chat parent (parent_chat_id)."""
    # Recherche du code qui construit le tableau flat avec _depth et _parent.
    assert "parent_chat_id" in DASH
    assert "_depth" in DASH
    assert "byParent" in DASH
    assert "border-l-cyan-400/40" in DASH  # style indent enfant


# ---------------------------------------------------------------------- Export picker


def test_export_picker_state_and_modal():
    """Le picker d'export multi-projets a son state + son modal rendu."""
    assert "exportPicker" in DASH
    assert "setExportPicker" in DASH
    assert "export-picker-modal" in DASH
    assert "export-picker-cancel" in DASH
    assert "Quel projet exporter" in DASH


def test_export_picker_triggered_for_chat_with_multiple_children():
    """exportProject ouvre le picker si selectedProject est chat avec >=2 enfants."""
    # On vérifie la branche logique :
    assert "p.parent_chat_id === selectedProject.project_id" in DASH
    assert "children.length >= 2" in DASH


# ---------------------------------------------------------------------- Spacings


def test_header_tight_gap_iter112():
    """Le header utilise gap-6 (tight) + ml-12 sur CreatorToolbar (resserré, 15cm naturels au zoom 67%)."""
    assert "lg:gap-6" in DASH
    assert "ml-3 sm:ml-12 flex items-center gap-2 sm:gap-3 border-l" in DASH


def test_compte_button_closer_to_lang():
    """AccountsButton cluster a un ml réduit (sm:ml-2 au lieu de sm:ml-24)."""
    assert "gap-3 sm:gap-5 ml-3 sm:ml-2" in DASH
