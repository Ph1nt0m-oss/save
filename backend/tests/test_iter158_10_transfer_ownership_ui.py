"""iter158.10 — P0.3 : Tests Transfer Ownership UI.

Vérifie que le composant frontend expose CORRECTEMENT le mécanisme backend
existant sans en inventer un nouveau.

Backend contract (analyse strict) :
  - POST /ownership/challenge {key_id, nonce, signature, action:'transfer_ownership',
    target_key_id} → {challenge_id, challenge_nonce, needs_double_signature:true}
  - POST /ownership/transfer {challenge_id, proofs:[{key_id, signature} x2],
    new_owner_key_id} — 2 signatures ECDSA de 2 appareils propriétaires DISTINCTS.
  - Backend refuse doublons, challenge expiré, single-use, signatures invalides.
  - Backend écrit sur owner_key_ids/owner_user_id UNIQUEMENT via cet endpoint.

Tests :
  1. Composant présent avec tous les data-testids attendus.
  2. Composant gaté par is_owner (accès refusé sinon).
  3. Utilise `/ownership/challenge` avec `action:'transfer_ownership'`.
  4. Utilise `/ownership/transfer` avec `challenge_id + proofs + new_owner_key_id`.
  5. Double confirmation : token littéral « TRANSFERT » exigé.
  6. 2 signatures distinctes exigées (frontend refuse même key_id sur les 2).
  7. Aucun état frontend ne peut transférer sans passer par le backend.
  8. Backend inchangé (tests source-level vérifient contract stable).
  9. Dashboard monte le panneau derrière le bouton `header-transfer-ownership-btn`
     gaté isOwnerDevice.
"""
from __future__ import annotations

from pathlib import Path

BACK = Path("/app/backend")
FRONT = Path("/app/frontend/src")


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# --- Backend contract inchangé ---

def test_backend_transfer_endpoint_unchanged():
    src = _read(BACK / "routes/ownership_routes.py")
    assert '@router.post("/ownership/transfer")' in src
    assert "async def transfer_ownership(payload: CriticalIn):" in src
    # Consomme challenge lié + vérifie 2 signatures
    idx = src.find("async def transfer_ownership")
    block = src[idx:idx + 2000]
    assert '_consume_challenge(payload.challenge_id, "transfer_ownership")' in block
    assert "_verify_proofs" in block
    # Écrit owner_key_ids uniquement ici (avec new_owner_user_id)
    assert "owner_key_ids" in block
    assert "owner_user_id" in block


def test_backend_transfer_in_double_sig_actions():
    src = _read(BACK / "utils/ownership_guard.py")
    idx = src.find("DOUBLE_SIG_ACTIONS = {")
    assert idx > 0
    block = src[idx:idx + 300]
    assert '"transfer_ownership"' in block


def test_backend_challenge_endpoint_needs_double_returned():
    src = _read(BACK / "routes/ownership_routes.py")
    idx = src.find('async def ownership_challenge(payload: ChallengeIn)')
    assert idx > 0
    block = src[idx:idx + 1500]
    assert "needs_double = payload.action in DOUBLE_SIG_ACTIONS" in block
    assert '"needs_double_signature": needs_double' in block


# --- Frontend UI ---

def test_component_file_exists():
    p = FRONT / "components/TransferOwnershipPanel.jsx"
    assert p.exists()


def test_component_uses_backend_endpoints():
    src = _read(FRONT / "components/TransferOwnershipPanel.jsx")
    assert "/ownership/status" in src
    assert "/ownership/challenge" in src
    assert "/ownership/transfer" in src
    # Action strictement 'transfer_ownership'
    assert "action: 'transfer_ownership'" in src


def test_component_all_testids_present():
    src = _read(FRONT / "components/TransferOwnershipPanel.jsx")
    for testid in [
        "transfer-ownership-panel",
        "transfer-ownership-close",
        "transfer-ownership-new-key",
        "transfer-ownership-continue-intro",
        "transfer-ownership-cancel-intro",
        "transfer-ownership-confirm-token",
        "transfer-ownership-request-challenge",
        "transfer-ownership-nonce",
        "transfer-ownership-copy-nonce",
        "transfer-ownership-sig2-keyid",
        "transfer-ownership-sig2-value",
        "transfer-ownership-submit",
        "transfer-ownership-cancel-sig2",
        "transfer-ownership-success",
        "transfer-ownership-denied",
    ]:
        assert testid in src, f"data-testid {testid} manquant"


def test_component_gated_by_is_owner():
    src = _read(FRONT / "components/TransferOwnershipPanel.jsx")
    # Vérifie is_owner via /ownership/status
    assert "r.data?.is_owner" in src
    # Rendu 'accès refusé' si !isOwner
    assert "if (!isOwner)" in src
    assert "transfer-ownership-denied" in src


def test_component_double_confirmation_token():
    src = _read(FRONT / "components/TransferOwnershipPanel.jsx")
    # Le token littéral 'TRANSFERT' est exigé
    assert "'TRANSFERT'" in src
    # Le bouton request-challenge est disabled tant que le token n'est pas exact
    assert "confirmToken !== 'TRANSFERT'" in src


def test_component_refuses_same_key_for_two_sigs():
    src = _read(FRONT / "components/TransferOwnershipPanel.jsx")
    assert "secondKeyId.trim() === selfKeyId" in src
    assert "DISTINCTS" in src


def test_component_refuses_self_as_target():
    src = _read(FRONT / "components/TransferOwnershipPanel.jsx")
    assert "newOwnerKeyId.trim() === selfKeyId" in src


def test_component_sends_two_proofs_to_backend():
    """Le POST /ownership/transfer envoie proofs=[proof1, proof2]."""
    src = _read(FRONT / "components/TransferOwnershipPanel.jsx")
    assert "proofs = [proof1" in src
    # Le payload complet contient challenge_id + proofs + new_owner_key_id
    assert "challenge_id: challenge.challenge_id" in src
    assert "new_owner_key_id: newOwnerKeyId.trim()" in src


def test_component_uses_local_signNonce():
    """Le proof #1 est généré par l'appareil courant via signNonce(challenge_nonce)."""
    src = _read(FRONT / "components/TransferOwnershipPanel.jsx")
    assert "signNonce" in src
    assert "signNonce(ch.challenge_nonce)" in src


def test_dashboard_mounts_panel_gated():
    src = _read(FRONT / "pages/Dashboard.js")
    assert "import TransferOwnershipPanel" in src
    assert "<TransferOwnershipPanel" in src
    assert "header-transfer-ownership-btn" in src
    # Gaté par isOwnerDevice (dans le même bloc conditionnel — remonter jusqu'à
    # 2500 chars pour trouver le `{isOwnerDevice && (` en amont).
    idx = src.find("header-transfer-ownership-btn")
    context = src[max(0, idx - 2500):idx]
    assert "isOwnerDevice" in context


def test_no_frontend_state_bypass():
    """Aucun state React ne peut déclencher un transfert sans passer par
    l'endpoint /ownership/transfer. Vérification source-level."""
    src = _read(FRONT / "components/TransferOwnershipPanel.jsx")
    # La seule voie vers setResultInfo passe par axios.post /ownership/transfer
    idx = src.find("setResultInfo(r.data)")
    assert idx > 0
    context = src[max(0, idx - 500):idx]
    assert "/ownership/transfer" in context
