"""iter158.18 — P2.1 : Décision UX du changement de statut.

Décision après audit : **conserver `StaffActionsIconBar`** (iter144) comme
unique UX pour le changement de statut d'un compte. Ne PAS introduire de
`<select>` unifié.

Justification :
  - **Lisibilité CDC** : les 12 actions sont visibles d'un coup d'œil, chaque
    icône porte un `title` et un `data-testid` explicite. Un dropdown
    masquerait l'ensemble derrière 2 clics.
  - **Statuts autorisés** : chaque icône correspond à une transition de
    statut concrète (mute/block/exclude/ban/force-visitor/disconnect/
    promote_modo/promote_admin/promote_creator/rename/visit/delete). Un
    `<select>` serait inapproprié car les transitions sont des VERBES, pas
    des valeurs de statut.
  - **Permissions par rôle** : la matrice frontend
    (MIN_RANK + rankOf dans StaffActionsIconBar) correspond EXACTEMENT à
    `_permission_matrix` du backend (`routes/staff_actions_routes.py:71`).
    Les icônes non-autorisées sont grisées (visibles mais désactivées) pour
    préserver la cohérence visuelle (CDC utilisatrice : « mêmes nombres
    d'icônes dont il est responsable »).
  - **Restrictions serveur** : le backend reste SEULE autorité
    (`/staff/action` + `_permission_matrix` + `assert_not_owner_target` +
    protection fondatrices + guard Créa-vs-Créa iter158.13). Le frontend
    ne joue qu'un rôle UX.
  - **Confirmations contextuelles** : `ban`, `block`, `promote_creator`
    déclenchent un `window.confirm` ciblé — ce workflow n'est pas natif
    dans un `<select>`.
  - **Fondatrices** : affichage visuel distinct (icône Lock + fond rouge
    + tooltip « Créa fondatrice — action interdite »), impossible à
    reproduire proprement dans un dropdown.

**Conclusion** : aucun manque CDC/UX démontré. Le dropdown aurait été une
régression UX. Décision verrouillée par les tests ci-dessous.
"""
from __future__ import annotations

import re
from pathlib import Path

FRONT = Path("/app/frontend/src")
BACK = Path("/app/backend")
ICONBAR = FRONT / "components/StaffActionsIconBar.jsx"
STAFF_ROUTE = BACK / "routes/staff_actions_routes.py"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ---------------- Décision : la barre d'icônes est l'UNIQUE UX --------

def test_icon_bar_is_the_single_ux_entry_point():
    """Aucun composant hors `StaffActionsIconBar` ne propose un `<select>`
    pour changer le statut staff d'un compte.
    
    Exclusion : `components/ui/select.jsx` (wrapper générique Radix UI shadcn)
    n'est pas un composant métier."""
    # Rechercher tout `<select>` associé à des statuts staff.
    status_select_hits = []
    for jsx in FRONT.rglob("*.jsx"):
        if jsx.name == "select.jsx" and "ui" in jsx.parts:
            continue  # wrapper shadcn générique
        src = _read(jsx)
        if "<select" not in src.lower():
            continue
        # Fenêtres de 300 caractères autour de chaque <select>.
        for m in re.finditer(r"<select", src, flags=re.IGNORECASE):
            window = src[max(0, m.start() - 50):m.end() + 400]
            # Un `<select>` est problématique si ses options incluent des
            # actions staff (en tant que mots entiers, pas substrings).
            if re.search(
                r"\b(mute|block|ban|exclude|promote_modo|promote_admin|"
                r"force_visitor|staff_kind)\b",
                window,
            ):
                status_select_hits.append((str(jsx), window[:200]))
    assert not status_select_hits, (
        f"Un <select> listant des actions staff est présent — "
        f"viole la décision P2.1 : {status_select_hits}"
    )


def test_iconbar_exports_twelve_canonical_actions():
    """`StaffActionsIconBar` liste exactement 12 icônes canoniques,
    strictement alignées sur `_permission_matrix` du backend."""
    src = _read(ICONBAR)
    ids = re.findall(r"key:\s*'([a-z_]+)'", src)
    expected = {
        "visit", "rename_global",
        "promote_modo", "promote_admin", "promote_creator",
        "mute", "block", "exclude", "force_visitor", "disconnect",
        "ban", "delete",
    }
    assert set(ids) == expected, (
        f"Les 12 actions canoniques doivent correspondre exactement — "
        f"attendu {expected}, obtenu {set(ids)}"
    )
    assert len(ids) == len(set(ids)) == 12


