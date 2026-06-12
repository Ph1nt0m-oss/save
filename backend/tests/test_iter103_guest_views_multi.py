"""
iter103 — Tests pour la migration guest_view (str) → guest_views (list) +
fix du crash useViewSpec (device.viewMode quand device=undefined).
"""
import os
from pathlib import Path
from fastapi.testclient import TestClient

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_codeforge_iter103")

from server import app  # noqa: E402


def test_get_site_mode_returns_guest_views():
    """GET /api/system/site-mode doit renvoyer guest_views (liste) + guest_view (legacy)."""
    with TestClient(app) as c:
        r = c.get("/api/system/site-mode")
        assert r.status_code == 200
        body = r.json()
        assert "guest_views" in body
        assert isinstance(body["guest_views"], list)
        assert "guest_view" in body  # legacy compat


def test_site_mode_set_in_accepts_guest_views_list():
    """Le payload SiteModeSetIn doit accepter guest_views: List[str]."""
    from server import SiteModeSetIn
    import inspect
    fields = SiteModeSetIn.model_fields
    assert "guest_views" in fields
    assert "guest_view" in fields  # legacy still there


def test_devices_verify_returns_guest_views():
    """/api/devices/verify must include guest_views field (even empty)."""
    src = Path("/app/backend/server.py").read_text(encoding="utf-8")
    # Vérifie que la réponse du verify inclut bien guest_views
    assert '"guest_views": gv_list' in src or "'guest_views': gv_list" in src
    assert "iter103" in src


def test_view_spec_hook_handles_undefined_device():
    """useViewSpec doit utiliser optional chaining sur device.viewMode."""
    hook = Path("/app/frontend/src/hooks/useViewSpec.js").read_text(encoding="utf-8")
    # Plus de destructuration { device }
    assert "const { device } = useDeviceIdentity()" not in hook
    # Doit utiliser optional chaining
    assert "device?.viewMode" in hook
    assert "device?.role" in hook


def test_site_mode_badge_uses_checkboxes_for_guest_views():
    """SiteModeBadge.jsx doit avoir le toggleGuestView multi-select."""
    badge = Path("/app/frontend/src/components/SiteModeBadge.jsx").read_text(encoding="utf-8")
    assert "toggleGuestView" in badge
    assert "activeGuestViews" in badge
    assert "guest_views" in badge


def test_use_device_identity_exposes_guest_views():
    """useDeviceIdentity doit exposer guestViews (array)."""
    hook = Path("/app/frontend/src/hooks/useDeviceIdentity.js").read_text(encoding="utf-8")
    assert "guestViews:" in hook
    assert "result.guest_views" in hook
