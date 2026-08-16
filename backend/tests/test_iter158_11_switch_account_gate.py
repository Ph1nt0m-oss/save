"""iter158.11 — P0.4 : Gate `switch_account` pour les délégations.

Vérifie que le bouton `sidebar-switch-account-btn` respecte la matrice CDC :
  - Propriétaire réel → visible (jamais restreint).
  - Utilisateur non-délégué (créateur non-délégué, admin, modo, user) → visible.
  - Créa déléguée AVEC `switch_account` dans les perms actives → visible.
  - Créa déléguée SANS `switch_account` → **masqué**.
  - Perm temporaire expirée → n'apparaît plus dans `delegate_perms` (backend filtre).

Le backend `/ownership/status` reste l'autorité finale : le frontend ne
lit que le champ `delegate_perms` (union permanentes + temp non expirées).
"""
from __future__ import annotations

from pathlib import Path

BACK = Path("/app/backend")
FRONT = Path("/app/frontend/src")


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# --- Backend : /ownership/status renvoie perms actives (permanent + temp non expirées) ---

def test_backend_status_returns_active_perms_union():
    src = _read(BACK / "routes/ownership_routes.py")
    idx = src.find('async def ownership_status(payload: _SignedIn)')
    assert idx > 0
    block = src[idx:idx + 1500]
    # Doit utiliser _all_active_perms (perm + temp non expirées) — pas juste
    # `.get("perms")` qui exclurait les délégations temporaires actives.
    assert "_all_active_perms(me_delegate)" in block, (
        "delegate_perms doit être calculé via _all_active_perms pour inclure "
        "les perms temporaires non-expirées."
    )
    # L'ancien accès direct .get('perms') ne doit plus être présent sur cette ligne.
    assert '(me_delegate or {}).get("perms") or []' not in block


def test_backend_all_active_perms_helper_exists():
    src = _read(BACK / "utils/ownership_guard.py")
    assert "def _all_active_perms" in src
    assert "def _active_temp_perms" in src


def test_backend_active_temp_perms_filters_expired():
    """`_active_temp_perms` doit exclure les perms dont expires_at < now."""
    src = _read(BACK / "utils/ownership_guard.py")
    idx = src.find("def _active_temp_perms")
    assert idx > 0
    block = src[idx:idx + 500]
    assert "expires_at" in block
    assert "exp > now" in block or "> now" in block


# --- Frontend : Dashboard.js gate le bouton via delegate_perms ---

def test_dashboard_reads_delegate_perms_from_status():
    src = _read(FRONT / "pages/Dashboard.js")
    # Le useEffect existant fetch /ownership/status et lit is_delegate + delegate_perms
    assert "r.data?.is_delegate" in src
    assert "r.data?.delegate_perms" in src


def test_dashboard_can_switch_account_state_exists():
    src = _read(FRONT / "pages/Dashboard.js")
    assert "canSwitchAccount" in src
    assert "setCanSwitchAccount" in src
    # État initial permissif (true) — la restriction s'applique uniquement
    # aux délégués sans switch_account.
    assert "useState(true)" in src


def test_dashboard_gate_logic_matches_matrix():
    """La logique attendue est :
      canSwitchAccount = isOwner || !isDelegate || perms.includes('switch_account')
    Un propriétaire ou un non-délégué reste toujours autorisé.
    """
    src = _read(FRONT / "pages/Dashboard.js")
    # Le pattern exact doit apparaître pour garantir la matrice CDC.
    assert "isOwner || !isDelegate || delegatePerms.includes('switch_account')" in src


def test_dashboard_button_wrapped_by_gate():
    src = _read(FRONT / "pages/Dashboard.js")
    idx = src.find('data-testid="sidebar-switch-account-btn"')
    assert idx > 0
    # Le block conditionnel `{canSwitchAccount && (` doit précéder le bouton
    # (dans les 300 chars amont).
    context = src[max(0, idx - 300):idx]
    assert "canSwitchAccount && (" in context, (
        "Le bouton doit être gaté par canSwitchAccount"
    )


def test_dashboard_non_creator_defaults_permissive():
    """Un utilisateur non-créateur (role != 'creator') ou en viewMode
    doit voir le bouton (aucune restriction). Vérifie que le useEffect
    remet canSwitchAccount à true dans ces cas."""
    src = _read(FRONT / "pages/Dashboard.js")
    idx = src.find("if (device.role !== 'creator' || device.viewMode)")
    assert idx > 0
    block = src[idx:idx + 500]
    assert "setCanSwitchAccount(true)" in block


def test_dashboard_fail_open_on_error():
    """En cas d'erreur réseau/API, le bouton reste visible (fail-open côté UX).
    La sécurité est de toute façon appliquée serveur-side côté endpoints.
    """
    src = _read(FRONT / "pages/Dashboard.js")
    # Le catch remet canSwitchAccount à true (permissif — le serveur reste
    # l'autorité). Deux occurrences attendues : (1) early return si non-créateur,
    # (2) catch réseau/API sur /ownership/status.
    count = src.count("setIsOwnerDevice(false); setCanSwitchAccount(true);")
    assert count >= 2, f"Expected ≥2 fail-open recoveries, found {count}"


def test_backend_still_authoritative():
    """Le frontend ne modifie AUCUN mécanisme serveur — has_delegate_perm
    reste inchangé et reste la source de vérité pour toute action réelle."""
    src = _read(BACK / "utils/ownership_guard.py")
    assert "async def has_delegate_perm" in src
    # Fonction consomme _all_active_perms
    idx = src.find("async def has_delegate_perm")
    block = src[idx:idx + 500]
    assert "_all_active_perms" in block


def test_switch_account_in_canonical_perms():
    """`switch_account` doit être une perm canonique connue du backend."""
    src = _read(BACK / "utils/ownership_guard.py")
    assert '"switch_account"' in src
    # Présente dans CANONICAL_DELEGATE_PERMS
    idx = src.find("CANONICAL_DELEGATE_PERMS = [")
    assert idx > 0
    block = src[idx:idx + 800]
    assert '"switch_account"' in block
