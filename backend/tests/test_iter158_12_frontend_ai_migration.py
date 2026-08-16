"""iter158.12 — P1.1 : Tests migration des call sites frontend AI restants.

Vérifie que Create.js et GuidedWizard.js utilisent le mapper partagé
`lib/aiErrorMapper.js` au lieu de messages génériques ad-hoc.

Périmètre :
  - Create.js : call `/api/generate` (LLM)
  - GuidedWizard.js : 3 catches Wizard AI suggest + 1 catch generate principal

Autres pages :
  - Discover.js : aucun call LLM identifié — hors périmètre
  - PrivateChatbotProgramming.js : config bots + files, pas de LLM direct — hors périmètre
  - Chat.js : déjà migré iter158.7
"""
from __future__ import annotations

from pathlib import Path

FRONT = Path("/app/frontend/src")


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_mapper_still_exists():
    p = FRONT / "lib/aiErrorMapper.js"
    assert p.exists()
    src = _read(p)
    assert "export function classifyAiError" in src


def test_create_js_uses_mapper():
    src = _read(FRONT / "pages/Create.js")
    assert "classifyAiError" in src
    assert "aiErrorMapper" in src
    # L'ancien message hardcodé est retiré
    assert "'Erreur de génération'" not in src
    assert "Le mode en ligne utilise l'IA cloud, le mode hors ligne nécessite Ollama installé localement" not in src
    # Utilise t(i18nKey) || fallback
    assert "t(errInfo.i18nKey)" in src
    # Le context est spécifique (aide diagnostic)
    assert "context: 'create.generate'" in src


def test_create_js_stores_error_code_in_message():
    """Chaque bulle d'erreur garde _error_code pour identification UI/diagnostic."""
    src = _read(FRONT / "pages/Create.js")
    assert "_error_code: errInfo.code" in src


def test_guided_wizard_migrated_all_catches():
    src = _read(FRONT / "pages/GuidedWizard.js")
    assert "classifyAiError" in src
    # 3 contexts distincts pour suggest + 1 pour generate
    for ctx in ("wizard.suggest.name", "wizard.suggest.design",
                "wizard.suggest.func", "wizard.generate"):
        assert f"context: '{ctx}'" in src, f"Context {ctx} manquant"
    # Le catch générique 'Suggestion impossible' est retiré
    assert "toast.error('Suggestion impossible')" not in src


def test_guided_wizard_falls_back_to_i18n_key_when_available():
    src = _read(FRONT / "pages/GuidedWizard.js")
    # t(errInfo.i18nKey) || errInfo.fallback est utilisé
    assert "t(errInfo.i18nKey)" in src
    # Le fallback ultime pour /generate garde wizard_error_toast si mapper retourne unknown
    idx = src.find("context: 'wizard.generate'")
    block = src[idx:idx + 500]
    assert "wizard_error_toast" in block


def test_no_leak_technical_details_to_user():
    """Les logs techniques restent en console.warn — jamais dans toast/messages."""
    src_c = _read(FRONT / "pages/Create.js")
    src_w = _read(FRONT / "pages/GuidedWizard.js")
    # Chaque call site logge en console.warn '[AI error]'
    assert "console.warn('[AI error]'" in src_c
    assert "console.warn('[AI error]'" in src_w


def test_discover_and_chatbotprogramming_not_touched():
    """Ces fichiers n'ont pas de call LLM direct — pas de migration nécessaire.
    On vérifie qu'ils N'ONT PAS été ajoutés à tort au périmètre."""
    src_disc = _read(FRONT / "pages/Discover.js")
    src_cbp = _read(FRONT / "pages/PrivateChatbotProgramming.js")
    # Aucun import classifyAiError (ils ne devraient pas en avoir besoin)
    assert "classifyAiError" not in src_disc
    assert "classifyAiError" not in src_cbp


def test_chat_js_still_uses_mapper():
    """Sanity : Chat.js migré iter158.7 reste inchangé."""
    src = _read(FRONT / "pages/Chat.js")
    assert "classifyAiError" in src
    assert "context: 'chat_send_text'" in src


def test_mapper_returns_all_ten_codes():
    """Le mapper couvre les 10 catégories utilisées par les call sites."""
    src = _read(FRONT / "lib/aiErrorMapper.js")
    for c in ("cloudflare", "ollama_offline", "ollama_error", "timeout",
              "json_invalid", "auth_error", "rate_limit", "provider_error",
              "network", "unknown"):
        assert f"'{c}'" in src or f'"{c}"' in src
