"""iter158.8 — P0.1 : Tests couverture backend du AI Error Mapper.

Vérifie que les 4 call sites LLM du monolithe `server.py` utilisent
maintenant `classify_ai_error` (spec P0.1 : « aucune voie LLM importante
ne doit contourner ai_error_mapper.py »).

Call sites audités :
  1. server.py: `/api/generate` Ollama fallback (mode=offline)
  2. server.py: `/api/generate` Emergent LLM cascade
  3. server.py: `/api/ai/generate-code` Ollama-only (JSON parse + HTTP)
  4. server.py: `/api/chat/message` Ollama offline
  5. server.py: `/api/chat/message` Emergent cascade
"""
from __future__ import annotations

from pathlib import Path

BACK = Path("/app/backend")


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_server_generate_ollama_uses_mapper():
    src = _read(BACK / "server.py")
    # Le bloc Ollama de /api/generate contient classify_ai_error
    idx = src.find("# Try Ollama first (for offline mode or if requested)")
    assert idx > 0
    block = src[idx:idx + 3500]
    assert "classify_ai_error" in block
    assert "context='server.generate.ollama'" in block
    # Cas erreur applicative (result['error']) + HTTP status != 200 + Exception
    assert block.count("classify_ai_error") >= 3


def test_server_generate_emergent_uses_mapper():
    src = _read(BACK / "server.py")
    idx = src.find("Fallback to Emergent AI")
    assert idx > 0
    # Le bloc emergent est long (~1600 lignes de routing) — cherche jusqu'à
    # 15000 chars ou jusqu'au except Exception qui suit
    end = src.find('generate_basic_template(description)', idx)
    assert end > 0
    block = src[idx:end]
    assert "classify_ai_error" in block
    assert "context='server.generate.emergent'" in block


def test_server_generate_exposes_ai_error_code():
    """La réponse HTTP /api/generate contient `ai_error_code` (None si aucun problème)."""
    src = _read(BACK / "server.py")
    idx = src.find('"ai_error_code": ai_error_code')
    assert idx > 0
    # Défini au début du flow
    assert "ai_error_code = None" in src


def test_ai_generate_code_uses_mapper():
    src = _read(BACK / "server.py")
    idx = src.find("async def _ai_generate_code_impl")
    assert idx > 0
    block = src[idx:idx + 5000]
    assert "classify_ai_error" in block
    # 3 usages : JSON parse fail, HTTP != 200, Exception globale
    assert block.count("classify_ai_error") >= 3
    # Réponse d'erreur inclut error_code + message localisé
    assert '"error_code":' in block
    # 503 spécifique pour ollama_offline
    assert "ollama_offline" in block


def test_send_chat_message_ollama_uses_mapper():
    src = _read(BACK / "server.py")
    idx = src.find("context='server.send_chat_message.ollama'")
    assert idx > 0


def test_send_chat_message_emergent_uses_mapper():
    src = _read(BACK / "server.py")
    idx = src.find("context='server.send_chat_message.emergent'")
    assert idx > 0


def test_no_regression_generic_ollama_log():
    """Les vieux logs génériques `Ollama not available: {e}` sont remplacés
    par des logs avec `[<code>]:` pour aider le diagnostic."""
    src = _read(BACK / "server.py")
    # L'ancien format brut ne doit plus exister isolé
    assert 'logger.warning(f"Ollama not available: {e}")' not in src
    assert 'logger.warning(f"Ollama error: {result.get(\'error\')}")' not in src
    assert 'logger.info(f"Ollama offline unreachable: {ollama_error}")' not in src
    # Les nouveaux formats existent
    assert "Ollama not available [{info['code']}]" in src
    assert "Ollama error [{info['code']}]" in src or "Ollama offline unreachable [{info['code']}]" in src


def test_all_context_labels_prefixed_by_server_dot():
    """Chaque appel `classify_ai_error` dans server.py doit préciser un
    `context='server.<flow>'` pour diagnostic clair dans les logs."""
    src = _read(BACK / "server.py")
    # Extraire les contextes utilisés
    import re
    contexts = re.findall(r"context='(server\.[a-z_.]+)'", src)
    assert len(contexts) >= 5, f"Attendu ≥5 contextes classify, trouvé {contexts}"
    expected_prefixes = {
        "server.generate.ollama",
        "server.generate.emergent",
        "server.ai_generate_code",
        "server.send_chat_message.ollama",
        "server.send_chat_message.emergent",
    }
    for exp in expected_prefixes:
        assert any(c.startswith(exp) for c in contexts), (
            f"Contexte manquant : {exp}. Trouvés : {contexts}"
        )
