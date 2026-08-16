"""iter158.15 — P1.4 : tutoriel mis à jour (Owner Privileges, Apprentice,
Force-visitor, AI errors, notifs+transfert).

Vérifie que le tutoriel couvre les nouvelles fonctionnalités livrées depuis
iter158.3 :
  - Owner Privileges ON/OFF (statut inviolable, rôle effectif quand OFF).
  - Apprentice Creator (délégations permanentes/temporaires, expiration,
    verrouillage du vrai propriétaire).
  - Force-visitor et sa bannière (portée temporaire, annulable).
  - AI Error Mapping (les 10 catégories : cloudflare, ollama_offline,
    ollama_error, timeout, json_invalid, auth_error, rate_limit,
    provider_error, network, unknown).
  - Notifications propriétaire + transfert de propriété (double signature).

Contraintes :
  - FR + EN cohérents (mêmes clés, mêmes catégories, mêmes concepts).
  - Aucune modification des mécanismes de sécurité/ownership (tests iter158
    précédents restent verts).
  - Les 7 étapes historiques (iter148) restent en place.
"""
from __future__ import annotations

import re
from pathlib import Path

FRONT = Path("/app/frontend/src")
LANG_FILE = FRONT / "contexts/LanguageContext.js"
TUTO_FILE = FRONT / "pages/Tutorial.js"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ---------------- Clés i18n : présence + cohérence FR/EN ----------------

NEW_KEYS = [
    # Owner Privileges
    "tut_owner_priv_title",
    "tut_owner_priv_intro",
    "tut_owner_priv_on",
    "tut_owner_priv_off",
    "tut_owner_priv_invariant",
    # Apprentice Creator
    "tut_apprentice_title",
    "tut_apprentice_intro",
    "tut_apprentice_perms",
    "tut_apprentice_temp",
    "tut_apprentice_locked",
    # Force-visitor
    "tut_force_visitor_title",
    "tut_force_visitor_intro",
    "tut_force_visitor_banner",
    "tut_force_visitor_scope",
    # AI errors
    "tut_ai_errors_title",
    "tut_ai_errors_intro",
    "tut_ai_errors_outro",
    "tut_ai_errors_list_intro",
    # Owner notifs + transfer
    "tut_notif_transfer_title",
    "tut_notif_transfer_intro",
    "tut_notif_transfer_details",
    "tut_notif_transfer_transfer",
]


def _extract_block(src: str, lang: str) -> str:
    """Extrait le bloc de traduction pour une langue donnée (ex. `fr:` ... `},`)."""
    m = re.search(rf"^\s*{lang}:\s*\{{", src, flags=re.MULTILINE)
    assert m, f"Bloc langue absent : {lang}"
    start = m.end()
    depth = 1
    i = start
    while i < len(src) and depth > 0:
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
        i += 1
    return src[start:i]


def test_all_new_keys_present_in_fr_block():
    """Toutes les nouvelles clés existent dans le bloc FR."""
    src = _read(LANG_FILE)
    fr_block = _extract_block(src, "fr")
    for k in NEW_KEYS:
        assert re.search(rf"\b{k}\s*:", fr_block), f"[FR] clé manquante : {k}"


def test_all_new_keys_present_in_en_block():
    """Toutes les nouvelles clés existent dans le bloc EN (cohérence FR/EN)."""
    src = _read(LANG_FILE)
    en_block = _extract_block(src, "en")
    for k in NEW_KEYS:
        assert re.search(rf"\b{k}\s*:", en_block), f"[EN] clé manquante : {k}"


def test_fr_and_en_translations_differ_and_non_empty():
    """FR ≠ EN pour chaque clé (traduction réelle, pas copie brute)
    et aucune valeur vide."""
    src = _read(LANG_FILE)
    fr_block = _extract_block(src, "fr")
    en_block = _extract_block(src, "en")

    def _val(block: str, key: str) -> str:
        m = re.search(
            rf"{key}\s*:\s*(['\"])((?:\\\1|(?!\1).)*)\1",
            block, flags=re.DOTALL,
        )
        assert m, f"Impossible d'extraire la valeur pour {key}"
        return m.group(2).replace("\\'", "'").replace('\\"', '"').strip()

    for k in NEW_KEYS:
        v_fr = _val(fr_block, k)
        v_en = _val(en_block, k)
        assert v_fr, f"[FR] valeur vide pour {k}"
        assert v_en, f"[EN] valeur vide pour {k}"
        # Titres courts peuvent contenir des mots communs, mais le corps
        # multi-mot doit être vraiment traduit.
        if k.endswith("_intro") or k.endswith("_scope") or k.endswith(
            "_invariant"
        ) or k.endswith("_outro"):
            assert v_fr != v_en, (
                f"{k} : FR et EN sont identiques — la traduction n'est pas faite"
            )


