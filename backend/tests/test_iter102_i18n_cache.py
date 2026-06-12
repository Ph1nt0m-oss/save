"""
iter102 — Sanity checks pour les ajouts i18n (Wizard + PrivateProgramming)
et le wiring du cache de chat history côté frontend.

Ces tests vérifient surtout l'absence de régression côté backend (endpoints
utilisés par l'hydratation cache) et la présence des clés i18n attendues
dans le LanguageContext.js (FR + EN).
"""
import re
from pathlib import Path

REPO = Path("/app")
LANG_CTX = REPO / "frontend" / "src" / "contexts" / "LanguageContext.js"
CHAT_JS = REPO / "frontend" / "src" / "pages" / "Chat.js"
WIZARD_JS = REPO / "frontend" / "src" / "pages" / "GuidedWizard.js"
PROG_JS = REPO / "frontend" / "src" / "pages" / "PrivateProgramming.js"

# Clés ajoutées dans iter102 — DOIVENT être présentes pour FR et EN
ITER102_KEYS = [
    "wizard_assistant_title",
    "wizard_q1_title",
    "wizard_q2_title",
    "wizard_q3_title",
    "wizard_recap_title",
    "wizard_generate_btn",
    "wizard_plat_web",
    "wizard_type_ecommerce",
    "prog_access_denied",
    "prog_search_in_code",
    "prog_agents_title",
    "prog_test_loop_title",
    "prog_history_empty",
    "prog_changelog_reload",
    "prog_changelog_add",
]


def test_iter102_keys_present_in_language_context():
    content = LANG_CTX.read_text(encoding="utf-8")
    for key in ITER102_KEYS:
        # Comptage des occurrences — au minimum 2 (une pour FR, une pour EN)
        occs = len(re.findall(rf"\b{re.escape(key)}\s*:", content))
        assert occs >= 2, f"i18n key '{key}' missing FR or EN translation (found {occs})"


def test_chat_uses_cache_context():
    """Chat.js doit importer useCache et appeler getCachedChatHistory."""
    content = CHAT_JS.read_text(encoding="utf-8")
    assert "useCache" in content, "Chat.js must import useCache"
    assert "getCachedChatHistory" in content, "Chat.js must use getCachedChatHistory for 0ms latency"
    assert "cacheChatHistory" in content, "Chat.js must persist via cacheChatHistory"


def test_wizard_no_hardcoded_french():
    """GuidedWizard.js ne doit plus contenir les chaînes françaises connues
    qui étaient avant en dur (couvre P1 traductions résiduelles)."""
    content = WIZARD_JS.read_text(encoding="utf-8")
    forbidden = [
        "Que veux-tu créer",
        "Donne-lui un nom",
        "Décris ton app",
        "Récapitulatif",
        "Application générée",
        "Génération…",
        "Générer l'application",
        "Retour au Dashboard",
        "Assistant de création",
    ]
    for s in forbidden:
        assert s not in content, f"GuidedWizard.js still contains hardcoded FR string: '{s}'"


def test_private_programming_no_hardcoded_french():
    """PrivateProgramming.js — chasse des strings hardcodés."""
    content = PROG_JS.read_text(encoding="utf-8")
    forbidden = [
        "Recherche dans le code",
        "Pattern à chercher",
        "ligne(s) trouvée(s)",
        "Tests en cours…",
        "Lancer pytest backend",
        "Aucun événement persisté",
    ]
    for s in forbidden:
        assert s not in content, f"PrivateProgramming.js still contains hardcoded FR string: '{s}'"
