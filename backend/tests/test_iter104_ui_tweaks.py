"""
iter104 — Tests pour les changements UI demandés par l'utilisatrice :
- Bouton ZIP renommé (plus de "ZIP + GitHub")
- Couleurs : Theft red, ViewModePicker cyan, SiteModeBadge citron (existing)
- "(lecture seule)" sur chaque "Forcer la vue X"
- CalyChatbot rose, repositionné à côté du rond jaune des idées
- Cohérence ViewModePicker avec guestViews forcés
- Endpoint write-file pour édition directe du code
"""
import os
from pathlib import Path

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_codeforge_iter104")

from server import app  # noqa: E402


# ============================================================================
# Backend : write-file endpoint
# ============================================================================

def test_write_file_endpoint_registered():
    routes = {r.path for r in app.routes if hasattr(r, "path")}
    assert "/api/private/code/write-file" in routes


def test_write_file_signature_requires_creator():
    """Le helper de signature doit être appelé : sans signature valide → erreur."""
    src = Path("/app/backend/server.py").read_text(encoding="utf-8")
    # Le helper write-file doit appeler _require_creator_signature
    idx = src.find("@api_router.post(\"/private/code/write-file\")")
    assert idx > 0
    chunk = src[idx:idx + 2000]
    assert "_require_creator_signature" in chunk


def test_write_file_path_restrictions():
    """Le source doit contenir les restrictions de chemins."""
    src = Path("/app/backend/server.py").read_text(encoding="utf-8")
    assert "_WRITE_ALLOWED_PREFIXES" in src
    assert "_WRITE_FORBIDDEN_SUFFIXES" in src
    assert "backend/" in src
    assert "frontend/src/" in src


# ============================================================================
# Frontend : UI tweaks
# ============================================================================

def test_zip_button_renamed():
    """Dashboard.js doit afficher juste 'ZIP', plus 'ZIP + GitHub'."""
    dash = Path("/app/frontend/src/pages/Dashboard.js").read_text(encoding="utf-8")
    assert "ZIP + GitHub" not in dash
    assert ">ZIP<" in dash or ">ZIP</span>" in dash


def test_theft_button_red():
    """TheftButton doit utiliser des classes rouges (bg-red-500)."""
    btn = Path("/app/frontend/src/components/TheftButton.jsx").read_text(encoding="utf-8")
    assert "bg-red-500" in btn
    assert "border-red-400" in btn


def test_view_mode_picker_cyan():
    """ViewModePicker doit utiliser cyan en couleur principale."""
    picker = Path("/app/frontend/src/components/ViewModePicker.jsx").read_text(encoding="utf-8")
    assert "bg-cyan-500" in picker
    assert "border-cyan-400" in picker
    # Plus de E4FF00 (citron) sur le bouton toggle
    # (E4FF00 reste OK dans le dropdown content pour le "désactiver toutes")


def test_caly_chatbot_pink():
    """CalyChatbot doit être rose (widget flottant iter105)."""
    caly = Path("/app/frontend/src/components/CalyChatbot.jsx").read_text(encoding="utf-8")
    # Le bouton flottant utilise bg-pink-500/95 + border-pink-300
    assert "bg-pink-" in caly
    assert "border-pink-" in caly


def test_guest_views_have_read_only_labels():
    """Toutes les options 'Forcer la vue X' incluent '(lecture seule)'."""
    ctx = Path("/app/frontend/src/contexts/LanguageContext.js").read_text(encoding="utf-8")
    # FR
    assert "Forcer la vue utilisateur (lecture seule)" in ctx
    assert "Forcer la vue modo (lecture seule)" in ctx
    assert "Forcer la vue admin (lecture seule)" in ctx
    assert "Forcer la vue créatrice (lecture seule)" in ctx
    # EN
    assert "Force user view (read-only)" in ctx
    assert "Force modo view (read-only)" in ctx
    assert "Force admin view (read-only)" in ctx
    assert "Force creator view (read-only)" in ctx


def test_view_mode_picker_handles_creator_as_default():
    """iter104→iter115 — Le toggle universel sur 'creator' : cliquer active la
    case Vue créatrice (viewMode='creator'), recliquer décoche (viewMode=null)."""
    picker = Path("/app/frontend/src/components/ViewModePicker.jsx").read_text(encoding="utf-8")
    # iter115 : toggle universel "active = m === viewMode" gère 'creator' comme les autres.
    assert "const active = m === viewMode;" in picker


def test_view_mode_picker_shows_forced_views_hint():
    """iter104 — Quand guest est cliqué et qu'il y a des forcedViews, affiche un hint."""
    picker = Path("/app/frontend/src/components/ViewModePicker.jsx").read_text(encoding="utf-8")
    assert "forced" in picker
    assert "Forcée vers" in picker or "↳" in picker


def test_private_programming_has_write_capability():
    """SiteProgrammingPanel doit avoir un textarea éditable + bouton Sauvegarder."""
    prog = Path("/app/frontend/src/pages/PrivateProgramming.js").read_text(encoding="utf-8")
    assert "private-code-textarea" in prog
    assert "private-save-file-btn" in prog
    assert "/private/code/write-file" in prog
    assert "saveFile" in prog
