"""iter114 — Tests : Vue créatrice sélectionnable, gros écran 'Accès refusé'
(plus de petit toast), historique des modifications du site dans Programmation,
polling live AccountVisitView."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DASH = (ROOT / "frontend" / "src" / "pages" / "Dashboard.js").read_text()
VMP = (ROOT / "frontend" / "src" / "components" / "ViewModePicker.jsx").read_text()
PRIV = (ROOT / "frontend" / "src" / "pages" / "PrivateProgramming.js").read_text()
AVV = (ROOT / "frontend" / "src" / "components" / "AccountVisitView.jsx").read_text()
SERVER = (ROOT / "backend" / "server.py").read_text()


# ---------------------------------------------------------------------- Vue créatrice


def test_vue_creatrice_clickable_to_toggle():
    """iter115 — Vue Créatrice est cliquable + recliquable : active si
    viewMode === 'creator', décoche si recliquée (retour 'Aucune vue active').
    Modèle de toggle universel : active = m === viewMode."""
    assert "const active = m === viewMode;" in VMP


def test_view_mode_toggle_shows_none_when_no_view_active():
    """Le bouton du picker affiche 'Aucune vue active' quand viewMode est null,
    et le label de la vue active sinon (y compris 'Vue créatrice' si 'creator' sélectionné)."""
    assert "isActive ? t(current.labelKey) : 'Aucune vue active'" in VMP


# ---------------------------------------------------------------------- Big access denied


def test_caly_tile_navigates_without_early_toast():
    """La tuile Caly NAVIGUE toujours sur /private/caly-programming ; la page
    rend la grande boîte 'Accès refusé' si l'utilisateur n'a pas les droits."""
    # Recherche : entre la balise creator-caly-prog-btn et la motion.button précédente,
    # il NE DOIT PLUS y avoir de toast.error sur 'Accès refusé pour des raisons'.
    idx = DASH.find('data-testid="creator-caly-prog-btn"')
    assert idx > 0
    # Remonte sur ~600 chars pour trouver le onClick de la tile.
    window = DASH[max(0, idx - 800): idx]
    assert "toast.error('Accès refusé pour des raisons" not in window


def test_bots_tile_navigates_without_early_toast():
    idx = DASH.find('data-testid="creator-bots-prog-btn"')
    assert idx > 0
    window = DASH[max(0, idx - 800): idx]
    assert "toast.error('Accès refusé pour des raisons" not in window


def test_private_site_tile_navigates_without_early_toast():
    idx = DASH.find('data-testid="creator-private-site-btn"')
    assert idx > 0
    window = DASH[max(0, idx - 800): idx]
    assert "toast.error('Accès refusé pour des raisons" not in window


def test_private_ai_tile_navigates_without_early_toast():
    idx = DASH.find('data-testid="creator-private-ai-btn"')
    assert idx > 0
    window = DASH[max(0, idx - 800): idx]
    assert "toast.error('Accès refusé pour des raisons" not in window


def test_private_programming_renders_access_denied_panel():
    """PrivateProgramming.js conserve le grand panneau 'Accès refusé'."""
    assert 'data-testid="private-access-denied"' in PRIV
    assert "prog_access_denied" in PRIV
    assert "Lock" in PRIV  # icône lock


# ---------------------------------------------------------------------- Site changelog


def test_changelog_panel_in_site_programming():
    """SiteProgrammingPanel affiche l'historique des modifications du site."""
    assert 'data-testid="site-changelog-panel"' in PRIV
    assert 'data-testid="site-changelog-list"' in PRIV
    assert "/private/changelog" in PRIV
    assert "loadChanges" in PRIV
    # Rafraîchissement auto toutes les 30s
    assert "setInterval(loadChanges, 30000)" in PRIV


def test_backend_changelog_endpoint_exists():
    """L'endpoint /api/private/changelog existe et requiert signature créa."""
    assert '@api_router.post("/private/changelog")' in SERVER
    idx = SERVER.find('@api_router.post("/private/changelog")')
    block = SERVER[idx: idx + 2000]
    assert "_require_creator_signature" in block


# ---------------------------------------------------------------------- AccountVisitView live polling


def test_account_visit_view_polls_live():
    """AccountVisitView refresh les data toutes les 5 secondes pour suivi live."""
    assert "setInterval(fetch, 5000)" in AVV
    # Le polling utilise la même route /accounts/visit
    assert "/accounts/visit" in AVV


def test_account_visit_view_supports_deleted_projects_visual():
    """Les projets supprimés sont affichés avec opacity-40 (foncé)."""
    assert "p.is_deleted ? 'opacity-40 grayscale'" in AVV


def test_account_visit_view_creator_can_send_direct_message():
    """La créa peut écrire un MP au compte visité via /messages/send."""
    assert "/messages/send" in AVV
    assert "directMessage" in AVV
