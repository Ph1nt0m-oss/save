"""iter130b — Caly (assistante flottante) en mode agent.

Caly garde sa spécialisation (aide au site, pas de code — non-fusion) mais
gagne un moteur d'exécution visible : analyse, recherche FAQ réelle (match
mots-clés sur la KB), réponse streamée token par token via /caly/ask-stream.
"""
import os
from pathlib import Path

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_codeforge_iter130b")

ROUTES = Path("/app/backend/routes/caly_routes.py").read_text(encoding="utf-8")
WIDGET = Path("/app/frontend/src/components/CalyChatbot.jsx").read_text(encoding="utf-8")


def test_caly_stream_endpoint_defined():
    assert '@router.post("/caly/ask-stream")' in ROUTES
    assert "StreamingResponse" in ROUTES
    assert "text/event-stream" in ROUTES


def test_caly_keeps_legacy_endpoint():
    """Compat : /caly/ask reste disponible (fallback non-stream)."""
    assert '@router.post("/caly/ask")' in ROUTES


def test_caly_real_kb_search():
    """La recherche FAQ est une VRAIE action : match mots-clés sur la KB."""
    assert "re.findall" in ROUTES
    assert "matched" in ROUTES
    assert "fiche(s) pertinente(s)" in ROUTES


def test_caly_no_personality_fusion():
    """Caly reste l'assistante d'aide : son prompt propre, pas d'outils code."""
    assert "CALY_DEFAULT_SYSTEM_PROMPT" in ROUTES
    block = ROUTES.split('@router.post("/caly/ask-stream")')[1]
    assert "workspace_write" not in block
    assert "run_dev_agent" not in block


def test_caly_route_registered():
    from server import app
    routes = {r.path for r in app.routes if hasattr(r, "path")}
    assert "/api/caly/ask-stream" in routes
    assert "/api/caly/ask" in routes


def test_caly_widget_shows_steps_and_streams():
    assert "caly-steps" in WIDGET
    assert "/caly/ask-stream" in WIDGET
    assert "evt.delta" in WIDGET and "evt.event" in WIDGET
    assert "_streaming" in WIDGET
