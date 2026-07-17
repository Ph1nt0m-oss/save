"""iter134 — Tests : onglet "Qui peut visiter" + export badge in header + visit-from-export."""
import os
from pathlib import Path

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_codeforge_iter134")

ROOT = Path("/app/backend")
FRONT = Path("/app/frontend/src")


def _read(p):
    return (ROOT / p).read_text(encoding="utf-8")


def _rf(p):
    return (FRONT / p).read_text(encoding="utf-8")


class TestWhoCanVisitBackend:
    def test_endpoint_declared(self):
        src = _read("server.py")
        assert '@api_router.put("/system/who-can-visit")' in src
        assert "class WhoCanVisitIn(BaseModel):" in src

    def test_endpoint_requires_creator_signature(self):
        src = _read("server.py")
        # Le body ci-dessous doit appeler require_creator_signature.
        block = src.split("async def set_who_can_visit(")[1].split("\nasync def ")[0]
        assert "_require_creator_signature" in block

    def test_endpoint_validates_forcing_and_modes(self):
        src = _read("server.py")
        block = src.split("async def set_who_can_visit(")[1].split("\nasync def ")[0]
        assert 'view_forcing not in ("free", "forced")' in block
        assert "Au moins un mode de visite" in block

    def test_get_endpoint_returns_visit_modes_and_forcing(self):
        src = _read("server.py")
        # Confirme que les nouveaux champs sont dans la réponse GET.
        block = src.split("async def get_site_mode_public():")[1].split("class WhoCanVisitIn")[0]
        assert '"visit_modes"' in block
        assert '"view_forcing"' in block

    def test_devices_verify_returns_new_fields(self):
        src = _read("routes/devices_routes.py")
        assert '"visit_modes": visit_modes' in src
        assert '"view_forcing": view_forcing' in src


class TestWhoCanVisitFrontend:
    def test_component_exists(self):
        assert (FRONT / "components/WhoCanVisitBadge.jsx").is_file()

    def test_six_modes_only(self):
        src = _rf("components/WhoCanVisitBadge.jsx")
        for mid in ("'private'", "'public'", "'guest'", "'modo'", "'admin'", "'creator'"):
            assert f"id: {mid}" in src, f"{mid} missing"
        assert "'none'" not in src
        assert "'all'" not in src

    def test_free_forced_toggles(self):
        src = _rf("components/WhoCanVisitBadge.jsx")
        assert 'data-testid="who-visit-forcing-free"' in src
        assert 'data-testid="who-visit-forcing-forced"' in src

    def test_min_one_selection_required(self):
        src = _rf("components/WhoCanVisitBadge.jsx")
        # Bouton du dernier mode actif désactivé.
        assert "isLastActive = isActive && active.length === 1" in src

    def test_mounted_in_creator_toolbar(self):
        src = _rf("components/CreatorToolbar.jsx")
        assert "import WhoCanVisitBadge from './WhoCanVisitBadge';" in src
        assert "<WhoCanVisitBadge" in src

    def test_useDeviceIdentity_exposes_new_fields(self):
        src = _rf("hooks/useDeviceIdentity.js")
        assert "visitModes:" in src
        assert "viewForcing:" in src

    def test_view_mode_picker_respects_forced(self):
        src = _rf("components/ViewModePicker.jsx")
        assert "visitModes" in src
        assert "viewForcing" in src
        assert "allowedFromWhoCanVisit" in src


class TestExportRequestsInHeader:
    def test_named_export(self):
        src = _rf("components/AccountsButton.jsx")
        assert "export function ExportRequestsHistoryButton" in src

    def test_imported_in_dashboard(self):
        src = _rf("pages/Dashboard.js")
        assert "import AccountsButton, { ExportRequestsHistoryButton }" in src
        # Bouton placé dans le header (avant le bouton bots).
        assert "<ExportRequestsHistoryButton t={t} />" in src

    def test_button_visible_only_when_count_positive(self):
        src = _rf("components/AccountsButton.jsx")
        # if (count <= 0) return null;
        assert "if (count <= 0) return null;" in src


class TestVisitFromExportRequest:
    def test_dashboard_export_notifier_uses_simulation(self):
        src = _rf("pages/Dashboard.js")
        # L'ancien : setVisiting({key_id: o.key_id})
        assert "setVisiting({ key_id: o.key_id })" not in src
        # Le nouveau : setStoredViewMode dans onOpenAccount de ExportApprovalNotifier.
        # On cherche la présence de setStoredViewMode dans le bloc export.
        block = src.split("<ExportApprovalNotifier")[1].split("</ExportApprovalNotifier>")[0] if "</ExportApprovalNotifier>" in src else src.split("<ExportApprovalNotifier")[1].split("/>")[0]
        assert "setStoredViewMode" in block
        assert "visitTargetKeyId" in block

    def test_notifier_passes_role_and_staff_kind(self):
        src = _rf("components/ExportApprovalNotifier.jsx")
        assert "target_role" in src
        assert "target_staff_kind" in src

    def test_backend_exposes_target_role(self):
        src = _read("routes/exports_routes.py")
        assert 'r["target_role"] = dev.get("role")' in src
        assert 'r["target_staff_kind"] = dev.get("staff_kind")' in src


# ============================================================
# Tests de comportement runtime (fonctions Python testables)
# ============================================================

from server import _normalize_modes, VALID_SITE_MODES  # noqa: E402


def test_site_modes_still_six():
    assert "none" not in VALID_SITE_MODES
    assert "all" not in VALID_SITE_MODES


def test_normalize_stable():
    assert _normalize_modes(["public", "creator"]) == ["public", "creator"]
    assert _normalize_modes([]) == ["public"]
