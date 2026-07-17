"""iter136 — Tests : nouvel onglet WhoCanView + WhoCanVisit simplifié + bloc guest retiré."""
import os
from pathlib import Path

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_codeforge_iter136")

ROOT = Path("/app/backend")
FRONT = Path("/app/frontend/src")


def _read(p):
    return (ROOT / p).read_text(encoding="utf-8")


def _rf(p):
    return (FRONT / p).read_text(encoding="utf-8")


class TestNewWhoCanViewComponent:
    def test_component_exists(self):
        assert (FRONT / "components/WhoCanViewBadge.jsx").is_file()

    def test_six_keys_in_exact_order(self):
        src = _rf("components/WhoCanViewBadge.jsx")
        # Ordre imposé par utilisateur : private, public, guest, modo, admin, creator
        order = ["'private'", "'public'", "'guest'", "'modo'", "'admin'", "'creator'"]
        # Extrait la section VIEW_KEYS
        idx = src.find("const VIEW_KEYS")
        assert idx != -1
        block = src[idx:idx + 1200]
        positions = [block.find(f"id: {k}") for k in order]
        # Toutes trouvées et strictement croissantes.
        assert all(p != -1 for p in positions)
        assert positions == sorted(positions)

    def test_min_one_selection(self):
        src = _rf("components/WhoCanViewBadge.jsx")
        assert "Impossible de tout décocher" in src
        assert "Au moins une case doit rester cochée" in src

    def test_test_ids_present(self):
        src = _rf("components/WhoCanViewBadge.jsx")
        assert 'data-testid="who-can-view-toggle"' in src
        assert 'data-testid="who-can-view-dropdown"' in src
        for k in ("private", "public", "guest", "modo", "admin", "creator"):
            assert f'data-testid={{`who-view-option-${{m.id}}`}}' in src or f'who-view-option-{k}' in src

    def test_writes_only_visit_modes(self):
        src = _rf("components/WhoCanViewBadge.jsx")
        # save() envoie SEULEMENT visit_modes, pas view_forcing.
        assert "{ visit_modes: finalModes }" in src

    def test_mounted_in_creator_toolbar(self):
        src = _rf("components/CreatorToolbar.jsx")
        assert "import WhoCanViewBadge from './WhoCanViewBadge';" in src
        assert "<WhoCanViewBadge" in src


class TestWhoCanVisitSimplified:
    def test_no_more_visit_modes_selector(self):
        src = _rf("components/WhoCanVisitBadge.jsx")
        # Les 6 checkboxes DOIVENT AVOIR ÉTÉ RETIRÉES.
        assert "who-visit-option-" not in src
        assert "VISIT_MODES = [" not in src

    def test_no_more_guest_blocks_message(self):
        src = _rf("components/WhoCanVisitBadge.jsx")
        assert "who-visit-guest-blocks-forced" not in src
        assert "guestInSiteMode" not in src

    def test_only_two_radios_kept(self):
        src = _rf("components/WhoCanVisitBadge.jsx")
        assert 'data-testid="who-visit-forcing-free"' in src
        assert 'data-testid="who-visit-forcing-forced"' in src

    def test_writes_only_view_forcing(self):
        src = _rf("components/WhoCanVisitBadge.jsx")
        # setForcing envoie { view_forcing: mode } uniquement.
        assert "{ view_forcing: mode }" in src


class TestSiteModeBadgeCleanup:
    def test_guest_view_options_removed(self):
        src = _rf("components/SiteModeBadge.jsx")
        assert "guest-view-options" not in src
        assert "guest-view-opt-" not in src
        # Le bloc concret UI est retiré (mais un commentaire "iter136 — Bloc ..."
        # peut mentionner l'ancien nom → on cherche le code actif uniquement).
        assert "toggleGuestView" not in src

    def test_still_has_locked_last_option(self):
        # Régression iter135 non touchée.
        src = _rf("components/SiteModeBadge.jsx")
        assert "site-mode-locked-" in src


class TestBackendIndependentFields:
    def test_who_can_visit_fields_optional(self):
        src = _read("server.py")
        assert "visit_modes: Optional[List[str]] = None" in src
        assert "view_forcing: Optional[str] = None" in src

    def test_partial_update_supported(self):
        src = _read("server.py")
        block = src.split("async def set_who_can_visit(")[1].split("\nasync def ")[0]
        assert "if payload.visit_modes is not None:" in block
        assert "if payload.view_forcing is not None:" in block
        # iter137 : 3ème champ optionnel forced_views.
        assert "if payload.forced_views is not None:" in block
        assert "if payload.visit_modes is None and payload.view_forcing is None and payload.forced_views is None:" in block

    def test_guest_forcing_rule_removed(self):
        src = _read("server.py")
        block = src.split("async def set_who_can_visit(")[1].split("\nasync def ")[0]
        # L'ancienne règle "guest in site → forced=free" est SUPPRIMÉE.
        assert '"guest" in active_site_modes' not in block

    def test_site_mode_no_longer_touches_view_forcing(self):
        src = _read("server.py")
        block = src.split("async def set_site_mode(")[1].split("\nasync def ")[0]
        # L'auto-revert view_forcing=free quand guest ajouté est SUPPRIMÉ.
        assert '"view_forcing": "free"' not in block


# Régression cumulée
def test_cumulative_no_regression():
    """Le module Python démarre et les constantes clés existent."""
    from server import VALID_SITE_MODES, _normalize_modes
    for k in ("private", "public", "guest", "modo", "admin", "creator"):
        assert k in VALID_SITE_MODES
    assert _normalize_modes([]) == ["public"]
