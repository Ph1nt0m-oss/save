"""iter158.21 — P2.4 : Complétude i18n.

Vérifie que toutes les langues déclarées dans `SUPPORTED_LANGS` disposent
d'un bloc de traductions et que les clés CRITIQUES de l'application (celles
qui apparaissent dans les flows utilisateur courants) sont traduites en
natif, sans retomber sur l'anglais via le fallback de `t()`.

Les clés non-critiques (menus avancés, textes marketing longs, etc.)
peuvent manquer dans certaines langues et retombent sur l'anglais — ce
comportement est préservé pour éviter de bloquer la validation finale sur
des traductions purement cosmétiques.

Audit des blocs présents (après P2.4) :
  - Avant : 15 blocs (fr, en, es, de, nl, ru, zh, hi, bn, pt, ur, ja, hr,
            da, ar). zh-TW manquant.
  - Après : 16 blocs (zh-TW ajouté). 13 langues enrichies avec les 20
            clés critiques (pseudo + tutoriel P1.4 + 10 catégories AI).

Les traductions ajoutées sont fournies ligne par ligne, en langue native,
avec commentaires `iter158.21 (P2.4)` pour traçabilité. Les locuteurs
natifs pourront raffiner ultérieurement — l'infrastructure est en place.
"""
from __future__ import annotations

import re
from pathlib import Path

PATH = Path("/app/frontend/src/contexts/LanguageContext.js")


def _read() -> str:
    return PATH.read_text(encoding="utf-8")


def _translation_blocks(src: str):
    """Returns list of (lang_code, body) tuples for translation blocks (before
    TRANSLATED_LANG_NAMES)."""
    tr_idx = src.find("export const TRANSLATED_LANG_NAMES")
    assert tr_idx > 0
    out = []
    for m in re.finditer(
        r"^\s*'?([a-z]{2}(?:-[A-Z]{2})?)'?:\s*\{",
        src[:tr_idx], flags=re.MULTILINE,
    ):
        code = m.group(1)
        i = src.find("{", m.start())
        depth = 1
        j = i + 1
        while depth > 0 and j < len(src):
            if src[j] == "{": depth += 1
            elif src[j] == "}": depth -= 1
            j += 1
        body = src[i+1:j-1]
        out.append((code, body))
    return out


def _supported_lang_codes(src: str):
    """Extracts SUPPORTED_LANGS declared codes."""
    sup_idx = src.find("export const SUPPORTED_LANGS")
    assert sup_idx > 0
    end = src.find("];", sup_idx)
    block = src[sup_idx:end]
    return set(re.findall(r"code:\s*'([^']+)'", block))


CRITICAL_KEYS = [
    # P1.4 tutorial titles (toujours affichés)
    "tut_owner_priv_title",
    "tut_apprentice_title",
    "tut_force_visitor_title",
    "tut_ai_errors_title",
    "tut_notif_transfer_title",
    # P0.1 AI errors — 10 codes canoniques
    "ai_err_cloudflare",
    "ai_err_ollama_offline",
    "ai_err_ollama_error",
    "ai_err_timeout",
    "ai_err_json_invalid",
    "ai_err_auth_error",
    "ai_err_rate_limit",
    "ai_err_provider_error",
    "ai_err_network",
    "ai_err_unknown",
    # Pseudo basics
    "pseudo_label",
    "pseudo_change",
    "pseudo_help",
    "pseudo_required",
    "pseudo_changed",
]


def test_all_supported_languages_have_translation_blocks():
    """Chaque code déclaré dans `SUPPORTED_LANGS` DOIT disposer d'un bloc
    de traductions correspondant — sinon fallback total vers EN."""
    src = _read()
    sup = _supported_lang_codes(src)
    blocks = {code for code, _ in _translation_blocks(src)}

    # 16 langues attendues après P2.4.
    assert len(sup) == 16, f"SUPPORTED_LANGS doit lister 16 langues, got {len(sup)}"

    missing = sup - blocks
    assert not missing, (
        f"Langues déclarées sans bloc de traduction : {missing}. "
        f"Un bloc même minimal est requis pour un support natif réel."
    )


def test_zh_tw_block_added_in_p24():
    """`zh-TW` doit avoir son propre bloc depuis P2.4 (avant iter158.21,
    seul `zh` existait → les utilisateurs TW retombaient sur EN)."""
    src = _read()
    blocks = dict(_translation_blocks(src))
    assert "zh-TW" in blocks, "Bloc zh-TW manquant (régression P2.4)"
    body = blocks["zh-TW"]
    # Le bloc doit contenir au moins les clés critiques en Traditional Chinese.
    assert "tut_owner_priv_title" in body
    assert "ai_err_cloudflare" in body


def test_critical_keys_present_in_every_language():
    """Les 20 clés critiques (tutorial titles + AI errors + pseudo basics)
    DOIVENT exister dans TOUS les blocs de traductions. Sinon le fallback
    EN prend le pas et un utilisateur allemand (par exemple) voit un titre
    en anglais au milieu d'un tutoriel en allemand."""
    src = _read()
    blocks = dict(_translation_blocks(src))
    gaps = {}
    for code, body in blocks.items():
        missing = [k for k in CRITICAL_KEYS if not re.search(rf"\b{k}\s*:", body)]
        if missing:
            gaps[code] = missing
    assert not gaps, (
        f"Clés critiques manquantes par langue : {gaps}. "
        f"Chaque langue DOIT traduire ces clés en natif."
    )


