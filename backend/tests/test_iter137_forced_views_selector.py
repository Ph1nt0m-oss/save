"""iter137 — Tests : forced_views (5 vues restreintes en mode forcé)."""
import os
from pathlib import Path

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_codeforge_iter137")

ROOT = Path("/app/backend")
FRONT = Path("/app/frontend/src")


def _read(p):
    return (ROOT / p).read_text(encoding="utf-8")


def _rf(p):
    return (FRONT / p).read_text(encoding="utf-8")


class TestBackendForcedViews:
    def test_field_declared_optional(self):
        src = _read("server.py")
        assert "forced_views: Optional[List[str]] = None" in src

    def test_endpoint_accepts_forced_views_LEGACY_removed(self):
        # iter137's dedicated test remains but now via the class above.
        pass

    def test_get_site_mode_returns_forced_views(self):
        src = _read("server.py")
        block = src.split("async def get_site_mode_public():")[1].split("class WhoCanVisitIn")[0]
        assert '"forced_views"' in block
        assert "forced_views = [v for v in fv_raw if v in valid_v]" in block

    def test_devices_verify_returns_forced_views(self):
        src = _read("routes/devices_routes.py")
        assert '"forced_views": forced_views' in src

    def test_endpoint_400_when_no_field(self):
        src = _read("server.py")
        block = src.split("async def set_who_can_visit(")[1].split("\nasync def ")[0]
        assert "if payload.visit_modes is None and payload.view_forcing is None and payload.forced_views is None:" in block


class TestFrontendWhoCanVisitViewSelector:
    def test_view_keys_present(self):
        # iter138 — WhoCanVisitBadge utilise désormais SITE_MODE_KEYS (7 clés)
        # partagées avec les autres onglets.
        src = _rf("components/WhoCanVisitBadge.jsx")
        assert "VIEW_KEYS = SITE_MODE_KEYS" in src
        keys = _rf("lib/siteModeKeys.js")
        # Les 5 vues réelles + les 2 clés d'audience partagées.
        for v in ("'creator'", "'user'", "'modo'", "'admin'", "'guest'", "'private'", "'public'"):
            assert f"id: {v}" in keys, f"missing key {v}"

    def test_endpoint_accepts_forced_views(self):
        # iter138 — 7 clés acceptées, valid_views élargi.
        src = _read("server.py")
        block = src.split("async def set_who_can_visit(")[1].split("\nasync def ")[0]
        for v in ('"user"', '"modo"', '"admin"', '"creator"', '"guest"', '"private"', '"public"'):
            assert v in block, f"forced_views vocab missing {v}"
        assert 'update["forced_views"] = out_v' in block

    def test_free_shows_message_not_selector(self):
        src = _rf("components/WhoCanVisitBadge.jsx")
        assert 'data-testid="mode-de-vue-free-message"' in src
        assert "Libre choix actif" in src

    def test_forced_shows_5view_selector(self):
        src = _rf("components/WhoCanVisitBadge.jsx")
        assert 'data-testid={`forced-view-option-${v.id}`}' in src
        assert "Vues autorisées en mode forcé" in src

    def test_default_forced_view_when_activating(self):
        src = _rf("components/WhoCanVisitBadge.jsx")
        assert "forced_views: ['user']" in src

    def test_min_one_locked(self):
        src = _rf("components/WhoCanVisitBadge.jsx")
        assert "En mode forcé, au moins une vue doit rester cochée" in src
        assert "forced-view-locked-" in src

    def test_writes_forced_views(self):
        src = _rf("components/WhoCanVisitBadge.jsx")
        assert "forced_views: next" in src

    def test_useDeviceIdentity_exposes_forcedViews(self):
        src = _rf("hooks/useDeviceIdentity.js")
        assert "forcedViews:" in src

    def test_creator_toolbar_passes_forcedViews(self):
        src = _rf("components/CreatorToolbar.jsx")
        assert "forcedViews={device.forcedViews}" in src


class TestViewModePickerUsesForcedViewsDirectly:
    def test_receives_forcedViews_prop(self):
        src = _rf("components/ViewModePicker.jsx")
        assert "forcedViews = null" in src

    def test_uses_forcedViews_no_mapping(self):
        src = _rf("components/ViewModePicker.jsx")
        assert "allowedForcedViews = isForcedMode && Array.isArray(forcedViews)" in src
        # L'ancien mapping fragile est retiré.
        assert "allowedFromWhoCanVisit" not in src


# Régression : les autres onglets et le split iter136 sont toujours en place.
def test_who_can_view_still_present():
    src = Path("/app/frontend/src/components/WhoCanViewBadge.jsx").read_text(encoding="utf-8")
    assert 'data-testid="who-can-view-toggle"' in src
