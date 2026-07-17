"""iter138 — Tests : source unique SITE_MODE_KEYS + 'user' backend + relabels."""
import os
from pathlib import Path

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_codeforge_iter138")

ROOT = Path("/app/backend")
FRONT = Path("/app/frontend/src")


def _read(p):
    return (ROOT / p).read_text(encoding="utf-8")


def _rf(p):
    return (FRONT / p).read_text(encoding="utf-8")


class TestBackendUserKey:
    def test_user_added_to_valid_site_modes(self):
        from server import VALID_SITE_MODES
        assert "user" in VALID_SITE_MODES
        # Les 6 autres toujours présents.
        for k in ("private", "public", "guest", "modo", "admin", "creator"):
            assert k in VALID_SITE_MODES

    def test_device_matches_user_branch(self):
        from server import _device_matches_mode
        # 'user' branche : pending role match.
        assert _device_matches_mode({"role": "pending"}, ["user"]) is True
        # creator match toujours.
        assert _device_matches_mode({"role": "creator"}, ["user"]) is True
        # role None + non-approved = False.
        assert _device_matches_mode({"role": None, "staff_kind": None}, ["user"]) is False

    def test_forced_views_accepts_7_keys(self):
        src = _read("server.py")
        block = src.split("async def set_who_can_visit(")[1].split("\nasync def ")[0]
        for k in ('"user"', '"modo"', '"admin"', '"creator"', '"guest"', '"private"', '"public"'):
            assert k in block, f"forced_views vocab missing {k}"

    def test_get_site_mode_expanded_valid(self):
        src = _read("server.py")
        block = src.split("async def get_site_mode_public():")[1].split("class WhoCanVisitIn")[0]
        # Le set des vues valides inclut les 7.
        assert '"private"' in block
        assert '"public"' in block


class TestSharedFrontendConstant:
    def test_module_exists(self):
        assert (FRONT / "lib/siteModeKeys.js").is_file()

    def test_seven_keys_in_exact_order(self):
        src = _rf("lib/siteModeKeys.js")
        expected_order = ["'private'", "'public'", "'guest'", "'user'", "'modo'", "'admin'", "'creator'"]
        positions = [src.find(f"id: {k}") for k in expected_order]
        assert all(p > 0 for p in positions)
        assert positions == sorted(positions)

    def test_new_guest_hint(self):
        src = _rf("lib/siteModeKeys.js")
        assert "Lecture seule pour les appareils ne disposant pas de compte" in src

    def test_new_user_hint(self):
        src = _rf("lib/siteModeKeys.js")
        assert "Appareils non approuvés mais possédant un compte validé" in src
        assert "label: 'Utilisateurs'" in src


class TestAllFourTabsConsumeShared:
    def test_site_mode_badge_imports_shared(self):
        src = _rf("components/SiteModeBadge.jsx")
        assert "from '../lib/siteModeKeys'" in src
        assert "SITE_MODE_KEYS" in src

    def test_who_can_view_imports_shared(self):
        src = _rf("components/WhoCanViewBadge.jsx")
        assert "from '../lib/siteModeKeys'" in src
        assert "VIEW_KEYS = SITE_MODE_KEYS" in src

    def test_who_can_visit_imports_shared(self):
        src = _rf("components/WhoCanVisitBadge.jsx")
        assert "from '../lib/siteModeKeys'" in src
        assert "VIEW_KEYS = SITE_MODE_KEYS" in src

    def test_view_mode_picker_updated_labels(self):
        src = _rf("components/ViewModePicker.jsx")
        # Nouveaux labels FR alignés sur SITE_MODE_KEYS.
        assert "label: 'Créa'" in src
        assert "label: 'Utilisateurs'" in src
        assert "label: 'Invité'" in src
        assert "label: 'Modo'" in src
        assert "label: 'Admin'" in src
        # Descriptions alignées.
        assert "Appareils non approuvés mais possédant un compte validé" in src
        assert "Lecture seule pour les appareils ne disposant pas de compte" in src
        assert "Seuls les appareils créateurs" in src


class TestOldHintsRetired:
    def test_no_more_english_style_labels_in_visit_badge(self):
        src = _rf("components/WhoCanVisitBadge.jsx")
        # L'ancien label "Vue créatrice/utilisateur/…" a été retiré au profit
        # des labels courts partagés (Privé/Public/Invité/Utilisateurs/Modo/Admin/Créa).
        assert "'Vue créatrice'" not in src
        assert "'Vue utilisateur'" not in src

    def test_view_mode_picker_no_more_labelKey(self):
        src = _rf("components/ViewModePicker.jsx")
        assert "labelKey" not in src

    def test_site_mode_badge_no_more_local_MODES_array(self):
        src = _rf("components/SiteModeBadge.jsx")
        # Le tableau local MODES = [ { id: 'private', ... }, ... ] a été
        # remplacé par une constante partagée SITE_MODE_KEYS.
        assert "const MODES = SITE_MODE_KEYS" in src