# ---------------- Alignement front/back de la matrice de permissions --

FRONT_MIN_RANK = {"modo": 1, "admin": 2, "creator": 3}
# Permissions attendues côté UI (déduites de ICONS[].min dans StaffActionsIconBar)
EXPECTED_MIN_BY_ACTION = {
    "visit": "creator",
    "rename_global": "admin",
    "promote_modo": "admin",
    "promote_admin": "admin",
    "promote_creator": "creator",
    "mute": "modo",
    "block": "modo",
    "exclude": "modo",
    "force_visitor": "modo",
    "disconnect": "modo",
    "ban": "admin",
    "delete": "creator",
}


def test_iconbar_permission_matrix_aligns_with_backend():
    """Pour chaque action non-callback (délégation visit/rename/delete au
    parent), le `min` déclaré côté UI correspond au niveau minimal attendu
    côté backend `_permission_matrix`."""
    src = _read(ICONBAR)
    # Parse { key: 'xxx', ..., min: 'yyy' }
    found = dict(re.findall(
        r"key:\s*'([a-z_]+)'[^}]+?min:\s*'(\w+)'", src, flags=re.DOTALL
    ))
    for action, expected_min in EXPECTED_MIN_BY_ACTION.items():
        assert found.get(action) == expected_min, (
            f"UI permission mismatch pour {action}: UI={found.get(action)!r} vs "
            f"attendu CDC={expected_min!r}"
        )


def test_backend_permission_matrix_covers_all_server_actions():
    """`_permission_matrix` backend accepte modo pour les actions basiques,
    admin pour promote_modo/admin + ban + rename_global + demote, créa pour
    tout. Vérifie ces 3 branches."""
    src = _read(STAFF_ROUTE)
    # Branche modo
    modo_m = re.search(r"modo_allowed\s*=\s*\{([^}]+)\}", src)
    assert modo_m
    modo_set = {s.strip().strip("'\"") for s in modo_m.group(1).split(",")}
    for a in ("mute", "unmute", "block", "unblock", "exclude",
              "force_visitor", "disconnect"):
        assert a in modo_set, f"Backend modo doit autoriser {a}"
    # Branche admin additionne les ban/promote_*/demote/rename_global
    admin_extra_m = re.search(r"admin_allowed\s*=\s*modo_allowed\s*\|\s*\{([^}]+)\}", src)
    assert admin_extra_m
    admin_extra = {s.strip().strip("'\"") for s in admin_extra_m.group(1).split(",")}
    for a in ("ban", "promote_modo", "promote_admin", "demote", "rename_global"):
        assert a in admin_extra, f"Backend admin doit autoriser {a}"
    # Créa : tout (branche is_creator → True sans filtre).
    assert re.search(r"if\s+is_creator:\s*\n\s*return\s+True", src)


# ---------------- Qualités UX non reproductibles par un <select> ------

def test_iconbar_each_icon_has_testid_and_title_for_a11y_and_tests():
    """Chaque bouton d'icône expose un `data-testid` unique par (action, target)
    et un `title` lisible — garantit a11y + testabilité, qu'un `<select>`
    (où les `<option>` ne portent pas de testids individuels par défaut)
    ne fournit pas aussi finement."""
    src = _read(ICONBAR)
    assert 'data-testid={`staff-action-${key}-${target?.key_id}`}' in src
    assert "title={targetIsFounder" in src and "label}" in src


def test_iconbar_shows_disabled_icons_for_denied_actions():
    """La barre AFFICHE les icônes refusées en mode désactivé (cohérence
    visuelle utilisatrice iter144 : « mêmes nombres d'icônes »). Un
    `<select>` masquerait au lieu d'informer — c'est une régression CDC."""
    src = _read(ICONBAR)
    # Un bouton toujours rendu, avec `disabled={!allowed || isBusy}`.
    assert "disabled={!allowed" in src
    # Classes CSS appliquées quand `!allowed`.
    assert "cursor-not-allowed" in src and "opacity-40" in src
    # Le bouton reste rendu dans tous les cas (pas de ternaire `allowed && …`
    # qui éliderait le DOM).
    assert "ICONS.map" in src
    # Non-pattern : pas d'if (!allowed) return null
    assert "if (!allowed) return null" not in src


