"""iter158.2 — Vérification source-level des règles d'affichage UI par rôle.

Chaque test lit les fichiers frontend et vérifie que les icônes/boutons sont
correctement gatées selon la matrice de permissions :
  - Créa propriétaire : toutes les icônes (dont Sandbox)
  - Créa déléguée   : mêmes icônes SAUF Sandbox (owner-only)
  - Admin           : rename/exclude/ban/delete + promote-admin/modo
  - Modérateur      : uniquement mute/block/exclude/force_visitor/disconnect
                       (PAS promote-admin/modo, PAS ban, PAS delete)
  - Utilisateur validé / classique / invité : aucun bouton staff
  - Sanctionné      : kick_reason correspondant à l'action
  - Banni           : kick_reason='kick_banned'
"""
from __future__ import annotations

from pathlib import Path

FRONT = Path("/app/frontend/src")


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ─────────────────────────────────────────────────────────────────
# 1. Bouton Sandbox visible UNIQUEMENT au propriétaire réel
# ─────────────────────────────────────────────────────────────────

def test_sandbox_button_gated_by_isOwnerDevice():
    """Le bouton `header-sandbox-btn` ne doit apparaître que quand
    `isOwnerDevice === true` (donc pas pour une Créa déléguée).
    """
    src = _read(FRONT / "pages/Dashboard.js")
    # 1) L'état isOwnerDevice existe.
    assert "const [isOwnerDevice, setIsOwnerDevice]" in src, (
        "isOwnerDevice state manquant dans Dashboard.js"
    )
    # 2) Il est initialisé via /ownership/status.
    assert "/ownership/status" in src, (
        "Dashboard.js doit interroger /ownership/status pour déterminer le propriétaire."
    )
    # 3) Le rendu du bouton sandbox est gaté par isOwnerDevice.
    idx = src.find('data-testid="header-sandbox-btn"')
    assert idx > 0, "bouton header-sandbox-btn absent"
    # Prend le contexte 400 chars avant le testid pour trouver la condition.
    context = src[max(0, idx - 400):idx]
    assert "isOwnerDevice" in context, (
        "Le bouton header-sandbox-btn n'est pas gaté par isOwnerDevice."
    )


def test_sandbox_page_denies_non_owner():
    """La page /dev/sandbox montre un écran 'accès refusé' si is_owner=false."""
    src = _read(FRONT / "pages/Sandbox.js")
    assert '"sandbox-denied"' in src or "'sandbox-denied'" in src, \
        "sandbox-denied testid manquant"
    assert "st.data?.is_owner" in src, \
        "La page Sandbox doit vérifier is_owner via /ownership/status"


# ─────────────────────────────────────────────────────────────────
# 2. Boutons promote-admin / promote-modo → admin+créa uniquement
# ─────────────────────────────────────────────────────────────────

def test_promote_admin_modo_buttons_gated_by_canRename():
    """Dans AccountsButton, les boutons `acc-admin-*` et `acc-modo-*` doivent
    être gatés par `canRename` (= isAdminOrCreator). Un modérateur ne doit
    PAS pouvoir voir ces boutons."""
    src = _read(FRONT / "components/AccountsButton.jsx")
    # Trouve la ligne des boutons admin/modo (aliases identifiés par le
    # data-testid `acc-admin-` juste après le `<>` fragment).
    idx = src.find('data-testid={`acc-admin-')
    assert idx > 0, "bouton acc-admin-* manquant"
    # Contexte 400 chars avant.
    context = src[max(0, idx - 400):idx]
    assert "canRename" in context, (
        "Les boutons promote-admin/modo doivent être gatés par canRename "
        "(admin+créa uniquement). Trouvé contexte : " + context[-200:]
    )


def test_useViewSpec_matrix():
    """La matrice `useViewSpec` doit exposer les permissions correctement."""
    src = _read(FRONT / "hooks/useViewSpec.js")
    # canRename/canForceVisitor/canExclude/canBan/canDelete = isAdminOrCreator
    for perm in ("canRenameFromAccountsPanel", "canForceVisitorFromAccountsPanel",
                 "canExcludeFromAccountsPanel", "canBanFromAccountsPanel",
                 "canDeleteFromAccountsPanel"):
        # Chaque perm est mappée sur isAdminOrCreator dans le hook.
        line = next((l for l in src.splitlines() if perm in l), "")
        assert "isAdminOrCreator" in line, (
            f"{perm} doit être = isAdminOrCreator. Ligne : {line!r}"
        )
    # canSeeAccountsButton = isStaffOrCreator (visible pour modo, admin, créa)
    line = next((l for l in src.splitlines() if "canSeeAccountsButton" in l), "")
    assert "isStaffOrCreator" in line, "canSeeAccountsButton doit être isStaffOrCreator"


# ─────────────────────────────────────────────────────────────────
# 3. Barre d'icônes staff — matrice des rangs
# ─────────────────────────────────────────────────────────────────