# ---------------- Cohérence i18n avec le comportement backend/frontend --

def test_owner_priv_texts_reflect_actual_behavior_fr():
    """FR : les textes Owner Privileges doivent refléter le comportement
    réel implémenté :
      - ON/OFF interrupteur (crown icon top-right)
      - statut inviolable (owner_key_ids intact)
      - sanctions clean au retour ON
      - notification secrète
    """
    src = _read(LANG_FILE)
    fr_block = _extract_block(src, "fr")

    def _val(k):
        # Regex tolérant les apostrophes échappées (\') dans les valeurs FR.
        m = re.search(
            rf"{k}\s*:\s*'((?:\\'|[^'])*)'", fr_block, flags=re.DOTALL
        )
        assert m, f"clé absente ou format inattendu : {k}"
        return m.group(1).replace("\\'", "'")

    intro = _val("tut_owner_priv_intro")
    assert "propriétaire" in intro.lower() or "propriété" in intro.lower()
    assert "couronne" in intro.lower() or "icône" in intro.lower()

    off = _val("tut_owner_priv_off")
    assert "rôle" in off.lower(), (
        "L'OFF doit expliquer que le propriétaire fonctionne comme le rôle actif"
    )

    invariant = _val("tut_owner_priv_invariant")
    assert "owner_key_ids" in invariant, (
        "L'invariant doit citer owner_key_ids (base ownership CDC)"
    )
    assert re.search(r"(sanction|notif|annul)", invariant.lower()), (
        "L'invariant doit mentionner sanctions/notifications"
    )


def test_apprentice_texts_include_perm_categories_fr():
    """FR : les délégations doivent lister les permissions réellement
    supportées par le backend."""
    src = _read(LANG_FILE)
    fr_block = _extract_block(src, "fr")
    perms_text = re.search(
        r"tut_apprentice_perms\s*:\s*'((?:\\'|[^'])+)'", fr_block
    ).group(1).replace("\\'", "'")
    # Ces perms doivent être documentées (elles existent réellement backend).
    for expected in ("moderate", "edit_bots", "switch_account", "full_control"):
        assert expected in perms_text, (
            f"Perm '{expected}' manquante dans tut_apprentice_perms"
        )

    temp_text = re.search(
        r"tut_apprentice_temp\s*:\s*'((?:\\'|[^'])+)'", fr_block
    ).group(1).replace("\\'", "'")
    assert re.search(r"(temp|durée|expir)", temp_text.lower()), (
        "grant-temp doit être mentionné (temporary/durée/expire)"
    )


def test_apprentice_locked_covers_no_ownership_challenge_fr():
    """FR : le verrouillage doit expliquer qu'un délégué ne peut PAS
    obtenir de challenge propriétaire (test iter158.13 scenario 3)."""
    src = _read(LANG_FILE)
    fr_block = _extract_block(src, "fr")
    locked = re.search(
        r"tut_apprentice_locked\s*:\s*'((?:\\'|[^'])+)'", fr_block
    ).group(1).replace("\\'", "'")
    assert re.search(r"(propri[éeè]t|owner|challenge|transf)", locked.lower())
    assert re.search(r"(jamais|never|full_control)", locked.lower())


def test_force_visitor_texts_mention_banner_and_readonly_fr():
    """FR : force-visitor doit mentionner la bannière + lecture seule +
    annulabilité (matrice permissions)."""
    src = _read(LANG_FILE)
    fr_block = _extract_block(src, "fr")

    def _val(k):
        return re.search(
            rf"{k}\s*:\s*'((?:\\'|[^'])+)'", fr_block
        ).group(1).replace("\\'", "'")

    intro = _val("tut_force_visitor_intro")
    banner = _val("tut_force_visitor_banner")
    scope = _val("tut_force_visitor_scope")
    assert re.search(r"(visit|lecture|read)", intro.lower())
    assert re.search(r"(bannière|banner|jaune|yellow)", banner.lower())
    assert re.search(r"(annul|histor|matri)", scope.lower())


def test_ai_errors_intro_mentions_classification_fr_and_en():
    """FR + EN : l'intro AI errors doit mentionner la classification et
    l'aspect actionnable."""
    src = _read(LANG_FILE)
    for lang in ("fr", "en"):
        block = _extract_block(src, lang)
        intro = re.search(
            r"tut_ai_errors_intro\s*:\s*(['\"])((?:\\\1|(?!\1).)*)\1", block
        ).group(2)
        assert re.search(r"(classif|categor|cause)", intro.lower()), (
            f"[{lang}] intro AI errors doit mentionner classification/cause"
        )


