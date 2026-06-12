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
    """CalyChatbot doit être un widget flottant fixed bottom + right (offset varie selon iter)."""
    caly = Path("/app/frontend/src/components/CalyChatbot.jsx").read_text(encoding="utf-8")
    assert 'fixed bottom-5' in caly
    # right-5 (iter105) ou right-64 (iter106) ou right-36 (iter107)
    assert any(rw in caly for rw in ('right-5 z-', 'right-64', 'right-36', 'right-44', 'right-32', 'right-28', 'right-[88px]'))
    assert 'caly-floating-btn' in caly
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
    """server.py doit utiliser 'Emergent' au lieu de 'Caly' dans les transcripts d'historique
    des conversations IA principales. (Caly elle-même garde son nom pour son propre widget.)"""
    src = Path("/app/backend/server.py").read_text(encoding="utf-8")
    # Doit contenir 'Emergent' comme speaker dans les transcripts d'historique chat
    assert "else 'Emergent')" in src or 'else "Emergent"' in src
    # Toutes les occurrences de "Caly" comme speaker doivent être dans le contexte Caly bot
    # On compte les occurrences problématiques (transcripts d'IA non-Caly)
    lines = src.split('\n')
    bad_lines = []
    for i, line in enumerate(lines):
        if "else 'Caly')" in line or 'else "Caly")' in line:
            # Vérifier si on est dans le contexte Caly endpoint (qui DOIT garder "Caly")
            ctx = '\n'.join(lines[max(0, i-30):i])
            if 'caly_ask' not in ctx and 'CalyAsk' not in ctx and '/caly/' not in ctx:
                bad_lines.append((i+1, line.strip()))
    assert not bad_lines, f"Found 'Caly' speaker in non-Caly contexts: {bad_lines}"


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
