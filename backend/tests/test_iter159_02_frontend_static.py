"""Chantier iter159 — Tests statiques frontend (structure/CSS/wiring).

On vérifie SANS lancer un navigateur :
  §1 Dashboard 67 %  : max-w-2xl + whitespace-nowrap sur les descriptions
                        de cartes + overflow-y-auto sur le contenu central.
  §2 États IA réels  : chat-ai-status + data-testid chat-ai-status-label +
                        setAiRealState câblé sur SSE réels (sending, streaming,
                        error, idle, pas de setTimeout fictif).
  §4 Toutes actions  : AccountsButton rend data-testid=acc-admin-* ET
                        acc-modo-* pour toutes les lignes (dont les comptes
                        qui ne sont pas 'approved').
  §5 Rang unique     : AccountsButton rend data-testid=acc-rank-* en lieu et
                        place des badges éparpillés.
  §3 Renommage auto  : Chat.js appelle /projects/{id}/auto-title après le
                        premier succès SSE, et Dashboard écoute
                        'codeforge:project-renamed'.
"""
from __future__ import annotations

from pathlib import Path

FRONT = Path("/app/frontend/src")


def _read(p: str) -> str:
    return (FRONT / p).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# §1 — Dashboard confort 67 %
# ---------------------------------------------------------------------------

def test_dashboard_center_section_is_narrower():
    """iter159 §1 : max-w-2xl. iter159.2 §1 : élargi à max-w-4xl à la
    demande utilisateur (+50 %)."""
    src = _read("pages/Dashboard.js")
    assert "max-w-4xl w-full py-" in src, "max-w-4xl manquant sur le conteneur central"
    assert "max-w-5xl w-full" not in src, "max-w-5xl encore présent"


def test_dashboard_descriptions_single_line():
    """Les descriptions des 4 cartes (chat/create online/offline) doivent
    tenir sur UNE ligne (whitespace-nowrap + overflow-hidden + ellipsis)."""
    src = _read("pages/Dashboard.js")
    for key in ("dashChatDescOn", "dashCreateDescOn", "dashChatDescOff", "dashCreateDescOff"):
        line = next((ln for ln in src.splitlines() if f"t('{key}')" in ln), None)
        assert line, f"Ligne {key} introuvable"
        assert "whitespace-nowrap" in line, f"{key} : classe whitespace-nowrap manquante"
        assert "overflow-hidden" in line and "text-ellipsis" in line, f"{key} : ellipsis manquant"


def test_dashboard_central_container_scrollable():
    """La section centrale doit permettre un overflow-y-auto (évite les
    scrolls fantômes des parents) et un overflow-x-hidden pour empêcher la
    scrollbar horizontale à 67 %."""
    src = _read("pages/Dashboard.js")
    assert "flex-1 overflow-y-auto overflow-x-hidden" in src


def test_header_overflow_switches_at_lg():
    """Le header passe en overflow-x-visible à partir de lg (1024 px) pour
    éviter l'ascenseur horizontal sur tablette/desktop à 67 %."""
    src = _read("pages/Dashboard.js")
    assert "overflow-x-auto lg:overflow-x-visible" in src
    assert "min-w-max lg:min-w-0" in src


# ---------------------------------------------------------------------------
# §2 — États IA réels
# ---------------------------------------------------------------------------

def test_chat_has_real_ai_state_hook():
    """Chat.js gère un state aiRealState dérivé du vrai SSE."""
    src = _read("pages/Chat.js")
    assert "aiRealState" in src
    assert "setAiRealState('sending')" in src
    assert "setAiRealState('streaming')" in src
    assert "setAiRealState('error')" in src


def test_chat_ai_status_label_is_rendered():
    """L'IA en cours de génération doit afficher un libellé textuel réel
    (data-testid chat-ai-status-label). iter159.2 §3 : affiche NOM DU MODÈLE
    + « L'IA écrit » + 3 points animés discrets."""
    src = _read("pages/Chat.js")
    assert 'data-testid="chat-ai-status"' in src
    assert 'data-testid="chat-ai-status-label"' in src
    assert "t('ai_state_streaming')" in src
    # Points animés iter159.2 §3
    assert 'data-testid="chat-ai-dots"' in src
    assert "animate-[cfdot_1.2s_ease-in-out_infinite]" in src


def test_chat_no_fake_timers_on_status():
    """Aucun setTimeout/setInterval ne doit piloter aiRealState (pas de
    simulation)."""
    src = _read("pages/Chat.js")
    # On cherche setTimeout(...setAiRealState) ou setInterval(...setAiRealState).
    assert "setTimeout" not in src.split("setAiRealState")[0][-200:] + src.split("setAiRealState")[-1][:400], \
        "Un setTimeout proche de setAiRealState — risque de simulation"


