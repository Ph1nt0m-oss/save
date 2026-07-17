"""iter130 (retagged iter133) — Tests "Qui peut voir actuellement" (multi-select).

iter133 : suppression des clés 'none' (Personne) et 'all' (Tous) sur demande
utilisateur. Ne restent que 6 clés : private, public, guest, modo, admin, creator.
Rétro-compat : `_normalize_modes` remappe 'none'/'all' legacy vers 'public'.
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


def test_valid_modes_no_none_no_all():
    """iter133 : 'none' et 'all' RETIRÉS de VALID_SITE_MODES."""
    assert "none" not in VALID_SITE_MODES
    assert "all" not in VALID_SITE_MODES
    # Les 6 clés autorisées.
    for k in ("public", "private", "creator", "guest", "modo", "admin"):
        assert k in VALID_SITE_MODES


def test_normalize_legacy_none_all_remapped_to_public():
    """iter133 : les valeurs legacy 'none' et 'all' en DB deviennent 'public'."""
    assert _normalize_modes("none") == ["public"]
    assert _normalize_modes("all") == ["public"]
    assert _normalize_modes(["none", "admin"]) == ["public", "admin"]
    assert _normalize_modes(["all", "private"]) == ["public", "private"]


def test_normalize_regular_multi_unchanged():
    assert _normalize_modes(["public", "admin"]) == ["public", "admin"]
    assert _normalize_modes("private") == ["private"]
    assert _normalize_modes([]) == ["public"]
    assert _normalize_modes(["bogus"]) == ["public"]


def test_normalize_dedupes_preserving_order():
    assert _normalize_modes(["public", "admin", "public"]) == ["public", "admin"]


def test_device_matches_no_all_none_branches():
    """iter133 : plus de matching magique 'all' / 'none' — comportement standard uniquement."""
    # 'all' n'est plus dans VALID donc ignoré par _normalize, mais si passé
    # direct à _device_matches_mode le for-loop ne match plus (safe).
    assert _device_matches_mode(APPROVED, ["all"]) is False
    assert _device_matches_mode(CREATOR, ["none"]) is False


def test_device_matches_regular_still_works():
    assert _device_matches_mode(CREATOR, ["creator"]) is True
    assert _device_matches_mode(APPROVED, ["private"]) is True
    assert _device_matches_mode(ADMIN, ["admin"]) is True
    assert _device_matches_mode(MODO, ["modo"]) is True
    assert _device_matches_mode(VISITOR, ["public"]) is True
    assert _device_matches_mode(VISITOR, ["private"]) is False


def test_frontend_multi_select_seven_options():
    """iter138 : SiteModeBadge affiche 7 clés (+ user)."""
    badge = Path("/app/frontend/src/components/SiteModeBadge.jsx").read_text(encoding="utf-8")
    # SITE_MODE_KEYS partagée depuis lib/siteModeKeys.js
    assert "SITE_MODE_KEYS" in badge
    keys = Path("/app/frontend/src/lib/siteModeKeys.js").read_text(encoding="utf-8")
    for mode_id in ("'private'", "'public'", "'guest'", "'user'", "'modo'", "'admin'", "'creator'"):
        assert f"id: {mode_id}" in keys, f"missing {mode_id}"
    assert "id: 'none'" not in keys
    assert "id: 'all'" not in keys


def test_frontend_toggle_no_exclusivity_logic():
    """iter133 : plus de logique d'exclusivité (all/none retirés)."""
    badge = Path("/app/frontend/src/components/SiteModeBadge.jsx").read_text(encoding="utf-8")
    assert "modeId === 'none' || modeId === 'all'" not in badge