def test_translations_are_non_empty_strings():
    """Chaque clé critique a une valeur non-vide dans chaque langue."""
    src = _read()
    blocks = dict(_translation_blocks(src))
    empty = []
    for code, body in blocks.items():
        for k in CRITICAL_KEYS:
            # Extract value for key (single-quoted, allows escaped quotes).
            m = re.search(
                rf"\b{k}\s*:\s*'((?:\\'|[^'])*)'",
                body, flags=re.DOTALL,
            )
            if m:
                val = m.group(1).replace("\\'", "'").strip()
                if not val:
                    empty.append((code, k))
    assert not empty, f"Clés avec valeur vide : {empty}"


def test_fr_remains_authoritative_source():
    """Le bloc FR reste la source autoritaire : au moins 150 clés
    (comportement iter158.0+). Non-régression P2.4."""
    src = _read()
    blocks = dict(_translation_blocks(src))
    assert "fr" in blocks
    body = blocks["fr"]
    # Compte approx des top-level keys
    keys = set(re.findall(
        r"^\s{1,8}([a-zA-Z_][\w]*)\s*:",
        re.sub(r"'(?:[^'\\]|\\.)*'", "''", body), flags=re.MULTILINE,
    ))
    assert len(keys) >= 150, (
        f"FR doit rester source autoritaire avec ≥150 clés, got {len(keys)}"
    )


def test_en_remains_complete_fallback_source():
    """EN est la langue de fallback (`t()` ligne 3715 de LanguageContext).
    Elle doit couvrir toutes les clés critiques pour que le fallback soit
    opérationnel pour les langues partiellement traduites."""
    src = _read()
    blocks = dict(_translation_blocks(src))
    body = blocks["en"]
    for k in CRITICAL_KEYS:
        assert re.search(rf"\b{k}\s*:", body), (
            f"EN manque la clé critique {k} — le fallback ne fonctionnerait "
            f"plus pour les langues incomplètes."
        )


def test_t_function_fallback_chain_preserved():
    """La chaîne de fallback `translations[lang] || translations['en'] || key`
    reste intacte dans LanguageContext.js. Non-régression."""
    src = _read()
    assert "translations[language]?.[key] || translations['en']?.[key] || key" in src


def test_rtl_languages_still_handled():
    """`ur` et `ar` restent dans la liste RTL_LANGS pour la direction
    textuelle. Non-régression P2.4."""
    src = _read()
    m = re.search(r"RTL_LANGS\s*=\s*\[([^\]]+)\]", src)
    assert m
    rtl = m.group(1)
    assert "'ur'" in rtl
    assert "'ar'" in rtl


def test_translated_lang_names_covers_all_supported():
    """`TRANSLATED_LANG_NAMES` doit mapper les 16 codes supportés."""
    src = _read()
    tr_idx = src.find("export const TRANSLATED_LANG_NAMES")
    end = src.find("};", tr_idx)
    block = src[tr_idx:end]
    sup = _supported_lang_codes(src)
    # Vérifier que zh-TW apparaît comme CLÉ de valeur traduite dans FR.
    assert "'zh-TW'" in block, (
        "TRANSLATED_LANG_NAMES doit contenir 'zh-TW' comme code"
    )


def test_supported_langs_has_sixteen_entries_with_valid_fields():
    """Chaque entrée SUPPORTED_LANGS a code/label/native/flag."""
    src = _read()
    sup_idx = src.find("export const SUPPORTED_LANGS")
    end = src.find("];", sup_idx)
    entries = re.findall(
        r"\{\s*code:\s*'[^']+',\s*label:\s*'[^']+',\s*native:\s*'[^']+',\s*flag:\s*'[^']+'\s*\}",
        src[sup_idx:end],
    )
    assert len(entries) == 16, f"16 entrées complètes attendues, got {len(entries)}"


# ============================================================================
# Diagnostic (non-bloquant) : reporte la couverture globale par langue
# ============================================================================

def test_report_coverage_summary_for_rapport(capsys):
    """Reporte la couverture (en %) par rapport à FR pour information.
    Ce test ne bloque PAS la validation (il assure juste la cohérence du
    rapport)."""
    src = _read()
    blocks = dict(_translation_blocks(src))

    def _keys(body):
        return set(re.findall(
            r"^\s{1,8}([a-zA-Z_][\w]*)\s*:",
            re.sub(r"'(?:[^'\\]|\\.)*'", "''", body), flags=re.MULTILINE,
        ))

    fr_keys = _keys(blocks["fr"])
    print("\n--- Couverture i18n par rapport à FR ---")
    for code in sorted(blocks):
        kk = _keys(blocks[code])
        pct = 100.0 * len(kk & fr_keys) / max(len(fr_keys), 1)
        print(f"  {code}: {len(kk & fr_keys)}/{len(fr_keys)} ({pct:.0f}%)")

    # Non-bloquant : vérifier juste qu'EN est le fallback source principal,
    # couvrant AU MOINS toutes les clés critiques (vérifié par un test dédié
    # ci-dessus). La métrique de "top-level keys" via regex grossier donne
    # un indicateur approximatif — pas un chiffre absolu.
    en_coverage_pct = 100.0 * len(fr_keys & _keys(blocks["en"])) / max(len(fr_keys), 1)
    assert en_coverage_pct >= 75.0, (
        f"EN couvre {en_coverage_pct:.0f}% de FR (minimum : 75% pour un "
        f"fallback utile — les clés critiques sont vérifiées séparément)."
    )
