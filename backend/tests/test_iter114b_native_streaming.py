"""iter114b — Test du vrai streaming natif via emergentintegrations stream_message."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVER = (ROOT / "backend" / "server.py").read_text()


def test_chat_stream_uses_native_stream_message():
    """L'endpoint /chat/stream utilise désormais stream_message() (vrai SSE
    token-par-token) au lieu de re-chunker la réponse complète."""
    block = SERVER.split("@api_router.post(\"/chat/stream\")")[1].split("# Include the router in the main app")[0]
    # Native path emits real tokens via stream_message + TextDelta
    assert "stream_message" in block
    assert "TextDelta" in block
    assert "StreamDone" in block


def test_chat_stream_has_fallback_for_attachments():
    """Le mode avec attachments ou offline retombe sur le pseudo-streaming
    (préserve toute la logique business de send_chat_message)."""
    block = SERVER.split("@api_router.post(\"/chat/stream\")")[1].split("# Include the router in the main app")[0]
    assert "has_attachments" in block
    assert "is_offline" in block
    assert "fallback_gen" in block


def test_chat_stream_persists_to_db():
    """Le streaming natif sauvegarde la réponse IA en DB chat_messages."""
    block = SERVER.split("@api_router.post(\"/chat/stream\")")[1].split("# Include the router in the main app")[0]
    assert "db.chat_messages.insert_one" in block
    assert 'role": "assistant"' in block or "'role': 'assistant'" in block


def test_emergent_integrations_version():
    """requirements.txt épingle emergentintegrations >= 0.2.0 (supporte stream_message)."""
    req = (ROOT / "backend" / "requirements.txt").read_text()
    assert "emergentintegrations==0.2.0" in req or "emergentintegrations>=0.2.0" in req
