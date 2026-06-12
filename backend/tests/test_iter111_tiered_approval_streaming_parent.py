"""iter111 — Tests pour : Tiered Approval, Guest viewSpec, parent_chat_id,
SSE token-par-token + ajustements de spacings UI."""
from pathlib import Path
import requests, os

API = (
    os.environ.get("REACT_APP_BACKEND_URL")
    or "https://no-code-builder-25.preview.emergentagent.com"
) + "/api"

ROOT = Path(__file__).resolve().parents[2]
SERVER = (ROOT / "backend" / "server.py").read_text()
DASH = (ROOT / "frontend" / "src" / "pages" / "Dashboard.js").read_text()
SMB = (ROOT / "frontend" / "src" / "components" / "SiteModeBadge.jsx").read_text()
DM = (ROOT / "frontend" / "src" / "components" / "DeviceManager.jsx").read_text()
CHAT = (ROOT / "frontend" / "src" / "pages" / "Chat.js").read_text()
WIZ = (ROOT / "frontend" / "src" / "pages" / "GuidedWizard.js").read_text()


# ---------------------------------------------------------------------- UI spacings


def test_dashboard_gap_15cm():
    """Header dashboard a un gap serré (iter112 lg:gap-6) avec resserrement après le swap iter110."""
    assert ("lg:gap-[15cm]" in DASH) or ("lg:gap-6" in DASH)


def test_site_mode_dropdown_right_10cm():
    """Dropdown 'Audiences actives' positionné 10cm depuis le bord droit."""
    assert "right-[10cm]" in SMB


# ---------------------------------------------------------------------- Tiered Approval


def test_devices_approve_accepts_as_role():
    """Le payload DeviceApproveIn doit avoir le champ as_role."""
    assert "class DeviceApproveIn" in SERVER
    assert "as_role" in SERVER


def test_devices_approve_hierarchy_logic():
    """La hiérarchie strict est implémentée côté backend."""
    # Modo → user uniquement ; Admin → user/modo ; Créa → tout.
    assert 'allowed = {"user", "modo", "admin"}' in SERVER  # créa
    assert 'allowed = {"user", "modo"}' in SERVER  # admin
    assert 'allowed = {"user"}' in SERVER  # modo


def test_devices_approve_endpoint_alive():
    r = requests.post(f"{API}/devices/approve", json={
        "key_id": "k", "nonce": "n", "signature": "s",
        "target_key_id": "t", "as_role": "user",
    }, timeout=10)
    assert r.status_code in (403, 422)  # 403 sig invalide attendu


def test_device_manager_dropdown_ui():
    """Frontend : DeviceManager a le dropdown 'Approuver comme…'."""
    assert "Approuver comme" in DM
    assert "approve-as-${r}-${d.key_id}" in DM
    assert "approveAs(" in DM
    assert "allowedApprovalRoles" in DM


# ---------------------------------------------------------------------- ViewSpec guest


def test_view_spec_includes_guest():
    r = requests.get(f"{API}/views/spec", timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert "guest" in data
    g = data["guest"]
    assert g["chats_visible"] == ["public"]
    assert g["see_friends"] is False
    assert g["see_programming"] is False
    assert g["can_send_messages"] is False
    assert g["can_create_projects"] is False


# ---------------------------------------------------------------------- parent_chat_id


def test_project_model_has_parent_chat_id():
    """Le modèle Project doit exposer parent_chat_id."""
    assert "parent_chat_id" in SERVER
    # Au moins dans le modèle Project
    project_block = SERVER.split("class Project(BaseModel):")[1].split("class ProjectCreate")[0]
    assert "parent_chat_id" in project_block


def test_generate_complete_app_persists_parent_chat_id():
    """_ai_generate_complete_app_impl extrait parent_chat_id de data."""
    impl_block = SERVER.split("async def _ai_generate_complete_app_impl")[1][:30000]
    assert "parent_chat_id" in impl_block
    assert "data.get('parent_chat_id'" in impl_block


def test_guided_wizard_sends_parent_chat_id():
    """GuidedWizard envoie parent_chat_id depuis location.state."""
    assert "parent_chat_id: parentChatId" in WIZ
    assert "location.state?.parent_chat_id" in WIZ


# ---------------------------------------------------------------------- SSE Streaming


def test_chat_stream_endpoint_alive():
    r = requests.post(f"{API}/chat/stream", json={
        "message": "test", "mode": "online", "language": "fr",
    }, timeout=10)
    # 401 sans auth ou 200 si quelqu'un est loggé (improbable ici).
    assert r.status_code in (401, 403, 200)


def test_chat_stream_input_accepts_model_attachments():
    """ChatStreamIn doit accepter model + attachments (iter111)."""
    block = SERVER.split("class ChatStreamIn(BaseModel):")[1].split("@api_router")[0]
    assert "model:" in block
    assert "attachments:" in block


def test_chat_stream_emits_done_with_project_id():
    """L'event 'done' SSE inclut project_id pour adoption frontend."""
    block = SERVER.split("class ChatStreamIn(BaseModel):")[1].split("# Include the router")[0]
    assert '"project_id": auto_pid' in block


def test_chat_uses_streaming_endpoint():
    """Chat.js utilise désormais /chat/stream avec reader.read() pour le SSE."""
    assert "/chat/stream" in CHAT
    assert "reader.read()" in CHAT
    assert "_streaming_id" in CHAT
    assert "evt.delta" in CHAT


# ---------------------------------------------------------------------- Regression : compile


def test_server_syntax_ok():
    """Compile-check : ast.parse réussit sur server.py."""
    import ast
    ast.parse(SERVER)
