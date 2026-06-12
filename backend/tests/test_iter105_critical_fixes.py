"""
iter105 — Tests pour les corrections critiques :
- Fix canWrite pour créatrice en mode site=guest (BUG bloquant édition)
- Caly devient widget flottant bottom-right + monté globalement dans App.js
- "Emergent" remplace "Caly" comme nom d'IA dans les chats
- Dimming des vues forcées appliqué côté visiteur (ViewModePicker), pas créa
"""
import os
from pathlib import Path

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_codeforge_iter105")


def test_can_write_creator_in_guest_site_mode():
    """useDeviceIdentity doit garder canWrite=true pour la créatrice
    même quand siteMode === 'guest'. Bug user iter104."""
    hook = Path("/app/frontend/src/hooks/useDeviceIdentity.js").read_text(encoding="utf-8")
    # Le branchement siteMode==='guest' doit checker role
    assert "canWrite = state.role === 'creator';" in hook
    # Le commentaire iter105 doit être présent
    assert "iter105" in hook


def test_can_write_fallback_for_creator():
    """Le fallback (mode inconnu) doit autoriser la créatrice."""
    hook = Path("/app/frontend/src/hooks/useDeviceIdentity.js").read_text(encoding="utf-8")
    # Fallback final
    assert "canWrite = state.role === 'creator';  // fallback" in hook


def test_caly_is_floating_widget():
    """CalyChatbot doit être un widget flottant fixed bottom-right."""
    caly = Path("/app/frontend/src/components/CalyChatbot.jsx").read_text(encoding="utf-8")
    assert 'fixed bottom-5 right-5' in caly
    assert 'caly-floating-btn' in caly
    # L'ancien testid header est supprimé
    assert 'header-caly-btn' not in caly


def test_caly_mounted_globally_in_app():
    """CalyChatbot doit être monté dans App.js (widget global)."""
    app = Path("/app/frontend/src/App.js").read_text(encoding="utf-8")
    assert "import CalyChatbot" in app
    assert "<CalyChatbot />" in app


def test_caly_removed_from_dashboard_topbar():
    """Dashboard.js ne doit plus importer/utiliser CalyChatbot."""
    dash = Path("/app/frontend/src/pages/Dashboard.js").read_text(encoding="utf-8")
    assert "from '../components/CalyChatbot'" not in dash


def test_chat_ai_label_says_emergent():
    """Chat.js doit afficher 'Emergent' et non 'Caly' pour les modèles OpenAI."""
    chat = Path("/app/frontend/src/pages/Chat.js").read_text(encoding="utf-8")
    assert "'Emergent (GPT-5.2)'" in chat
    assert "'Caly (GPT-5.2)'" not in chat


def test_backend_chat_transcript_uses_emergent_speaker():
    """server.py doit utiliser 'Emergent' au lieu de 'Caly' dans les transcripts d'historique."""
    src = Path("/app/backend/server.py").read_text(encoding="utf-8")
    # Pas de "else 'Caly'" dans les transcripts
    assert "else 'Caly')" not in src
    assert "else \"Caly\"" not in src
    # Doit contenir 'Emergent' à la place
    assert "else 'Emergent')" in src or 'else "Emergent"' in src


def test_view_mode_picker_visible_to_visitors_with_forced():
    """ViewModePicker doit être visible aux visiteurs si guest_views est forcé."""
    picker = Path("/app/frontend/src/components/ViewModePicker.jsx").read_text(encoding="utf-8")
    # Plus de return null sur role !== 'creator' inconditionnel
    assert "if (role !== 'creator') return null;" not in picker
    # Nouveau gating : pas créa ET aucune vue forcée → null
    assert "if (!isCreator && forced.length === 0)" in picker


def test_view_mode_picker_dims_forbidden_views_for_visitors():
    """Le picker doit gréer les vues non autorisées pour visiteurs."""
    picker = Path("/app/frontend/src/components/ViewModePicker.jsx").read_text(encoding="utf-8")
    assert "hasForcedConstraint" in picker
    assert "Non autorisé par la créatrice" in picker
    assert "disabled={disabled}" in picker


def test_site_mode_badge_no_dimming_on_creator():
    """SiteModeBadge ne doit PAS griser les vues non-sélectionnées (créa libre)."""
    badge = Path("/app/frontend/src/components/SiteModeBadge.jsx").read_text(encoding="utf-8")
    # Le commentaire iter105 retirant le dimming doit être présent
    assert "iter105" in badge
    # Pas de logique 'dimmed' dans le map des guest_views (revert iter104)
    # On vérifie en cherchant le contenu spécifique : le toggle bouton SiteModeBadge
    # ne doit pas avoir text-white/30 (qui était le greyed pattern)
    assert "text-white/30" not in badge