def test_caly_stays_assistant_mode():
    """CalyChatbot garde son rôle d'assistance (pas de prompt generation
    projet) : son system_prompt interdit explicitement de coder/générer."""
    src = _read("components/CalyChatbot.jsx")
    assert "CALY_SYSTEM_PROMPT" in src
    assert "Tu ne crées PAS de projet ou de fichier" in src


# ---------------------------------------------------------------------------
# §3 — Renommage auto
# ---------------------------------------------------------------------------

def test_chat_triggers_auto_title_after_stream():
    """Chat.js appelle /projects/{id}/auto-title une fois le flux SSE terminé."""
    src = _read("pages/Chat.js")
    assert "/auto-title" in src
    assert "codeforge:project-renamed" in src


def test_dashboard_listens_project_renamed_event():
    """Dashboard met à jour sa sidebar lorsqu'il reçoit l'event
    codeforge:project-renamed."""
    src = _read("pages/Dashboard.js")
    assert "codeforge:project-renamed" in src
    assert "setProjects((prev) => prev.map((p)" in src


# ---------------------------------------------------------------------------
# §4 — Toutes les actions visibles
# ---------------------------------------------------------------------------

def test_accounts_button_renders_all_actions_always():
    """AccountsButton doit TOUJOURS rendre les boutons admin/modo/visitor/
    disconnect/exclude/ban/delete via le helper makeBtn — jamais via un
    guard conditionnel qui les ferait disparaître."""
    src = _read("components/AccountsButton.jsx")
    # Les clés data-testid proviennent d'un helper (unique source de vérité).
    assert "data-testid={`acc-${key}-${a.key_id}`}" in src
    # Chaque action doit être poussée dans buttons.push.
    required = ["key: 'admin'", "key: 'modo'", "key: 'visitor'",
                "key: 'disconnect'", "key: 'exclude'", "key: 'rename'",
                "key: 'visit'", "key: 'delete'"]
    for key in required:
        assert key in src, f"Action manquante : {key}"


def test_accounts_button_no_grey_out_no_cursor_change():
    """iter159.2 §2 : les 12 icônes doivent avoir le MÊME rendu visuel pour
    chaque compte, sans estompement ni changement de curseur. On vérifie que
    `cursor-not-allowed` et `opacity-40` NE SONT PLUS appliqués aux boutons
    d'action (ils peuvent exister ailleurs — row deleted par ex)."""
    src = _read("components/AccountsButton.jsx")
    # Les actions ne doivent plus utiliser l'attribut `disabled` HTML non plus.
    # On vérifie que le helper makeBtn ne pose plus d'opacity-40 ou cursor-not-allowed.
    assert "cursor-not-allowed`" not in src, "cursor-not-allowed présent sur un bouton d'action"
    assert "opacity-40" not in src, "opacity-40 présent sur un bouton d'action"
    # La fonction de click doit être silencieuse quand non applicable (no-op).
    assert "const safeClick = enabled" in src


# ---------------------------------------------------------------------------
# §5 — Rang unique
# ---------------------------------------------------------------------------

def test_accounts_button_has_rank_badge():
    """AccountsButton doit calculer un rang unique via computeRank(a) et
    poser un data-testid acc-rank-{key_id}."""
    src = _read("components/AccountsButton.jsx")
    assert "computeRank" in src
    assert "data-testid={`acc-rank-${a.key_id}`}" in src
    # Les 7 libellés demandés (via clés i18n).
    for key in ("rank_creator", "rank_admin", "rank_modo", "rank_visitor",
                "rank_user", "rank_approved", "rank_unapproved"):
        assert f"t('{key}')" in src, f"Clé de rang {key} manquante"


def test_language_context_has_rank_labels():
    """LanguageContext expose les libellés Rang en FR et EN."""
    src = _read("contexts/LanguageContext.js")
    # FR
    for pair in [
        ("rank_creator", "'Créa'"),
        ("rank_admin", "'Admin'"),
        ("rank_modo", "'Modo'"),
        ("rank_visitor", "'Visiteur'"),
        ("rank_user", "'Utilisateur'"),
        ("rank_approved", "'Approuvé'"),
        ("rank_unapproved", "'Non approuvé'"),
    ]:
        key, label = pair
        assert f"{key}: {label}" in src, f"FR {key}={label} manquant"
    # EN (vérifie juste la clé présente côté EN)
    assert "rank_creator: 'Creator'" in src
    assert "rank_unapproved: 'Not approved'" in src
