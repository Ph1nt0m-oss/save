"""iter158.5 — Tests source-level du Chantier 2 « Autres comptes — Reorg ».

Vérifie :
  1. Backend `/accounts/disconnect` — endpoint enregistré, protège owner,
     log account_history avec kick_reason="kick_disconnected".
  2. Backend `/accounts/history` — élargi staff avec matrice de permission.
  3. Backend `/accounts/history/clear` → 410 Gone.
  4. Backend `/accounts/history/undo` et `/accounts/history/undo-multi` — nouveaux
     endpoints avec UNDO_MATRIX + matrice de permission (créa=tout, admin=admin+modo,
     modo=self).
  5. Frontend AccountsButton — bouton `acc-disconnect-*` gaté par
     `canDisconnectFromAccountsPanel` (staff+).
  6. Frontend AccountsHistoryPanel — data-testids présents + confirm CDC exact.
  7. `useViewSpec.canDisconnectFromAccountsPanel` = `isStaffOrCreator`.
"""
from __future__ import annotations

from pathlib import Path

BACK = Path("/app/backend")
FRONT = Path("/app/frontend/src")


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# --- Backend ---

def test_backend_accounts_disconnect_endpoint_exists():
    src = _read(BACK / "routes/accounts_routes.py")
    assert '@router.post("/accounts/disconnect")' in src
    idx = src.find('/accounts/disconnect')
    block = src[idx:idx + 2500]
    assert "disconnect_until" in block
    assert "assert_not_owner_target" in block, "L'endpoint doit protéger les propriétaires."
    assert '"kick_reason": "kick_disconnected"' in block, (
        "Le log account_history doit contenir kick_reason='kick_disconnected'."
    )


def test_backend_accounts_history_multi_role():
    src = _read(BACK / "routes/accounts_routes.py")
    idx = src.find('@router.post("/accounts/history")')
    assert idx > 0
    block = src[idx:idx + 1200]
    assert "require_staff_signature" in block
    assert 'sk == "modo"' in block  # modo → self only
    assert "actor_key_id" in block


def test_backend_accounts_history_clear_gone():
    src = _read(BACK / "routes/accounts_routes.py")
    idx = src.find('/accounts/history/clear')
    assert idx > 0
    block = src[idx:idx + 800]
    assert "410" in block
    assert "Fonction retirée" in block


def test_backend_accounts_history_undo_endpoints():
    src = _read(BACK / "routes/accounts_routes.py")
    assert '@router.post("/accounts/history/undo")' in src
    assert '@router.post("/accounts/history/undo-multi")' in src
    assert "UNDO_MATRIX" in src
    assert "_can_undo_event" in src
    # Événements réversibles clés
    for ev in ("mute", "unmute", "ban", "unban", "exclude", "disconnect",
               "force_visitor_on", "force_visitor_off",
               "staff_kind_admin", "staff_kind_modo"):
        assert f'"{ev}"' in src, f"UNDO_MATRIX doit contenir '{ev}'"


def test_backend_undo_permission_matrix_symmetric_with_keys():
    """Même matrice que /devices/decisions/undo (spec finalisation)."""
    src = _read(BACK / "routes/accounts_routes.py")
    assert 'sk == "modo"' in src
    assert 'sk == "admin"' in src
    # créa always allowed
    assert 'actor_role == "creator"' in src


# --- Frontend ---

def test_useViewSpec_can_disconnect():
    src = _read(FRONT / "hooks/useViewSpec.js")
    assert "canDisconnectFromAccountsPanel" in src
    line = next((l for l in src.splitlines()
                 if "canDisconnectFromAccountsPanel" in l), "")
    assert "isStaffOrCreator" in line


def test_accounts_button_disconnect_wired():
    src = _read(FRONT / "components/AccountsButton.jsx")
    assert "canDisconnect" in src
    assert "acc-disconnect-" in src
    assert "'/accounts/disconnect'" in src
    # Icon LogOut importé
    assert "LogOut" in src


def test_accounts_history_panel_component():
    p = FRONT / "components/AccountsHistoryPanel.jsx"
    assert p.exists()
    src = _read(p)
    for testid in [
        "accounts-history-panel", "accounts-history-close",
        "accounts-history-search", "accounts-history-select-all",
        "accounts-history-undo-multi", "accounts-history-empty",
    ]:
        assert testid in src, f"data-testid {testid} manquant"
    assert "/accounts/history" in src
    assert "/accounts/history/undo-multi" in src
    assert "Quelles actions choisies par cette clé doivent être annulées" in src


def test_accounts_button_opens_history_panel():
    src = _read(FRONT / "components/AccountsButton.jsx")
    assert "import AccountsHistoryPanel" in src
    assert "<AccountsHistoryPanel" in src
    assert "accounts-open-history-btn" in src
    assert "historyOpen" in src
