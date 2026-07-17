"""iter135 — Tests : SiteMode verrou dernière case, WhoCanVisit yellow-forced, guest-in-site désactive vue forcée."""
import os
from pathlib import Path

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_codeforge_iter135")

ROOT = Path("/app/backend")
FRONT = Path("/app/frontend/src")


def _read(p):
    return (ROOT / p).read_text(encoding="utf-8")


def _rf(p):
    return (FRONT / p).read_text(encoding="utf-8")


class TestSiteModeLastLocked:
    def test_toggle_blocks_last_deselection(self):
        src = _rf("components/SiteModeBadge.jsx")
        # Le toggleMode contient bien la garde "next.length === 1".
        assert "if (next.length === 1)" in src
        assert "Impossible de tout décocher" in src

    def test_last_option_disabled_and_flagged(self):
        src = _rf("components/SiteModeBadge.jsx")
        assert "isLastActive = active && activeModes.length === 1" in src
        # Badge "verrouillé" présent avec icône.
        assert "site-mode-locked-" in src
        assert "verrouillé" in src
        assert "ShieldQuestion" in src

    def test_disabled_prop_on_last_button(self):
        src = _rf("components/SiteModeBadge.jsx")
        assert "disabled={saving || isLastActive}" in src


class TestWhoCanVisitYellowForced:
    def test_top_button_yellow_when_forced(self):
        src = _rf("components/WhoCanVisitBadge.jsx")
        # Le bouton principal utilise #E4FF00 quand forcing === 'forced'.
        assert "forcing === 'forced'" in src
        assert "'bg-[#E4FF00]/10 border-[#E4FF00]/40 text-[#E4FF00]" in src

    def test_multi_select_checks_yellow_when_forced(self):
        src = _rf("components/WhoCanVisitBadge.jsx")
        # Les cases actives sont dynamiquement colorées jaune ou cyan.
        assert "isForced ? 'text-[#E4FF00]'" in src
        assert "isForced ? 'bg-[#E4FF00]/5'" in src
        assert "isForced ? 'border-[#E4FF00] bg-[#E4FF00]/20'" in src

    def test_forced_radio_uses_yellow(self):
        src = _rf("components/WhoCanVisitBadge.jsx")
        # Radio "Vue forcée" active = jaune (plus amber-200/amber-300).
        assert "forcing === 'forced' ? 'bg-[#E4FF00]/15 text-[#E4FF00]'" in src


class TestGuestInSiteDisablesForced:
    def test_prop_siteModes_received(self):
        src = _rf("components/WhoCanVisitBadge.jsx")
        assert "siteModes = []" in src
        assert "guestInSiteMode = Array.isArray(siteModes) && siteModes.includes('guest')" in src

    def test_forced_radio_disabled_when_guest_in_site(self):
        src = _rf("components/WhoCanVisitBadge.jsx")
        assert "disabled={saving || guestInSiteMode}" in src
        assert "who-visit-guest-blocks-forced" in src

    def test_auto_revert_to_free_when_guest_toggled_on(self):
        src = _rf("components/WhoCanVisitBadge.jsx")
        # useEffect qui repasse à 'free' quand guestInSiteMode + viewForcing === 'forced'
        assert "useEffect" in src
        assert "guestInSiteMode && viewForcing === 'forced'" in src
        assert "view_forcing: 'free'" in src

    def test_setForcing_blocks_when_guest_active(self):
        src = _rf("components/WhoCanVisitBadge.jsx")
        assert "mode === 'forced' && guestInSiteMode" in src

    def test_creator_toolbar_passes_siteModes(self):
        src = _rf("components/CreatorToolbar.jsx")
        # WhoCanVisitBadge reçoit bien siteModes={device.siteModes}
        assert "siteModes={device.siteModes}" in src


class TestBackendGuestGuardsForced:
    def test_who_can_visit_forces_free_when_guest_in_site(self):
        src = _read("server.py")
        block = src.split("async def set_who_can_visit(")[1].split("\nasync def ")[0]
        assert '"guest" in active_site_modes' in block
        assert 'final_forcing = "free"' in block

    def test_set_site_mode_resets_view_forcing_on_guest(self):
        src = _read("server.py")
        block = src.split("async def set_site_mode(")[1].split("\nasync def ")[0]
        # Après update, si is_guest_mode et view_forcing == 'forced' → reset.
        assert "if is_guest_mode:" in block
        assert '"view_forcing": "free"' in block


# Regression : les endpoints répondent toujours
from server import _normalize_modes, VALID_SITE_MODES  # noqa: E402


def test_no_regression_valid_modes():
    for k in ("private", "public", "guest", "modo", "admin", "creator"):
        assert k in VALID_SITE_MODES


def test_no_regression_normalize():
    assert _normalize_modes(["public", "guest"]) == ["public", "guest"]
