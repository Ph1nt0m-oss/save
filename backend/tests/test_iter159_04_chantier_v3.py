"""Chantier iter159.3 — Tests pour les 8 points du 3e chantier post-vérif.

Backend-side tests (via HTTP contre le backend running). Pour les points
UI purs (dashboard, autres comptes, tutoriel adapté appareil), on fait
du static-grep sur la source frontend.
"""
from __future__ import annotations

import os
import uuid
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import requests
from pymongo import MongoClient


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")
FRONT = Path("/app/frontend/src")


def _read(p: str) -> str:
    return (FRONT / p).read_text(encoding="utf-8")


@pytest.fixture
def mongo():
    cli = MongoClient(MONGO_URL)
    yield cli[DB_NAME]
    cli.close()


# ---------------------------------------------------------------------------
# §1 — Dashboard : max-w-6xl + cards p-2/2.5
# ---------------------------------------------------------------------------

def test_dashboard_cards_doubled_width():
    """iter159.3 §1 : max-w-6xl (×2 vs max-w-4xl précédent)."""
    src = _read("pages/Dashboard.js")
    assert "max-w-6xl w-full py-" in src, "max-w-6xl manquant"
    assert "max-w-4xl w-full py-" not in src, "max-w-4xl encore présent"


def test_dashboard_cards_half_height():
    """iter159.3 §1 : cartes p-2 sm:p-2.5 (hauteur ÷2 vs p-3/3.5 précédent)."""
    src = _read("pages/Dashboard.js")
    hits = src.count("rounded-lg p-2 sm:p-2.5 backdrop-blur-xl")
    assert hits >= 4, f"Attendu >=4 cartes à p-2/2.5, trouvé {hits}"


def test_dashboard_sidebar_items_compressed():
    """iter159.3 §1 : items sidebar compactés avec px-1.5 py-1 sur mobile
    (hauteur ÷ ~50 % vs p-3 initial), transition à p-2 à partir de sm."""
    src = _read("pages/Dashboard.js")
    assert "w-full text-left px-1.5 py-1 sm:px-2 sm:py-1.5 lg:p-2 rounded-sm border" in src


# ---------------------------------------------------------------------------
# §3 — Titre normalisé (snap mots entiers, pas d'ellipsis)
# ---------------------------------------------------------------------------

def test_backend_truncates_project_title_on_word_boundary():
    """iter159.3 §3 : la création auto d'un projet via /chat/stream normalise
    le titre sur mot entier, sans ellipsis finale."""
    src = Path("/app/backend/routes/chat_advanced_routes.py").read_text(encoding="utf-8")
    assert "_snap_words" in src
    assert '"title_manual": False' in src


def test_dashboard_rename_strips_trailing_ellipsis():
    """iter159.3 §3 : le champ Renommer reprend le titre affiché sans
    ellipsis finale."""
    src = _read("pages/Dashboard.js")
    # On vérifie que startRename nettoie l'ellipsis.
    assert "project.name || '').replace(/[…\\u2026\\s]+$/" in src, \
        "Normalisation ellipsis absente dans startRename"


# ---------------------------------------------------------------------------
# §6 — Preferred view persistance serveur
# ---------------------------------------------------------------------------

def test_preferred_view_endpoints_exist():
    """GET + PUT /api/system/preferred-view doivent exister."""
    # GET sans key_id → 200 avec null
    r = requests.get(f"{API}/system/preferred-view", timeout=10)
    assert r.status_code == 200
    assert r.json() == {"preferred_view": None}


def test_preferred_view_round_trip(mongo):
    kid = f"key_test_{uuid.uuid4().hex[:10]}"
    try:
        # PUT guest
        r = requests.put(f"{API}/system/preferred-view",
                         json={"key_id": kid, "preferred_view": "guest"},
                         timeout=10)
        assert r.status_code == 200
        assert r.json()["preferred_view"] == "guest"

        # GET
        r2 = requests.get(f"{API}/system/preferred-view",
                          params={"key_id": kid}, timeout=10)
        assert r2.status_code == 200
        assert r2.json()["preferred_view"] == "guest"

        # Mongo trace
        doc = mongo.device_preferences.find_one({"key_id": kid})
        assert doc and doc.get("preferred_view") == "guest"

        # PUT None (clear)
        r3 = requests.put(f"{API}/system/preferred-view",
                          json={"key_id": kid, "preferred_view": None},
                          timeout=10)
        assert r3.status_code == 200
        assert r3.json()["preferred_view"] is None
    finally:
        mongo.device_preferences.delete_many({"key_id": kid})


def test_preferred_view_rejects_invalid():
    r = requests.put(f"{API}/system/preferred-view",
                     json={"key_id": "k1", "preferred_view": "superadmin"},
                     timeout=10)
    assert r.status_code == 400