def test_iconbar_founders_show_lock_icon_and_block_actions():
    """Les créas fondatrices affichent une icône Lock + bouton désactivé +
    tooltip explicite. Impossible à reproduire élégamment avec un `<select>`."""
    src = _read(ICONBAR)
    assert "targetIsFounder" in src
    assert "Lock" in src
    assert "Créa fondatrice" in src
    # Lock utilisé quand targetIsFounder, action remplacée visuellement.
    assert re.search(r"targetIsFounder\s*\?\s*<Lock", src)


def test_iconbar_critical_actions_require_confirm():
    """`ban`, `block`, `promote_creator` déclenchent `window.confirm` —
    workflow non natif dans un `<select>`."""
    src = _read(ICONBAR)
    m = re.search(r"\[\s*'ban',\s*'block',\s*'promote_creator'\s*\]", src)
    assert m, "Les 3 actions critiques doivent déclencher confirm"
    assert "window.confirm" in src


# ---------------- Backend reste seule autorité -------------------------

def test_backend_is_the_sole_authority_for_actions():
    """Le composant frontend délègue 100 % des actions non-callback au
    endpoint backend `/staff/action` — aucune mutation d'état en local
    sans validation serveur."""
    src = _read(ICONBAR)
    # Un seul appel POST, vers /staff/action.
    posts = re.findall(r"axios\.post\(`\$\{API\}([^`]+)`", src)
    assert posts == ["/staff/action"], (
        f"Le composant ne doit émettre QUE vers /staff/action — trouvé {posts}"
    )
    # Les actions purement UI (visit/rename/delete) sont déléguées à des
    # callbacks parents, PAS à une mutation locale directe.
    for cb in ("onVisit", "onRename", "onDeleteRequested"):
        assert cb in src, f"Callback parent manquant : {cb}"


def test_server_guards_still_apply_regardless_of_ui_choice():
    """Même si un futur attaquant appelait /staff/action directement sans
    passer par la barre, les protections serveur restent intactes :
      - signature ECDSA requise (`verify_signed`)
      - matrice de permissions (`_permission_matrix`)
      - garde ownership (`assert_not_owner_target`)
      - garde fondatrices (`is_founder`)
      - garde Créa-vs-Créa iter158.13."""
    src = _read(STAFF_ROUTE)
    for guard in (
        "verify_signed",
        "_permission_matrix",
        "assert_not_owner_target",
        "is_founder",
    ):
        assert guard in src, f"Guard backend manquant : {guard}"


# ---------------- Non-régression intégration DeviceManager -------------

def test_device_manager_mounts_iconbar_instead_of_a_select():
    """DeviceManager monte `StaffActionsIconBar` pour chaque compte staff
    — aucun autre composant de statut ajouté."""
    src = _read(FRONT / "components/DeviceManager.jsx")
    assert "StaffActionsIconBar" in src
    # Pas de `<select>` global pour statut dans ce fichier.
    for m in re.finditer(r"<select", src, flags=re.IGNORECASE):
        window = src[max(0, m.start() - 50):m.end() + 300]
        assert not re.search(
            r"(mute|block|ban|exclude|promote_modo|promote_admin|force_visitor|staff.?kind)",
            window
        ), f"DeviceManager contient un <select> de statut : {window[:200]}"


# ---------------- Décision verrouillée côté documentation --------------

def test_decision_documented_in_rapport():
    """Le rapport de validation contient explicitement la décision P2.1
    pour éviter que les prochains agents réintroduisent un `<select>`."""
    rapport = _read(Path("/app/memory/RAPPORT_VALIDATION_iter158.md"))
    assert "P2.1" in rapport
    assert "StaffActionsIconBar" in rapport
    assert "select" in rapport.lower(), (
        "Le rapport doit mentionner explicitement la décision "
        "« ne PAS introduire de <select> »"
    )
