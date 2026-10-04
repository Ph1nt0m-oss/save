"""Chantier iter159.2 — Tests frontend-static dédiés aux 7 corrections post-vérif
utilisateur :
  §1 Dashboard élargi (+50%) + hauteur réduite
  §2 Autres comptes : 12 icônes TOUJOURS visibles sans estompement, pas de
     doublons de statut
  §3 IA réelle : prompt neutre, nom modèle affiché, points animés
  §4 Titre auto : respect langue UI (payload language)
  §5 Création : timeout 180s + message actionnable
  §6 Ollama check à chaque entrée + recommended_available
"""
from __future__ import annotations

from pathlib import Path

FRONT = Path("/app/frontend/src")
BACK = Path("/app/backend")


def _read(p: str) -> str:
    base = FRONT if not p.startswith("backend/") else Path("/app")
    return (base / p).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# §1 — Dashboard largeur + hauteur
# ---------------------------------------------------------------------------

def test_dashboard_main_grid_tighter_gap():
    """Grille principale : gap-2 sm:gap-3 (réduit depuis gap-3 sm:gap-4)."""
    src = _read("pages/Dashboard.js")
    assert 'grid grid-cols-1 sm:grid-cols-2 gap-2 sm:gap-3 cf-export-blocked" data-testid="main-actions-grid"' in src


def test_dashboard_cards_padding_reduced():
    """Les 4 cartes principales : p-3 sm:p-3.5 (hauteur réduite ~50 %)."""
    src = _read("pages/Dashboard.js")
    # Au moins 4 occurrences du nouveau padding compact.
    hits = src.count("rounded-lg p-3 sm:p-3.5 backdrop-blur-xl")
    assert hits >= 4, f"Attendu >=4 cartes à padding p-3/p-3.5, trouvé {hits}"


# ---------------------------------------------------------------------------
# §2 — Autres comptes : 12 icônes identiques
# ---------------------------------------------------------------------------

def test_accounts_button_has_12_action_keys():
    """Les 12 keys d'action exactes doivent apparaître dans makeBtn (ordre fixe)."""
    src = _read("components/AccountsButton.jsx")
    required = [
        "key: 'visit'", "key: 'rename'", "key: 'admin'", "key: 'modo'",
        "key: 'visitor'", "key: 'remove-creator'", "key: 'delete'",
        "key: 'disconnect'", "key: 'exclude'",
    ]
    for k in required:
        assert k in src, f"Action key manquante : {k}"
    # Boutons toggle (mute/unmute, block/unblock, ban/unban) via expression ternaire.
    assert "a.muted ? 'unmute' : 'mute'" in src
    assert "a.role === 'blocked' ? 'unblock' : 'block'" in src
    assert "a.banned ? 'unban' : 'ban'" in src


def test_accounts_button_removes_duplicate_status_badges():
    """iter159.2 §2 : les badges statut secondaires (inactif/banned/
    excluded/muted/pending_creator_review) ne doivent PLUS être rendus — seul
    le badge Rang reste comme info de statut."""
    src = _read("components/AccountsButton.jsx")
    assert ">inactif<" not in src, "badge 'inactif' encore présent"
    assert ">banned<" not in src, "badge 'banned' encore présent"
    assert ">excluded<" not in src, "badge 'excluded' encore présent"
    assert ">muted<" not in src, "badge 'muted' encore présent"
    assert "Validation temporaire" not in src, "badge pending_creator_review encore présent"


def test_accounts_button_rank_badge_still_present():
    """Rang reste la SEULE info de statut affichée."""
    src = _read("components/AccountsButton.jsx")
    assert "data-testid={`acc-rank-${a.key_id}`}" in src
    assert "computeRank" in src


def test_accounts_button_silent_noop_on_disabled():
    """Un clic sur une action non applicable est un no-op silencieux :
    pas d'attribut `disabled` HTML, pas d'appel API, le visuel reste
    identique aux actions actives."""
    src = _read("components/AccountsButton.jsx")
    # Pas d'attribut `disabled={!enabled}` dans makeBtn — le helper utilise
    # un safeClick qui fait un no-op () => {} quand enabled est falsy.
    assert "const safeClick = enabled ? (onClick || (() => {})) : (() => {});" in src
    assert "// IMPORTANT : pas de `disabled` HTML" in src


# ---------------------------------------------------------------------------
# §3 — IA réelle : prompt neutre + nom modèle + points animés
# ---------------------------------------------------------------------------

