"""
iter102 — Tests pour les nouveaux endpoints Community Bots Test + Knowledge Base
+ auto GitHub push helper.

NOTE : on évite FastAPI TestClient ici car il y a un conflit connu entre Motor
(client MongoDB async) et la boucle asyncio de TestClient qui se ferme entre
tests. À la place : vérification de la table de routes + curl externe.
"""
import os

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_codeforge_iter102")

from server import app  # noqa: E402


def test_community_bots_test_endpoint_registered():
    routes = {r.path for r in app.routes if hasattr(r, "path")}
    assert "/api/community-bots/test" in routes


def test_community_bots_kb_endpoints_registered():
    routes = {r.path for r in app.routes if hasattr(r, "path")}
    assert "/api/community-bots/knowledge/upsert" in routes
    assert "/api/community-bots/knowledge/list" in routes
    assert "/api/community-bots/knowledge/delete" in routes


def test_push_helper_imported_and_callable():
    """_push_project_to_github helper must be importable + callable."""
    from server import _push_project_to_github
    assert callable(_push_project_to_github)


def test_push_helper_signature_supports_raise_on_missing():
    """Helper must accept raise_on_missing kwarg for fire-and-forget mode."""
    import inspect
    from server import _push_project_to_github
    sig = inspect.signature(_push_project_to_github)
    assert "raise_on_missing" in sig.parameters
    assert sig.parameters["raise_on_missing"].default is False


def test_auto_push_hook_present_in_generate_app():
    """Le hook auto-push GitHub à la création doit être présent dans
    _ai_generate_complete_app_impl (string match dans le source)."""
    from pathlib import Path
    src = Path("/app/backend/server.py").read_text(encoding="utf-8")
    assert "iter102 — Auto-push GitHub silencieux à la création" in src
    assert "_push_project_to_github(project_id, user_id, raise_on_missing=False)" in src


def test_enhancement_suggestions_widget_unused_in_chat():
    """Le widget de suggestions doit être retiré de Chat.js comme demandé."""
    from pathlib import Path
    chat = Path("/app/frontend/src/pages/Chat.js").read_text(encoding="utf-8")
    # Le composant n'est plus importé et le state plus déclaré
    assert "EnhancementSuggestionsWidget" not in chat, \
        "EnhancementSuggestionsWidget devrait être retiré de Chat.js"
    assert "enhancementSuggestions" not in chat, \
        "Le state enhancementSuggestions devrait être retiré"


def test_bots_admin_panel_has_test_and_kb_buttons():
    """Le panel admin doit exposer les boutons Test + Knowledge Base."""
    from pathlib import Path
    panel = Path("/app/frontend/src/components/BotsAdminPanel.jsx").read_text(encoding="utf-8")
    assert "bot-test-" in panel
    assert "bot-kb-" in panel
    assert "/community-bots/test" in panel
    assert "/community-bots/knowledge" in panel
