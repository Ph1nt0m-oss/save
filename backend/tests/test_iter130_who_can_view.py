"""iter130 — Tests "Qui peut voir actuellement" (multi-select site modes).

Nouvelles audiences : 'none' (Personne — site fermé, créa seule) et
'all' (Tous — tout le monde). Exclusivité none/all dans _normalize_modes.
"""
import os
from pathlib import Path

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_codeforge_iter130")

from server import _normalize_modes, _device_matches_mode, VALID_SITE_MODES  # noqa: E402

CREATOR = {"role": "creator", "staff_kind": None}
ADMIN = {"role": "approved", "staff_kind": "admin"}
MODO = {"role": "approved", "staff_kind": "modo"}
APPROVED = {"role": "approved", "staff_kind": None}
VISITOR = {"role": "pending", "staff_kind": None}
BANNED = {"role": "approved", "banned": True}


def test_valid_modes_include_none_and_all():
    assert "none" in VALID_SITE_MODES and "all" in VALID_SITE_MODES


def test_normalize_none_is_exclusive():
    assert _normalize_modes(["none", "public", "admin"]) == ["none"]
    assert _normalize_modes(["public", "none"]) == ["none"]


def test_normalize_all_is_exclusive():
    assert _normalize_modes(["all", "private"]) == ["all"]
    # none prioritaire sur all
    assert _normalize_modes(["all", "none"]) == ["none"]


def test_normalize_regular_multi_unchanged():
    assert _normalize_modes(["public", "admin"]) == ["public", "admin"]
    assert _normalize_modes("private") == ["private"]
    assert _normalize_modes([]) == ["public"]
    assert _normalize_modes(["bogus"]) == ["public"]


def test_mode_none_only_creator_matches():
    assert _device_matches_mode(CREATOR, ["none"]) is True
    assert _device_matches_mode(ADMIN, ["none"]) is False
    assert _device_matches_mode(MODO, ["none"]) is False
    assert _device_matches_mode(APPROVED, ["none"]) is False
    assert _device_matches_mode(VISITOR, ["none"]) is False


def test_mode_all_everyone_matches_except_banned():
    for dev in (CREATOR, ADMIN, MODO, APPROVED, VISITOR):
        assert _device_matches_mode(dev, ["all"]) is True
    assert _device_matches_mode(BANNED, ["all"]) is False
    assert _device_matches_mode({"role": "revoked"}, ["all"]) is False


def test_kick_reason_closed_wired():
    src = Path("/app/backend/routes/devices_routes.py").read_text(encoding="utf-8")
    assert '"none" in modes_active' in src
    assert "kick_closed" in src


def test_frontend_multi_select_eight_options():
    badge = Path("/app/frontend/src/components/SiteModeBadge.jsx").read_text(encoding="utf-8")
    for mode_id in ("'none'", "'private'", "'public'", "'guest'", "'modo'", "'admin'", "'creator'", "'all'"):
        assert f"id: {mode_id}" in badge
    assert "'staff'" not in badge  # retiré de l'UI (admin+modo le couvrent)
    assert "Qui peut voir actuellement" in badge
    assert "Personne" in badge and "Tous" in badge


def test_frontend_exclusivity_and_overlay():
    badge = Path("/app/frontend/src/components/SiteModeBadge.jsx").read_text(encoding="utf-8")
    assert "modeId === 'none' || modeId === 'all'" in badge
    overlay = Path("/app/frontend/src/components/SiteLockedOverlay.jsx").read_text(encoding="utf-8")
    assert "kick_closed" in overlay
    lang = Path("/app/frontend/src/contexts/LanguageContext.js").read_text(encoding="utf-8")
    assert "kick_closed_title" in lang and "Site fermé" in lang


def test_can_write_handles_all_and_none():
    hook = Path("/app/frontend/src/hooks/useDeviceIdentity.js").read_text(encoding="utf-8")
    assert "state.siteMode === 'all'" in hook
