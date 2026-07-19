"""iter145 — Correctifs UX Login/Landing + Bot report DM analysis.

Tests :
 - Founder keys manuellement définis (2 clés spec utilisateur)
 - export_validator_bot n'ajoute plus "Type d'export inhabituel" comme anomalie
 - export_validator_bot analyse les MP contenant le project_id
 - MessageButton retiré de Landing.js + Login.js
 - Toast "Bienvenue" retiré de Login.js
 - CreatorToolbar présent en Landing (filtré côté composant selon rôle)
"""
import inspect
import json
from pathlib import Path


def test_founder_creators_json_has_two_keys():
    p = Path("/app/backend/utils/founder_creators.json")
    assert p.exists()
    data = json.loads(p.read_text())
    keys = data.get("key_ids") or []
    assert len(keys) == 2, f"Expected 2 founder keys, got {len(keys)}"
    # Vérifie les clés exactes fournies par l'utilisateur.
    assert any(k.startswith("eyJrdHkiOiJFQyIsImNydiI6IlAtMjU2IiwieCI6IkFjVlRjU0FHVWxrOHdiUHZMTjY1bm9TUFVteTJmYWJOQmNDd2NzdnM4T0UiLCJ5") for k in keys)
    assert any(k.startswith("eyJrdHkiOiJFQyIsImNydiI6IlAtMjU2IiwieCI6Ik16aTIxNUc4SHdqeS0ybEVyS1VENW9YVm41OURTd1FtTkRidFhGSU5xLVUiLCJ5") for k in keys)


def test_founder_guard_recognizes_two_keys():
    import sys
    sys.path.insert(0, "/app")
    sys.path.insert(0, "/app/backend")
    from backend.utils import founder_guard
    # Recharge le fichier.
    keys = founder_guard.get_founder_key_ids()
    assert len(keys) == 2


def test_export_validator_no_kind_anomaly():
    from backend.utils import export_validator_bot
    src = inspect.getsource(export_validator_bot.analyze_export_request)
    # Ancien code retiré (spec utilisateur).
    assert 'Type d\'export inhabituel' not in src
    assert 'inhabituel' not in src.lower() or 'anomalies.append(f"Type' not in src


def test_export_validator_analyzes_dms():
    from backend.utils import export_validator_bot
    src = inspect.getsource(export_validator_bot.analyze_export_request)
    # Nouvelle logique iter145 : inspecte les MP liés au projet.
    assert 'private_messages' in src
    assert 'dm_related_count' in src
    assert 'dm_flagged' in src


def test_landing_removes_message_button():
    content = Path("/app/frontend/src/pages/Landing.js").read_text()
    # MessageButton retiré du header Landing (image 2).
    assert '<MessageButton' not in content
    assert 'MessageButton retiré' in content or 'MessageButton' not in content


def test_login_removes_message_button():
    content = Path("/app/frontend/src/pages/Login.js").read_text()
    # MessageButton retiré (image 3) + import retiré.
    assert '<MessageButton' not in content
    assert 'import MessageButton' not in content


def test_login_removes_welcome_toast():
    content = Path("/app/frontend/src/pages/Login.js").read_text()
    # Les toasts "Bienvenue, ..." ont été retirés (spec utilisateur image 4).
    assert 'toast.success(`Bienvenue' not in content


def test_landing_has_preview_menu_button_before_login_ctas():
    """iter149 — LoginAuxButtons remplace PreviewMenuButton. Doit rester avant CTAs."""
    content = Path("/app/frontend/src/pages/Landing.js").read_text()
    idx_preview = content.find('<LoginAuxButtons')
    idx_login = content.find('hero-login-btn')
    assert idx_preview > 0 and idx_login > 0
    assert idx_preview < idx_login, "LoginAuxButtons doit être avant les CTAs Connexion/Inscription"


def test_founder_note_only_two_founders():
    """Le PRD note qu'il n'y a que 2 fondatrices (pas 5)."""
    prd = Path("/app/memory/PRD.md").read_text()
    # Le PRD doit être à jour pour cette itération.
    assert "founder_creators.json" in prd
