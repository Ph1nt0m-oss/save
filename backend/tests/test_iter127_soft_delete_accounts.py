"""iter127 — Vérifie le soft-delete d'un compte (/accounts/delete-one).

Le compte reste dans /accounts/list avec `deleted: true` ; la créatrice
verra dans l'UI le badge "Compte supprimé" et toutes les actions seront
désactivées.
"""
from __future__ import annotations

from pathlib import Path


def test_delete_one_is_soft_delete_in_route_source():
    """L'endpoint /accounts/delete-one doit utiliser update_one(deleted)
    et NON delete_one() afin de conserver l'entrée pour la liste."""
    src = Path("/app/backend/routes/accounts_routes.py").read_text(encoding="utf-8")
    # Localise la fonction delete-one
    marker = "@router.post(\"/accounts/delete-one\")"
    assert marker in src
    body = src.split(marker, 1)[1].split("@router.post", 1)[0]
    # Doit NE PAS appeler delete_one sur device_keys
    assert "device_keys.delete_one" not in body, (
        "delete-one ne doit plus hard-delete : il doit faire un soft-delete."
    )
    # Doit poser le flag deleted: True
    assert "\"deleted\": True" in body
    assert "deleted_at" in body


def test_accounts_list_exposes_deleted_flag():
    """/accounts/list doit renvoyer le champ booléen `deleted`."""
    src = Path("/app/backend/routes/accounts_routes.py").read_text(encoding="utf-8")
    marker = "@router.post(\"/accounts/list\")"
    assert marker in src
    body = src.split(marker, 1)[1].split("@router.post", 1)[0]
    assert "d[\"deleted\"] = bool(d.get(\"deleted\"))" in body


def test_accounts_button_renders_deleted_badge_and_disables_actions():
    """Le composant React doit afficher le badge et désactiver les actions."""
    src = Path("/app/frontend/src/components/AccountsButton.jsx").read_text(encoding="utf-8")
    assert "acc_deleted_badge" in src, "Badge i18n manquant"
    assert "actionsDisabled = isDeleted" in src
    # Les boutons "Tout supprimer" et "Vider la vue" doivent être retirés
    assert "acc-delete-all" not in src, "Bouton 'Tout supprimer' doit être retiré"
    assert "acc-clear-view" not in src, "Bouton 'Vider la vue' doit être retiré"
    assert "acc-reset-view" not in src
    # Tri A→Z
    assert "localeCompare" in src
    # Affichage : 4 lignes obligatoires (pseudo, email, type d'appareil, clé partageable)
    assert "acc-pseudo-" in src
    assert "acc-email-" in src
    assert "acc-device-" in src
    assert "acc-key-" in src
    # Type d'appareil (pas type de compte)
    assert "deviceTypeLabel" in src
    assert "Type d'appareil" in src
    # Clé = share_code (PAS key_id)
    assert "{a.share_code" in src


def test_accounts_list_exposes_share_code():
    """/accounts/list doit dériver share_code = base64(jwk) à partir du
    public_key_jwk avant de pop ce dernier."""
    src = Path("/app/backend/routes/accounts_routes.py").read_text(encoding="utf-8")
    marker = "@router.post(\"/accounts/list\")"
    assert marker in src
    body = src.split(marker, 1)[1].split("@router.post", 1)[0]
    assert "share_code" in body
    assert "base64.b64encode" in body
    # public_key_jwk doit être pop (pas retourné en clair)
    assert "d.pop(\"public_key_jwk\"" in body


def test_export_notifier_x_closes_in_forced_open_mode():
    """Le bouton X doit fermer le modal quand forcedOpen=true (ouvert via
    l'icône historique bleue)."""
    src = Path("/app/frontend/src/components/ExportApprovalNotifier.jsx").read_text(encoding="utf-8")
    # Le dismissCurrent doit court-circuiter en mode forcedOpen
    assert "if (forcedOpen)" in src
    assert "setForcedOpen(false)" in src