def test_staff_icon_bar_min_rank():
    """`StaffActionsIconBar` doit imposer les rangs minimaux corrects :
      - mute/block/exclude/force_visitor/disconnect : modo
      - rename/promote_modo/promote_admin/ban : admin
      - visit/promote_creator/delete : creator
    """
    src = _read(FRONT / "components/StaffActionsIconBar.jsx")
    expected = {
        "mute": "modo", "block": "modo", "exclude": "modo",
        "force_visitor": "modo", "disconnect": "modo",
        "rename_global": "admin", "promote_modo": "admin",
        "promote_admin": "admin", "ban": "admin",
        "visit": "creator", "promote_creator": "creator", "delete": "creator",
    }
    for key, min_rank in expected.items():
        # Match ex: { key: 'mute', ..., min: 'modo' }
        needle = f"key: '{key}',"
        idx = src.find(needle)
        assert idx > 0, f"clé {key} manquante dans ICONS"
        # Prends la ligne complète.
        line_end = src.find("\n", idx)
        line = src[idx:line_end]
        assert f"min: '{min_rank}'" in line, (
            f"Icône {key} doit avoir min='{min_rank}'. Ligne : {line}"
        )


# ─────────────────────────────────────────────────────────────────
# 4. Traductions kick_* complètes (FR + EN)
# ─────────────────────────────────────────────────────────────────

def test_kick_reason_translations_complete():
    """Toutes les kick_reasons renvoyées par le backend doivent avoir
    leurs traductions FR et EN."""
    src = _read(FRONT / "contexts/LanguageContext.js")
    backend_reasons = [
        "kick_banned", "kick_excluded", "kick_disconnected",
        "kick_blocked", "kick_revoked", "kick_closed",
        "kick_creator_only", "kick_staff_only", "kick_private",
    ]
    for reason in backend_reasons:
        # Chaque reason doit avoir _title et _body dans les 2 langues.
        # On compte les occurrences (au moins 2 par clé — FR + EN).
        title_count = src.count(f"{reason}_title:")
        body_count = src.count(f"{reason}_body:")
        assert title_count >= 2, (
            f"{reason}_title manquant dans FR ou EN (trouvé {title_count} fois)"
        )
        assert body_count >= 2, (
            f"{reason}_body manquant dans FR ou EN (trouvé {body_count} fois)"
        )


# ─────────────────────────────────────────────────────────────────
# 5. SiteLockedOverlay gère role='banned' en fallback
# ─────────────────────────────────────────────────────────────────

def test_site_locked_overlay_handles_banned_role():
    """L'overlay doit reconnaître role='banned' comme kick_banned si le
    kickReason n'est pas fourni (défense en profondeur)."""
    src = _read(FRONT / "components/SiteLockedOverlay.jsx")
    assert "role === 'banned'" in src, (
        "SiteLockedOverlay doit reconnaître role='banned' en fallback"
    )
    assert "'kick_banned'" in src, (
        "SiteLockedOverlay doit affecter reason='kick_banned'"
    )


# ─────────────────────────────────────────────────────────────────
# 6. Créa propriétaire ≠ Créa déléguée dans le backend
# ─────────────────────────────────────────────────────────────────

def test_backend_ownership_status_exposes_is_owner_and_is_delegate():
    """L'endpoint /ownership/status doit distinguer is_owner et is_delegate
    (source de vérité pour l'UI)."""
    src = _read(Path("/app/backend/routes/ownership_routes.py"))
    assert '"is_owner"' in src
    assert '"is_delegate"' in src


def test_backend_staff_action_blocks_owner_target():
    """Le module staff_actions doit refuser toute action de type
    ban/block/demote/etc. sur un appareil propriétaire."""
    src = _read(Path("/app/backend/routes/staff_actions_routes.py"))
    assert "assert_not_owner_target" in src
    assert "_owner_touching" in src


def test_backend_staff_action_promote_creator_requires_creator_role():
    """promote_creator doit exiger role='creator' (owner OU délégate)."""
    src = _read(Path("/app/backend/routes/staff_actions_routes.py"))
    idx = src.find('elif action == "promote_creator"')
    assert idx > 0
    block = src[idx:idx + 400]
    assert 'me.get("role") != "creator"' in block


# ─────────────────────────────────────────────────────────────────
# 7. Sanctions : /devices/verify renvoie les bons kick_reason
# ─────────────────────────────────────────────────────────────────

def test_backend_devices_verify_evaluates_all_sanctions():
    """/devices/verify doit appeler evaluate_sanctions et retourner
    can_access=False + kick_reason pour chaque type de sanction."""
    src = _read(Path("/app/backend/routes/devices_routes.py"))
    assert 'kick_reason = "kick_banned"' in src
    assert 'kick_reason = "kick_excluded"' in src
    assert 'kick_reason = "kick_disconnected"' in src
    assert 'kick_reason = "kick_blocked"' in src


# ─────────────────────────────────────────────────────────────────
# 8. Environnement production
# ─────────────────────────────────────────────────────────────────

def test_test_mode_disabled_in_env():
    """CODEFORGE_TEST_MODE doit être =0 dans backend/.env pour la production."""
    src = _read(Path("/app/backend/.env"))
    assert "CODEFORGE_TEST_MODE=0" in src, (
        "CODEFORGE_TEST_MODE doit être =0 en production."
    )
