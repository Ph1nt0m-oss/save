"""
iter107 — Tests pour les changements demandés :
- Sécurité programming page : créa physique + PAS en simulation
- Claude Fable 5 ajouté dans les routes backend
- Spacings : Caly right-36 (3cm vers droite), public ml-24 (5cm gauche supplémentaire), langues ml-24 (5cm droite supplémentaire)
- ViewModePicker : "Aucune vue active" + contrainte forcée applique partout
"""
import os
from pathlib import Path

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_codeforge_iter107")

from server import app  # noqa: E402


def test_programming_blocked_in_simulation_view():
    """PrivateProgramming.js : 'allowed' doit exiger canSeeProgramming ET pas en simulation."""
    src = Path("/app/frontend/src/pages/PrivateProgramming.js").read_text(encoding="utf-8")
    # Le check doit combiner canSeeProgramming + isInSimulation false
    assert "isInSimulation" in src
    assert "canSeeProgramming && !isInSimulation" in src


def test_claude_fable_5_in_create_routes():
    """server.py : CREATE_MODEL_ROUTES contient claude-fable-5 et l'id frontend."""
    src = Path("/app/backend/server.py").read_text(encoding="utf-8")
    assert '"claude-fable-5":  ("anthropic", "claude-fable-5")' in src
    assert '"claude-5-fable":  ("anthropic", "claude-fable-5")' in src


def test_claude_fable_5_in_chat_routes():
    """server.py : la route chat doit aussi accepter Claude Fable."""
    src = Path("/app/backend/server.py").read_text(encoding="utf-8")
    assert '"claude-fable":     ("anthropic", "claude-fable-5")' in src


def test_claude_fable_5_label_in_chat():
    """Chat.js : badge IA distingue Claude Fable."""
    chat = Path("/app/frontend/src/pages/Chat.js").read_text(encoding="utf-8")
    assert "'Claude Fable 5'" in chat


def test_caly_offset_iter107_or_newer():
    """Caly à right-36 (iter107), right-32 (iter108) ou right-28 (iter109)."""
    caly = Path("/app/frontend/src/components/CalyChatbot.jsx").read_text(encoding="utf-8")
    assert any(rw in caly for rw in ("right-36", "right-32", "right-28"))
    assert "right-64" not in caly


def test_dashboard_spacings_iter107():
    """Dashboard.js : ml-24+ (5cm extra) ou ml-32/40 (iter109) pour langues et SiteModeBadge."""
    dash = Path("/app/frontend/src/pages/Dashboard.js").read_text(encoding="utf-8")
    # Doit contenir AU MOINS un des spacing widths recents
    found = sum(1 for m in ("ml-3 sm:ml-24", "ml-3 sm:ml-32", "ml-3 sm:ml-40") if m in dash)
    assert found >= 2, f"Expected ≥2 spacing widths, got {found}"


def test_view_mode_picker_aucune_vue_active():
    """ViewModePicker affiche 'Aucune vue active' quand pas en simulation."""
    picker = Path("/app/frontend/src/components/ViewModePicker.jsx").read_text(encoding="utf-8")
    assert "Aucune vue active" in picker


def test_view_mode_picker_constraint_applies_to_all():
    """iter107 — hasForcedConstraint applique à tout le monde (créa incluse)."""
    picker = Path("/app/frontend/src/components/ViewModePicker.jsx").read_text(encoding="utf-8")
    # La nouvelle déf n'a plus `!isCreator && ...`
    assert "const hasForcedConstraint = forced.length > 0;" in picker
