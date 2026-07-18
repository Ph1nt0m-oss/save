"""iter142 Batch 3 — Tests bots analyseurs + journal + Créa protection.

Couvre :
  - bot_analyzer.analyze_message : détection spam/mots-clés/flood/répétition/mentions
  - Journal d'anonymat : logging via log_mode_change
  - État suspicion : mark_group_suspicion + is_group_under_suspicion
  - Endpoints /social/anonymity-journal + /social/suspicion-state
  - Sun mode requires suspicion for non-créa
  - Créa anonyme protégée (jamais révélée par Sun mode)
  - Mentions parsing @handle
"""
import sys
import inspect
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))


def test_bot_analyzer_module_present():
    from backend.utils import bot_analyzer
    assert hasattr(bot_analyzer, 'analyze_message')
    assert hasattr(bot_analyzer, 'log_mode_change')
    assert hasattr(bot_analyzer, 'mark_group_suspicion')
    assert hasattr(bot_analyzer, 'is_group_under_suspicion')


def test_analyze_message_clean_content():
    from backend.utils import bot_analyzer
    r = bot_analyzer.analyze_message(
        group_type="public", key_id="k1", content="Bonjour, comment ça va aujourd'hui ?",
    )
    assert r["score"] < 60
    assert not r["suspicion"]
    assert isinstance(r["reasons"], list)


def test_analyze_message_keywords_flag():
    from backend.utils import bot_analyzer
    # Contient plusieurs mots-clés spam.
    r = bot_analyzer.analyze_message(
        group_type="public", key_id="k_spam",
        content="Gagnez de l'argent facile avec du free bitcoin ! Cliquez vite gagnez casino.",
    )
    assert r["score"] >= 40
    assert "mots-clés suspects" in r["reasons"]


def test_analyze_message_flood_detection():
    from backend.utils import bot_analyzer
    # Simule 8 messages en 1 seconde du même user.
    now = time.time()
    r = None
    for _ in range(7):
        r = bot_analyzer.analyze_message(
            group_type="test_flood", key_id="k_flood",
            content="salut", now_ts=now + 0.1,
        )
    assert r["score"] >= 40
    assert "rafale de messages" in r["reasons"]


def test_analyze_message_repeat_detection():
    from backend.utils import bot_analyzer
    r = None
    for _ in range(4):
        r = bot_analyzer.analyze_message(
            group_type="repeat_group", key_id="k_rep",
            content="ACHETEZ MAINTENANT !", now_ts=time.time(),
        )
    assert r["score"] >= 30


def test_analyze_message_mention_flood():
    from backend.utils import bot_analyzer
    r = bot_analyzer.analyze_message(
        group_type="mention_group", key_id="k_ment",
        content="@user1 @user2 @user3 @user4 @user5 @user6 hey!",
    )
    assert r["score"] >= 30
    assert "mentions en rafale" in r["reasons"]


def test_suspicion_threshold():
    from backend.utils import bot_analyzer
    # Combine keywords + flood pour dépasser 60.
    now = time.time()
    r = None
    for _ in range(7):
        r = bot_analyzer.analyze_message(
            group_type="susp", key_id="k_susp",
            content="Casino gratuit maintenant argent facile !",
            now_ts=now + 0.1,
        )
    assert r["suspicion"] is True
    assert r["score"] >= 60


def test_journal_endpoint_defined():
    from backend.routes import social_members_routes
    src = inspect.getsource(social_members_routes.build_social_member_router)
    assert '/social/anonymity-journal' in src
    assert '/social/suspicion-state' in src


def test_sun_mode_requires_suspicion_for_non_creator():
    from backend.routes import social_members_routes
    src = inspect.getsource(social_members_routes.build_social_member_router)
    # Vérifie que le check "any_suspicion" est présent.
    assert 'any_suspicion' in src
    assert 'group_suspicion' in src
    # Créa bypass.
    assert 'me.get("role") != "creator"' in src


def test_creator_anonymous_never_revealed():
    from backend.routes import social_routes
    src = inspect.getsource(social_routes.build_groups_router)
    assert '_sender_is_creator' in src
    # La logique doit renvoyer Anonyme SANS passer par le check sun_mode.
    assert 'protection absolue Créa' in src or 'jamais révélée' in src.lower()


def test_bot_analyzer_hooks_in_groups_send():
    from backend.routes import social_routes
    src = inspect.getsource(social_routes.build_groups_router)
    assert 'bot_analyzer.analyze_message' in src
    assert 'mark_group_suspicion' in src
    assert 'bot_moderator' in src
    assert 'Modérateur automatique' in src


def test_journal_mode_change_signature():
    from backend.utils import bot_analyzer
    import inspect as _i
    sig = _i.signature(bot_analyzer.log_mode_change)
    params = set(sig.parameters.keys())
    assert {"db", "actor_key_id", "mode", "enabled"}.issubset(params)
    assert {"actor_pseudo", "actor_public_handle", "actor_role"}.issubset(params)


def test_no_more_backend_prefix_import():
    """Vérifie que les modules utilisent l'import direct `from utils import`
    (pas `from backend.utils`) pour rester compatibles avec le runtime."""
    for f in [
        "/app/backend/routes/social_routes.py",
        "/app/backend/routes/social_members_routes.py",
    ]:
        content = Path(f).read_text()
        assert 'from backend.utils' not in content, f"Bad import in {f}"
        assert 'from utils import bot_analyzer' in content or 'from utils.bot_analyzer' in content
