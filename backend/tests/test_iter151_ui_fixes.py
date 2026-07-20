"""iter151 — 3 corrections rapides.

1. LoginAuxButtons AU-DESSUS des tabs Connexion/Inscription (image 1).
2. ViewSimulationBanner : ne PLUS afficher « LECTURE SEULE » quand
   aucune vue n'est active (image 2 — vue créa en mode écriture réel).
3. Cartes hero Dashboard réduites en hauteur (image 3 — plus de scroll).
"""
from pathlib import Path


REPO = Path("/app")
LOGIN = (REPO / "frontend/src/pages/Login.js").read_text()
BANNER = (REPO / "frontend/src/components/ViewSimulationBanner.jsx").read_text()
DASH = (REPO / "frontend/src/pages/Dashboard.js").read_text()


def test_login_aux_buttons_above_tabs_iter151():
    """LoginAuxButtons doit apparaître AVANT les tabs Connexion/Inscription."""
    idx_aux = LOGIN.find('<LoginAuxButtons')
    idx_tab_login = LOGIN.find('data-testid="tab-login"')
    idx_tab_signup = LOGIN.find('data-testid="tab-signup"')
    assert idx_aux > 0
    assert idx_aux < idx_tab_login, "LoginAuxButtons doit être au-dessus de tab-login"
    assert idx_aux < idx_tab_signup, "LoginAuxButtons doit être au-dessus de tab-signup"


def test_view_simulation_banner_hides_when_no_view_active_iter151():
    """Quand viewMode est null/vide, le bandeau NE DOIT PAS s'afficher."""
    # Vérifie la présence de la garde explicite.
    assert 'if (!viewMode) return null;' in BANNER, \
        "ViewSimulationBanner doit early-return quand viewMode est null"
    # Vérifie qu'on n'utilise plus le fallback `viewMode || 'creator'`.
    assert "activeMode = viewMode || 'creator'" not in BANNER


def test_dashboard_hero_cards_reduced_height_iter151():
    """Les 4 cartes hero (online-chat/create + offline-chat/create) ont un
    padding réduit (p-8 → p-4 sm:p-5) et un espace interne compact."""
    # Aucune carte ne doit plus utiliser p-8 (padding excessif).
    p8_count = DASH.count('rounded-lg p-8 backdrop-blur-xl')
    assert p8_count == 0, f"Il reste {p8_count} cartes en p-8 (spec: réduire)"
    # Les 4 cartes utilisent p-4 sm:p-5.
    p4_count = DASH.count('rounded-lg p-4 sm:p-5 backdrop-blur-xl')
    assert p4_count == 4, f"Attendu 4 cartes en p-4 sm:p-5, trouvé {p4_count}"
    # Titres réduits de text-2xl vers text-lg sm:text-xl.
    assert "text-lg sm:text-xl font-['Chivo'] font-bold mb-1" in DASH
    # Icônes internes réduites (16→12 desktop).
    assert 'w-11 h-11 sm:w-12 sm:h-12 bg-[#E4FF00] rounded-full' in DASH


def test_no_regression_login_aux_still_has_5_views():
    src = (REPO / "frontend/src/components/LoginAuxButtons.jsx").read_text()
    for view in ('creator', 'user', 'modo', 'admin', 'guest'):
        assert f"key: '{view}'" in src


def test_no_regression_read_only_badge_still_present_when_active():
    """iter149 D — Le badge lecture seule reste affiché quand une vue EST active."""
    assert 'read-only-badge' in BANNER
    assert 'Lecture seule' in BANNER
