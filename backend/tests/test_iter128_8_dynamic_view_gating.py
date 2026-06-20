"""iter128.8 — Règles dynamiques site_modes × rôle device.

Vérifie au niveau source que :
  - Le endpoint /devices/verify expose `can_simulate_views` et
    `view_simulation_constraint`.
  - Les 3 règles spec sont présentes :
    * public + guest → bloque non-approuvés
    * public + private + staff → bloque tout sauf créa
    * creator only + guest non coché → bloque les autres en invité
  - Frontend `useDeviceIdentity` expose `canSimulateViews` +
    `viewSimulationConstraint` au state.
  - `ViewModePicker` accepte ces props et cache le picker si bloqué.
"""
from pathlib import Path


BACK = Path("/app/backend")
FRONT = Path("/app/frontend/src")


def test_backend_exposes_can_simulate_views():
    src = (BACK / "routes/devices_routes.py").read_text(encoding="utf-8")
    assert "can_simulate_views" in src
    assert "view_simulation_constraint" in src
    # Les 3 règles
    assert "public_guest_blocks_non_approved" in src
    assert "triple_mode_blocks_all" in src
    assert "creator_only_guest_not_enabled" in src
    # La créa physique n'est jamais bridée
    assert "if not is_creator_dev" in src


def test_frontend_hook_exposes_simulation_flags():
    src = (FRONT / "hooks/useDeviceIdentity.js").read_text(encoding="utf-8")
    assert "canSimulateViews" in src
    assert "viewSimulationConstraint" in src


def test_view_mode_picker_respects_blocking():
    src = (FRONT / "components/ViewModePicker.jsx").read_text(encoding="utf-8")
    assert "canSimulateViews" in src
    assert "blockedBySiteRules" in src


def test_creator_toolbar_passes_simulation_flags():
    src = (FRONT / "components/CreatorToolbar.jsx").read_text(encoding="utf-8")
    assert "canSimulateViews={device.canSimulateViews}" in src