def test_frontend_hooks_recover_preferred_view_on_mount():
    """useDeviceIdentity doit tenter de récupérer preferred_view serveur si
    localStorage est vide."""
    src = _read("hooks/useDeviceIdentity.js")
    assert "/system/preferred-view" in src
    assert "if (!readViewMode() && result.keyId)" in src
    # setStoredViewMode doit aussi faire un PUT fire-and-forget.
    assert "axios.put(`${API}/system/preferred-view`" in src


# ---------------------------------------------------------------------------
# §7 — Ollama polling + lock/unlock automatique
# ---------------------------------------------------------------------------

def test_chat_polls_ollama_every_10s_in_offline():
    """iter159.3 §7 : setInterval 10 s + auto-unlock. iter160 §8 : la détection
    est maintenant côté navigateur (fetch http://localhost:11434), le toast
    change libellé."""
    src = _read("pages/Chat.js")
    assert "setInterval(check, 10000)" in src
    # Message de déverrouillage (texte peut varier iter160).
    assert "déverrouillage automatique" in src or "le chat est maintenant déverrouillé" in src


def test_chat_input_voice_locked_when_offline_unavailable():
    """iter159.3 §7 : textarea, VoiceRecorder et Send désactivés quand
    offlineLocked = mode offline + !ollamaAvailable."""
    src = _read("pages/Chat.js")
    assert "const offlineLocked = mode === 'offline' && !ollamaAvailable" in src
    assert "data-offline-locked" in src
    # Les VoiceRecorder doivent dépendre de voiceDisabled qui inclut offlineLocked.
    assert "disabled={voiceDisabled}" in src


def test_chat_non_blocking_banner_not_forced_modal():
    """iter159.3 §7 : le user peut fermer le tutoriel sans déverrouiller.
    Le banner reste visible tant que !ollamaAvailable, avec un lien manuel."""
    src = _read("pages/Chat.js")
    assert 'data-testid="chat-offline-lock-banner"' in src
    assert 'data-testid="chat-offline-install-link"' in src
    # sendText NE doit PLUS forcer setShowOfflineInstaller(true).
    send_pos = src.find("const sendText = async")
    assert send_pos > 0
    window = src[send_pos:send_pos + 1500]
    assert "setShowOfflineInstaller(true)" not in window, \
        "sendText force encore l'ouverture du modal — devrait être non-bloquant"


# ---------------------------------------------------------------------------
# §8 — Tutoriel Ollama adapté à l'appareil
# ---------------------------------------------------------------------------

def test_tutorial_has_android_phone_and_tablet_variants():
    """iter159.3 §8 : parcours android_phone + android_tablet ajoutés."""
    src = _read("components/OfflineAIInstaller.jsx")
    assert "android_phone:" in src
    assert "android_tablet:" in src


def test_tutorial_desktop_vs_mobile_commands():
    """iter159.3 §8 : sur mobile, pas de référence à « Invite de commandes »
    ou PowerShell comme contexte d'exécution. Sur desktop (windows), la
    référence CMD/PowerShell reste pertinente."""
    src = _read("components/OfflineAIInstaller.jsx")
    # Les parcours mobile mentionnent explicitement « PAS depuis une Invite ».
    assert "PAS depuis une « Invite de commandes » Windows" in src
    # Pas de « Exécuter OllamaSetup.exe » dans android_* (c'est un .exe desktop).
    android_phone_block = src[src.find("android_phone:"):src.find("android_tablet:")]
    assert "OllamaSetup.exe" not in android_phone_block
    android_tablet_block = src[src.find("android_tablet:"):src.find("android_tablet:") + 1500]
    assert "OllamaSetup.exe" not in android_tablet_block


def test_tutorial_detects_device_class():
    """iter159.3 §8 : détection isAndroidPhone / isAndroidTablet / isIPad."""
    src = _read("components/OfflineAIInstaller.jsx")
    for marker in ("isAndroidPhone", "isAndroidTablet", "isIPad", "isIPhone"):
        assert marker in src, f"Marqueur détection {marker} manquant"
    # Fallback explicite si impossible à déterminer.
    assert "Fallback desktop" in src or "else setOs('windows')" in src


# ---------------------------------------------------------------------------
# §4+5 — Autres comptes : 12 icônes + 7 rangs (régression)
# ---------------------------------------------------------------------------

def test_autres_comptes_still_has_12_icons_no_greying():
    """Garantit que la correction iter159.2 §2 est préservée."""
    src = _read("components/AccountsButton.jsx")
    assert "const safeClick = enabled" in src
    assert "cursor-not-allowed`" not in src
    assert "opacity-40" not in src


def test_ranks_7_labels_still_mapped():
    src = _read("components/AccountsButton.jsx")
    for k in ("rank_creator", "rank_admin", "rank_modo", "rank_visitor",
              "rank_user", "rank_approved", "rank_unapproved"):
        assert f"t('{k}')" in src
