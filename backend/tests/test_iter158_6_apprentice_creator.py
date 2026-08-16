"""iter158.6 — Tests source-level du Chantier 3 « Apprentice Creator ».

Vérifie :
  1. `utils/ownership_guard` : CANONICAL_DELEGATE_PERMS + helpers d'expiration
     (`_active_temp_perms`, `_all_active_perms`, `has_delegate_perm` mis à jour).
  2. Endpoints backend :
       /ownership/delegate/list
       /ownership/delegate/grant-temp
       /ownership/delegate/grant-permanent
       /ownership/delegate/revoke-perm
       /ownership/delegate/lock
       /ownership/delegate/unlock
       /ownership/delegate/history
  3. Revoke refuse si délégué verrouillé.
  4. Lock exige toutes les canonical perms permanentes (sauf full_control).
  5. Frontend : composant OwnerDelegatesPanel présent + monté dans Dashboard.
  6. Traçabilité : `_log_delegate_history` sur chaque action.
"""
from __future__ import annotations

from pathlib import Path

BACK = Path("/app/backend")
FRONT = Path("/app/frontend/src")


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# --- Backend guard ---

def test_guard_exposes_canonical_perms():
    src = _read(BACK / "utils/ownership_guard.py")
    assert "CANONICAL_DELEGATE_PERMS" in src
    # Perms clés attendues par la spec CDC
    for p in ("approve_key", "promote_staff", "manage_bots", "manage_ideas",
              "manage_exports", "manage_ai", "site_config", "switch_account",
              "visit_account", "rename_global"):
        assert f'"{p}"' in src, f"Perm {p} manquante dans CANONICAL_DELEGATE_PERMS"


def test_guard_temp_perm_helpers():
    src = _read(BACK / "utils/ownership_guard.py")
    assert "def _active_temp_perms" in src
    assert "def _all_active_perms" in src
    # has_delegate_perm doit consulter les temp perms
    idx = src.find("async def has_delegate_perm")
    assert idx > 0
    block = src[idx:idx + 800]
    assert "_all_active_perms" in block or "temp_perms" in block


def test_delegate_permissions_extended():
    src = _read(BACK / "utils/ownership_guard.py")
    # DELEGATE_PERMISSIONS doit inclure les nouvelles perms canoniques
    idx = src.find("DELEGATE_PERMISSIONS = {")
    assert idx > 0
    block = src[idx:idx + 1200]
    for p in ("approve_key", "promote_staff", "manage_ai", "site_config",
              "switch_account", "visit_account", "rename_global", "full_control"):
        assert f'"{p}"' in block, f"Perm {p} absente de DELEGATE_PERMISSIONS"


# --- Backend routes ---

def test_new_endpoints_exist():
    src = _read(BACK / "routes/ownership_routes.py")
    for ep in [
        "/ownership/delegate/list",
        "/ownership/delegate/grant-temp",
        "/ownership/delegate/grant-permanent",
        "/ownership/delegate/revoke-perm",
        "/ownership/delegate/lock",
        "/ownership/delegate/unlock",
        "/ownership/delegate/history",
    ]:
        assert f'@router.post("{ep}")' in src, f"Endpoint {ep} manquant"


def test_revoke_refuses_locked_delegate():
    src = _read(BACK / "routes/ownership_routes.py")
    idx = src.find('@router.post("/ownership/delegate/revoke")')
    assert idx > 0
    block = src[idx:idx + 1500]
    assert "locked" in block
    assert "409" in block
    assert "véritable créateur" in block


def test_grant_temp_has_duration_bounds():
    src = _read(BACK / "routes/ownership_routes.py")
    idx = src.find('/ownership/delegate/grant-temp')
    assert idx > 0
    block = src[idx:idx + 2000]
    # Bornage 1 min → 30 jours
    assert "60 * 24 * 30" in block
    assert "expires_at" in block


def test_grant_permanent_promotes_temp():
    src = _read(BACK / "routes/ownership_routes.py")
    idx = src.find('/ownership/delegate/grant-permanent')
    assert idx > 0
    block = src[idx:idx + 2000]
    # Retire de temp_perms + ajoute à perms
    assert "delegates.$.temp_perms" in block
    assert "delegates.$.perms" in block
    assert "addToSet" in block


def test_lock_requires_all_canonical_perms():
    src = _read(BACK / "routes/ownership_routes.py")
    idx = src.find('/ownership/delegate/lock')
    assert idx > 0
    block = src[idx:idx + 2500]
    assert "CANONICAL_DELEGATE_PERMS" in block
    assert "full_control" in block
    assert "manquantes pour verrouiller" in block


def test_history_persisted_in_delegate_row():
    src = _read(BACK / "routes/ownership_routes.py")
    assert "_log_delegate_history" in src
    assert "delegates.$.history" in src
    # Les actions clés sont loggées
    for action in ("grant_temp", "grant_permanent", "revoke_perm", "lock", "unlock"):
        assert f'"action": "{action}"' in src, f"Action {action} non loggée"


def test_delegate_list_purges_expired_temp():
    src = _read(BACK / "routes/ownership_routes.py")
    idx = src.find('/ownership/delegate/list')
    assert idx > 0
    block = src[idx:idx + 2000]
    assert "temp_perms" in block
    assert "canonical_perms_missing" in block


# --- Frontend ---

def test_frontend_owner_delegates_panel():
    p = FRONT / "components/OwnerDelegatesPanel.jsx"
    assert p.exists()
    src = _read(p)
    for testid in [
        "owner-delegates-panel", "owner-delegates-close",
        "delegate-add-keyid", "delegate-add-perm", "delegate-add-minutes",
        "delegate-add-submit",
        "delegate-history-modal", "owner-delegates-empty",
    ]:
        assert testid in src, f"data-testid {testid} manquant"
    # Appels aux nouveaux endpoints
    for ep in ["/ownership/delegate/list", "/ownership/delegate/grant-temp",
               "/ownership/delegate/grant-permanent", "/ownership/delegate/revoke-perm",
               "/ownership/delegate/history"]:
        assert ep in src, f"Endpoint {ep} non appelé"


def test_dashboard_mounts_delegates_panel():
    src = _read(FRONT / "pages/Dashboard.js")
    assert "import OwnerDelegatesPanel" in src
    assert "<OwnerDelegatesPanel" in src
    assert "header-delegates-btn" in src
    # Gaté par isOwnerDevice (dans le même block conditionnel que sandbox-btn)
    idx = src.find("header-delegates-btn")
    context = src[max(0, idx - 800):idx]
    assert "isOwnerDevice" in context


# --- Traçabilité ---

def test_ownership_events_logged():
    """Chaque action de délégation doit générer un ownership_event."""
    src = _read(BACK / "routes/ownership_routes.py")
    for ev in ("delegate_grant_temp", "delegate_grant_permanent",
               "delegate_revoke_perm", "delegate_lock", "delegate_unlock"):
        assert f'"{ev}"' in src, f"Event {ev} non journalisé"
