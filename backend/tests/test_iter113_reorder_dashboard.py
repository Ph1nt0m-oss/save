"""iter113 — Tests : Caly fab 0.2cm à droite, dropdowns coordonnés (1 seul ouvert),
réorganisation Dashboard (Programme admin EN HAUT > Création accompagnée > 4 tchats > Programmation créa)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DASH = (ROOT / "frontend" / "src" / "pages" / "Dashboard.js").read_text()
CALY = (ROOT / "frontend" / "src" / "components" / "CalyChatbot.jsx").read_text()
SMB = (ROOT / "frontend" / "src" / "components" / "SiteModeBadge.jsx").read_text()
VMP = (ROOT / "frontend" / "src" / "components" / "ViewModePicker.jsx").read_text()
CTB = (ROOT / "frontend" / "src" / "components" / "CreatorToolbar.jsx").read_text()


# ---------------------------------------------------------------------- Caly fab


def test_caly_fab_advanced_right_by_0_2cm():
    """Caly fab : right-24 (96px) → right-[88px] (~8px de moins ≈ 0.2cm vers la droite)."""
    assert "right-[88px]" in CALY
    assert "right-24 z-" not in CALY


# ---------------------------------------------------------------------- Dropdowns coordonnés


def test_sitemode_dropdown_repositioned():
    """SiteModeBadge dropdown remis à right-0 (la non-superposition est assurée
    par la coordination des dropdowns au niveau CreatorToolbar)."""
    assert "absolute right-0 mt-1.5 w-72" in SMB


def test_sitemode_accepts_controlled_open():
    """SiteModeBadge accepte controlledOpen + onOpenChange props."""
    assert "controlledOpen" in SMB
    assert "onOpenChange" in SMB


def test_viewmode_accepts_controlled_open():
    """ViewModePicker accepte controlledOpen + onOpenChange props."""
    assert "controlledOpen" in VMP
    assert "onOpenChange" in VMP


def test_creator_toolbar_coordinates_dropdowns():
    """CreatorToolbar maintient un état openDropdown (null|'site'|'view')
    pour qu'un seul dropdown soit ouvert à la fois."""
    assert "openDropdown" in CTB
    assert "setOpenDropdown" in CTB
    assert "controlledOpen={openDropdown === 'site'}" in CTB
    assert "controlledOpen={openDropdown === 'view'}" in CTB


# ---------------------------------------------------------------------- Dashboard reorganization


def test_admin_prog_row_present_above_creation_accompagnee():
    """Le bloc 'Programme admin' (testid admin-prog-row) doit apparaître
    AVANT 'Création rapide accompagnée' dans le JSX."""
    assert 'data-testid="admin-prog-row"' in DASH
    admin_pos = DASH.find('data-testid="admin-prog-row"')
    creation_pos = DASH.find("Création rapide accompagnée")
    assert admin_pos > 0 and creation_pos > 0
    assert admin_pos < creation_pos, (
        "Le bloc admin-prog-row (Caly + Bots) doit apparaître AVANT 'Création rapide accompagnée'"
    )


def test_caly_and_bots_tiles_inside_admin_row():
    """Les 2 tuiles Caly + Bots sont DANS le bloc admin-prog-row."""
    admin_start = DASH.find('data-testid="admin-prog-row"')
    # Trouve la fermeture du div correspondant — on prend les ~5000 chars après.
    block = DASH[admin_start: admin_start + 5000]
    assert "creator-caly-prog-btn" in block
    assert "creator-bots-prog-btn" in block


def test_creator_only_tiles_remain_below():
    """Programmation du site + Programmation des IA restent en bas (créa-only)."""
    # Vérification de l'ordre : guided-wizard < tchats < programmation créa.
    wizard_pos = DASH.find('data-testid="guided-wizard-btn"')
    online_chat_pos = DASH.find('data-testid="online-chat-btn"')
    private_site_pos = DASH.find('data-testid="creator-private-site-btn"')
    private_ai_pos = DASH.find('data-testid="creator-private-ai-btn"')
    assert 0 < wizard_pos < online_chat_pos < private_site_pos
    assert private_site_pos < private_ai_pos
