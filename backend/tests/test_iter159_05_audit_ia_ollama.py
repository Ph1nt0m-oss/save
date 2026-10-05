"""Chantier iter159.4 — Audit IA + réglage zoom mobile sidebar.

Cette passe est 90 % **audit lecture seule** — un seul changement UX appliqué
(§1 : sidebar mobile encore plus compacte). Tests dédiés :
  §1 : compactage mobile sidebar
  §4 : audit détection Ollama — vérifie le code tel qu'il est
       (pas de nouvelle architecture, juste des assertions sur l'état réel).
"""
from __future__ import annotations

from pathlib import Path

FRONT = Path("/app/frontend/src")
BACK = Path("/app/backend")


def _r(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# §1 — Nouveau réglage zoom : sidebar mobile ~50 % plus compacte
# ---------------------------------------------------------------------------

def test_sidebar_items_mobile_half_height():
    """iter159.4 §1 : padding mobile `px-1.5 py-1` (au lieu de `p-1.5 sm:p-2`)
    pour réduire ~50 % la hauteur des items sidebar sur téléphone."""
    src = _r(FRONT / "pages/Dashboard.js")
    assert "w-full text-left px-1.5 py-1 sm:px-2 sm:py-1.5 lg:p-2 rounded-sm border" in src


def test_sidebar_title_text_smaller_mobile():
    """iter159.4 §1 : titre item sidebar `text-xs sm:text-sm leading-tight`
    (vs text-sm par défaut) + icônes 3x3 sm:4x4."""
    src = _r(FRONT / "pages/Dashboard.js")
    assert 'text-xs sm:text-sm leading-tight' in src
    # Icônes projet réduites sur mobile.
    assert 'w-3 h-3 sm:w-4 sm:h-4 text-[#A1A1AA] flex-shrink-0' in src


def test_sidebar_header_and_new_project_compressed():
    """iter159.4 §1 : header sidebar + bouton Nouveau projet compactés sur
    mobile pour exploiter l'espace vertical."""
    src = _r(FRONT / "pages/Dashboard.js")
    assert 'px-2 py-2 sm:p-3 lg:p-4 border-b border-white/10 flex items-center' in src
    assert 'size="sm"' in src and 'bg-[#E4FF00] text-[#050505] hover:bg-[#E4FF00]/90' in src
    # Icône Sparkles + libellé titre sidebar réduits mobile.
    assert "Sparkles className=\"w-4 h-4 sm:w-5 sm:h-5" in src
    assert 'text-sm sm:text-base' in src


def test_sidebar_filters_pill_compressed():
    """iter159.4 §1 : pills filtres sidebar px-1.5 py-0.5 sur mobile."""
    src = _r(FRONT / "pages/Dashboard.js")
    assert 'text-[10px] sm:text-[11px] px-1.5 py-0.5 sm:px-2 sm:py-1 rounded-sm border' in src


# ---------------------------------------------------------------------------
# §4 — Audit détection Ollama (lecture seule — pas de nouvelle architecture)
# ---------------------------------------------------------------------------

def test_ollama_detection_runs_from_backend_not_browser():
    """Audit : l'endpoint `/system/ollama-status` hit `http://localhost:11434`
    **côté serveur**. Dans un déploiement pod, « localhost » = le pod, PAS
    la machine de l'utilisateur — donc Ollama local user est INVISIBLE.
    Ce test fige l'état actuel pour que la décision d'architecture (côté
    user agent via fetch direct) soit prise en toute conscience."""
    src = _r(BACK / "routes/system_routes.py")
    assert 'os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")' in src
    # L'appel httpx GET est bien côté serveur (async with httpx.AsyncClient).
    assert "async with httpx.AsyncClient(timeout=1.5) as client" in src
    assert 'await client.get(f"{ollama_url}/api/tags")' in src


def test_ollama_recommended_models_whitelist():
    """Audit : whitelist des modèles chat compatibles détectés."""
    src = _r(BACK / "routes/system_routes.py")
    for marker in ('"gemma3:4b"', '"gemma3:2b"', '"deepseek-r1:7b"',
                   '"llama3.2"', '"llama3.2:3b"', '"llama3.2:8b"'):
        assert marker in src, f"Modèle recommandé {marker} manquant"


def test_ollama_frontend_calls_backend_proxy_not_direct():
    """Audit : le frontend `/system/ollama-status` passe par le proxy backend
    (REACT_APP_BACKEND_URL), PAS directement `http://localhost:11434`. C'est
    la raison du bug « gemma3:4b installé mais non détecté » : le backend
    pod ne voit pas le localhost user."""
    chat = _r(FRONT / "pages/Chat.js")
    installer = _r(FRONT / "components/OfflineAIInstaller.jsx")
    # Confirme usage du proxy backend.
    assert '`${API}/system/ollama-status`' in chat
    assert '`${API}/system/ollama-status`' in installer
    # Aucun appel direct `fetch('http://localhost:11434`
    assert 'fetch(\'http://localhost:11434' not in chat
    assert 'fetch("http://localhost:11434' not in chat
    assert 'fetch(\'http://localhost:11434' not in installer
    assert 'fetch("http://localhost:11434' not in installer


def test_ollama_polling_10s_still_present():
    """Confirmé iter159.3 : polling 10 s + auto-unlock."""
    src = _r(FRONT / "pages/Chat.js")
    assert "setInterval(check, 10000)" in src
    assert "le chat est maintenant déverrouillé" in src


# ---------------------------------------------------------------------------
# §2 — Audit routes IA (lecture seule — pas de modif)
# ---------------------------------------------------------------------------

def test_audit_ai_routes_13_models_registered():
    """Audit : les 13 IA sélectionnables sont bien mappées dans MODEL_ROUTES."""
    src = _r(BACK / "server.py")
    required = [
        '"emergent-collab":',          # Emergent collab
        '"vexub-video":',               # Vexub vidéo
        '"claude-5-fable":',            # Claude 5 Fable
        '"gpt-5.5":',                   # GPT 5.5
        '"claude-4.8-opus":',           # Claude 4.8 Opus
        '"claude-4.7-opus-1m":',        # Claude 4.7 Opus (1M)
        '"claude-4.6-sonnet":',         # Claude 4.6 Sonnet
        '"gpt-5.3-codex":',             # GPT 5.3 Codex
        '"gemini-3.1-pro":',            # Gemini 3.1 Pro
        '"gpt-5.4-1m":',                # GPT 5.4 (1M)
        '"grok-4.3":',                  # Grok 4.3
        '"grok-4.20-reasoning":',       # Grok 4.20 Reasoning
        '"lindy-flow":',                # Lindy Flow
    ]
    for key in required:
        assert key in src, f"Route IA manquante : {key}"


def test_audit_vexub_lindy_emergent_fall_through_cascade():
    """Audit : vexub, lindy, emergent-collab n'ont PAS de handler custom.
    Ils tombent dans le cascade LlmChat qui ne supporte que
    openai/anthropic/gemini → fallback silencieux Claude Sonnet 4.5."""
    src = _r(BACK / "server.py")
    # Pas de bloc `if provider == "vexub":` ni "lindy" ni "emergent"
    assert 'if provider == "vexub"' not in src
    assert 'if provider == "lindy"' not in src
    assert 'if provider == "emergent"' not in src
    # Seul xai a un handler direct.
    assert 'if provider == "xai":' in src


def test_audit_xai_grok_requires_env_key():
    """Audit : Grok n'est réellement appelé que si XAI_API_KEY est présente,
    sinon fallback cascade Claude."""
    src = _r(BACK / "server.py")
    assert "from grok_integration import is_xai_available, grok_chat" in src
    assert "if is_xai_available():" in src
    g = _r(BACK / "grok_integration.py")
    assert 'os.environ.get("XAI_API_KEY")' in g


def test_audit_chat_stream_prompt_is_model_neutral():
    """Audit : le prompt est bien model-neutral (post-iter159.2 §3), pas de
    Caly leaké dans /chat/stream."""
    src = _r(BACK / "server.py")
    assert "Chantier iter159.2 §3 — Prompt système MODEL-NEUTRAL" in src
    assert "Tu NE t'appelles PAS Caly" in src
