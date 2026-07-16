"""iter114b — Test du vrai streaming natif via emergentintegrations stream_message.
iter129 — /chat/stream vit dans routes/chat_advanced_routes.py et délègue au
pipeline multi-agents (agents/) qui stream nativement via stream_message."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROUTES = (ROOT / "backend" / "routes" / "chat_advanced_routes.py").read_text()
COMMON = (ROOT / "backend" / "agents" / "common.py").read_text()


def test_chat_stream_uses_native_stream_message():
    """Le pipeline multi-agents utilise stream_message() (vrai SSE token-par-token)."""
    assert "stream_message" in COMMON
    assert "TextDelta" in COMMON
    assert "StreamDone" in COMMON
    block = ROUTES.split('@router.post("/chat/stream")')[1]
    assert "run_pipeline" in block


def test_chat_stream_has_fallback_for_attachments():
    """Le mode avec attachments ou offline retombe sur le pseudo-streaming
    (préserve toute la logique business de send_chat_message)."""
    block = ROUTES.split('@router.post("/chat/stream")')[1]
    assert "has_attachments" in block
    assert "is_offline" in block
    assert "fallback_gen" in block


def test_chat_stream_persists_to_db():
    """Le streaming sauvegarde la réponse IA en DB chat_messages avec le journal agent."""
    block = ROUTES.split('@router.post("/chat/stream")')[1]
    assert "db.chat_messages.insert_one" in block
    assert '"role": "assistant"' in block
    assert '"agent_events"' in block


def test_emergent_integrations_version():
    """requirements.txt épingle emergentintegrations >= 0.2.0 (supporte stream_message)."""
    req = (ROOT / "backend" / "requirements.txt").read_text()
    assert "emergentintegrations==0.2.0" in req or "emergentintegrations>=0.2.0" in req
