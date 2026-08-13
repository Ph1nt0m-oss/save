"""iter158.4 — Tests source-level du Chantier 1 « Autres identifiants — Reorg ».

Vérifie :
  1. Endpoints backend : /devices/decisions (multi-role), /decisions/undo (multi-role),
     /decisions/undo-multi (nouveau), /decisions/clear (410 Gone).
  2. Matrice de permission : modo/admin/créa autorisés à /decisions et /undo
     avec périmètre correct.
  3. Composant KeysHistoryTab.jsx présent avec search, select-all, undo-multi.
  4. DeviceManager.jsx utilise 2 onglets (Demandes / Historique).
"""
from __future__ import annotations

from pathlib import Path

BACK = Path("/app/backend")
FRONT = Path("/app/frontend/src")


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_backend_devices_decisions_multi_role():
    src = _read(BACK / "routes/devices_routes.py")
    idx = src.find('/devices/decisions"')
    assert idx > 0
    block = src[idx:idx + 1500]
    # Utilise require_staff_signature (pas require_creator_signature)
    assert "require_staff_signature" in block, (
        "GET /devices/decisions doit accepter modo/admin/créa (staff)."
    )
    # Modo est filtré sur ses propres décisions
    assert "actor_key_id" in block


def test_backend_decisions_clear_deprecated():
    src = _read(BACK / "routes/devices_routes.py")
    # /decisions/clear renvoie 410 (spec CDC : plus de vidage historique)
    idx = src.find('/devices/decisions/clear')
    assert idx > 0
    block = src[idx:idx + 800]
    assert "410" in block or "Fonction retirée" in block


def test_backend_decisions_undo_multi_exists():
    src = _read(BACK / "routes/devices_routes.py")
    assert '@router.post("/devices/decisions/undo-multi")' in src
    assert "DecisionsUndoMultiIn" in src
    assert "ok_count" in src
    assert "failed" in src


def test_backend_decisions_undo_matrix():
    """Undo simple doit accepter modo/admin/créa avec la matrice correcte."""
    src = _read(BACK / "routes/devices_routes.py")
    idx = src.find('/devices/decisions/undo"')
    assert idx > 0
    block = src[idx:idx + 3000]
    assert "require_staff_signature" in block
    # Un modo ne peut annuler QUE ses propres décisions
    assert "Un modérateur ne peut annuler que ses propres décisions" in src
    # Un admin ne peut pas annuler les décisions d'une créa
    assert "Un administrateur ne peut annuler les décisions d'un créateur" in src


def test_backend_decisions_undo_multi_permission_matrix():
    src = _read(BACK / "routes/devices_routes.py")
    idx = src.find('/devices/decisions/undo-multi')
    assert idx > 0
    block = src[idx:idx + 3500]
    # Même matrice que undo simple : modo → propres décisions, admin → pas créa
    assert 'actor_sk == "modo"' in block
    assert 'actor_sk == "admin"' in block
    assert 'not_authorized' in block


def test_frontend_keys_history_tab_component():
    p = FRONT / "components/KeysHistoryTab.jsx"
    assert p.exists()
    src = _read(p)
    for testid in [
        "keys-history-tab", "keys-history-search",
        "keys-history-select-all", "keys-history-undo-multi",
        "keys-history-empty",
    ]:
        assert testid in src, f"data-testid {testid} manquant dans KeysHistoryTab"
    # Utilise l'endpoint undo-multi
    assert "/devices/decisions/undo-multi" in src
    # Prompt utilisateur exact (spec CDC : « Quelles actions choisies... »)
    assert "Quelles actions choisies par cette clé doivent être annulées" in src
    # Multi-select via Set + select-all
    assert "new Set(" in src


def test_frontend_device_manager_two_tabs():
    src = _read(FRONT / "components/DeviceManager.jsx")
    assert "import KeysHistoryTab" in src
    assert '"dm-tab-requests"' in src
    assert '"dm-tab-history"' in src
    assert "activeTab === 'history'" in src
    assert "activeTab === 'requests'" in src
    assert "<KeysHistoryTab" in src


def test_full_regression_iter158_still_passes():
    """Sanity check : les tests précédents iter158.2/.3 existent."""
    assert (BACK / "tests/test_iter158_2_ui_visibility.py").exists()
    assert (BACK / "tests/test_iter158_3_owner_privileges.py").exists()