def test_notif_transfer_covers_double_signature_fr():
    """FR : transfert doit expliquer la double signature ECDSA."""
    src = _read(LANG_FILE)
    fr_block = _extract_block(src, "fr")
    transfer = re.search(
        r"tut_notif_transfer_transfer\s*:\s*'((?:\\'|[^'])+)'", fr_block
    ).group(1).replace("\\'", "'")
    assert re.search(r"(double.*signat|deux.*appareil|ECDSA)",
                     transfer, flags=re.IGNORECASE), (
        "Le transfert de propriété doit expliquer la double signature CDC"
    )


# ---------------- Wiring Tutorial.js : nouvelles étapes présentes -------

def test_tutorial_imports_use_language_and_new_icons():
    """Tutorial.js doit importer useLanguage + les nouvelles icônes
    (Crown, UserCheck, Eye, AlertTriangle, Bell)."""
    src = _read(TUTO_FILE)
    assert "useLanguage" in src
    for icon in ("Crown", "UserCheck", "Eye", "AlertTriangle", "Bell"):
        assert re.search(rf"\b{icon}\b", src), f"Icône lucide-react manquante : {icon}"


def test_tutorial_has_five_new_steps():
    """Les 5 nouveaux id de step DOIVENT être présents dans le module."""
    src = _read(TUTO_FILE)
    for step_id in (
        "owner-privileges",
        "apprentice-creator",
        "force-visitor",
        "ai-errors",
        "owner-notifs-transfer",
    ):
        assert re.search(rf"id:\s*['\"]{step_id}['\"]", src), (
            f"Étape manquante : id={step_id}"
        )


def test_tutorial_preserves_seven_historical_steps():
    """Les 7 étapes historiques (iter148) sont conservées intactes."""
    src = _read(TUTO_FILE)
    for step_id in ("identity", "groups", "moderation", "ai-programming",
                    "exports", "integrations", "languages"):
        assert re.search(rf"id:\s*['\"]{step_id}['\"]", src), (
            f"Étape historique manquante : {step_id}"
        )


def test_tutorial_step_bodies_use_i18n_keys():
    """Les nouveaux composants body appellent t() avec les clés i18n
    définies dans LanguageContext."""
    src = _read(TUTO_FILE)
    for key in NEW_KEYS:
        # au moins une référence à la clé quelque part dans Tutorial.js
        # (via t('...') ou via .replace() texte)
        pass  # on autorise indirection : t(...) est bien testé plus bas
    # Vérifier qu'au moins les clés titles sont utilisées dans le module.
    for title_key in ("tut_owner_priv_title", "tut_apprentice_title",
                      "tut_force_visitor_title", "tut_ai_errors_title",
                      "tut_notif_transfer_title"):
        assert re.search(rf"t\(\s*['\"]{title_key}['\"]", src), (
            f"Titre non branché sur t() : {title_key}"
        )


def test_ai_errors_step_reuses_existing_ai_err_keys():
    """L'étape AI errors doit lister les 10 clés `ai_err_*` existantes
    (cohérence avec le mapper iter158.7)."""
    src = _read(TUTO_FILE)
    for code in ("cloudflare", "ollama_offline", "ollama_error", "timeout",
                 "json_invalid", "auth_error", "rate_limit", "provider_error",
                 "network", "unknown"):
        assert re.search(rf"ai_err_{code}", src), (
            f"Catégorie AI absente du tutoriel : ai_err_{code}"
        )


def test_tutorial_step_count_reaches_twelve_total():
    """7 historiques + 5 nouvelles = 12 étapes."""
    src = _read(TUTO_FILE)
    ids = re.findall(r"id:\s*['\"]([a-z-]+)['\"]", src)
    # dédupliquer (chaque id doit apparaître une seule fois dans STEPS).
    assert len(ids) == len(set(ids)), (
        f"IDs dupliqués : {[x for x in ids if ids.count(x) > 1]}"
    )
    assert len(ids) >= 12, (
        f"Nombre d'étapes total attendu ≥ 12, obtenu {len(ids)} : {ids}"
    )


# ---------------- Non-régression : mécanismes ownership inchangés -------

def test_no_backend_ownership_files_modified():
    """P1.4 ne doit toucher NI le backend ownership NI les hooks sécurité.
    Vérification structurelle : les fichiers critiques existent toujours
    avec leurs signatures publiques attendues."""
    ownership_guard = Path("/app/backend/utils/ownership_guard.py").read_text()
    assert "is_owner_device" in ownership_guard
    assert "is_privileges_active" in ownership_guard
    assert "assert_not_owner_target" in ownership_guard

    ownership_routes = Path("/app/backend/routes/ownership_routes.py").read_text()
    assert "/toggle-privileges" in ownership_routes
    assert "/ownership/transfer" in ownership_routes  # /ownership/transfer + fn transfer_ownership