def test_chat_prompt_is_model_neutral_backend():
    """Backend /chat/stream : le system_prompt ne commence plus par
    « Tu es Caly ». Il interdit explicitement de se présenter comme Caly."""
    src = _read("backend/server.py")
    # On cherche le prompt rebooté.
    assert "Chantier iter159.2 §3 — Prompt système MODEL-NEUTRAL" in src
    # Le fragment interdit est bien là.
    assert "Tu NE t'appelles PAS Caly" in src
    # L'ancien fragment "Tu es **Caly**" doit avoir disparu de la portion
    # system_prompt de /chat/stream.
    # (Caly reste présent dans caly_routes.py et dans la définition historique
    # du widget — pas dans /chat/stream.)
    chat_stream_pos = src.find("Chantier iter159.2 §3 — Prompt système MODEL-NEUTRAL")
    assert chat_stream_pos > 0
    # Vérifie que dans un rayon de 4000 chars autour, il n'y a pas « Tu es **Caly** ».
    window = src[max(0, chat_stream_pos - 200):chat_stream_pos + 4000]
    assert "Tu es **Caly**" not in window


def test_chat_shows_real_model_name():
    """Chat.js affiche le NOM DU MODÈLE RÉEL (GPT-5.5, Claude Fable 5, etc.)
    dans la bulle « L'IA écrit », pas « Caly »."""
    src = _read("pages/Chat.js")
    assert "modelLabels" in src
    assert "'gpt-5.5':" in src and "'GPT-5.5'" in src
    assert "'claude-sonnet'" in src and "'Claude Sonnet 4.5'" in src
    assert "'gemini-3-pro'" in src and "'Gemini 3 Pro'" in src
    # Aucune mention "Caly" dans la bulle rendue (le mot peut rester dans
    # les commentaires JSX qui expliquent la correction).
    status_pos = src.find('data-testid="chat-ai-status"')
    assert status_pos > 0
    bubble_src = src[status_pos:status_pos + 2500]
    # Retire les commentaires JSX `{/* ... */}` et `//` avant la vérif.
    import re as _re
    cleaned = _re.sub(r"\{/\*.*?\*/\}", "", bubble_src, flags=_re.DOTALL)
    cleaned = _re.sub(r"//[^\n]*", "", cleaned)
    assert "Caly" not in cleaned, "'Caly' encore rendu dans la bulle AI status"


def test_chat_dots_animation_defined():
    """Keyframe @keyframes cfdot définie dans index.css."""
    src = _read("index.css")
    assert "@keyframes cfdot" in src
    assert "translateY(-2px)" in src


# ---------------------------------------------------------------------------
# §4 — Titre auto : langue UI
# ---------------------------------------------------------------------------

def test_auto_title_backend_accepts_language_param():
    """Endpoint /auto-title accepte un payload avec `language` et l'applique
    au prompt LLM."""
    src = _read("backend/routes/projects_routes.py")
    assert "payload: dict | None = None" in src
    assert 'payload or {}).get("language")' in src
    assert "Langue OBLIGATOIRE : **{lang_label}**" in src


def test_chat_sends_language_to_auto_title():
    """Chat.js envoie `{language}` dans le body du POST auto-title."""
    src = _read("pages/Chat.js")
    pos = src.find("/auto-title`")
    assert pos > 0
    window = src[pos:pos + 400]
    assert "language: (language || 'fr')" in window


# ---------------------------------------------------------------------------
# §5 — Création : timeout 180s + message actionnable
# ---------------------------------------------------------------------------

def test_create_has_client_timeout_and_actionable_error():
    src = _read("pages/Create.js")
    assert "AbortController" in src
    assert "setTimeout(() => controller.abort('client_timeout')" in src
    assert "'ai_timeout_client'" in src
    assert "elle continue en arrière-plan" in src.lower() or "arrière-plan côté serveur" in src


# ---------------------------------------------------------------------------
# §6 — Ollama à chaque entrée
# ---------------------------------------------------------------------------

def test_ollama_backend_returns_recommended_available():
    src = _read("backend/routes/system_routes.py")
    assert "recommended_available" in src
    assert "RECOMMENDED =" in src
    # Garanti : pas de cache serveur, HTTP /api/tags hit à chaque appel.
    assert "pas de cache" in src.lower() or "Jamais de cache serveur" in src


def test_chat_and_create_recheck_ollama_on_each_entry():
    """Chat.js et Create.js re-contrôlent Ollama à chaque entrée en mode
    offline (useEffect dep sur `mode`), et refusent l'accès si pas prêt."""
    for p in ("pages/Chat.js", "pages/Create.js"):
        src = _read(p)
        assert "/system/ollama-status" in src, f"{p} : check endpoint manquant"
        assert "recommended_available" in src, f"{p} : check modèle recommandé manquant"
        assert "setShowOfflineInstaller(true)" in src, f"{p} : tutoriel natif non déclenché"


def test_chat_blocks_send_when_offline_unavailable():
    """Chat.js : sendText refuse d'envoyer si offline + pas disponible."""
    src = _read("pages/Chat.js")
    assert "if (mode === 'offline' && !ollamaAvailable)" in src
    assert "IA locale non détectée" in src


def test_create_blocks_generate_when_offline_unavailable():
    src = _read("pages/Create.js")
    assert "if (mode === 'offline' && !ollamaAvailable)" in src
    assert "IA locale non détectée" in src
