"""iter147 — Sprint 2 remaining : LLM layer in bot_analyzer, journal
2-tabs (bot alerts + staff decisions), @mentions anonymous-safe.
"""
import asyncio
import inspect
import os
import sys
from pathlib import Path
from unittest.mock import patch, AsyncMock

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def test_bot_analyzer_still_exports_deterministic_layer():
    """La couche 1 déterministe reste PRIMAIRE et intacte."""
    from utils import bot_analyzer
    assert hasattr(bot_analyzer, 'analyze_message'), "analyze_message doit rester exporté"
    # Vérifie l'analyse locale sur un flood keyword.
    r = bot_analyzer.analyze_message(
        group_type='public', key_id='k1',
        content='casino gagnez argent facile cliquez vite gratuit maintenant',
    )
    assert r['layer'] == 'local'
    assert r['score'] > 0
    assert 'mots-clés suspects' in r['reasons']


def test_bot_analyzer_has_combined_layer():
    """iter147 — analyze_message_combined ajoute la couche LLM séparément."""
    from utils import bot_analyzer
    assert hasattr(bot_analyzer, 'analyze_message_combined')
    # analyze_message_combined est async
    assert asyncio.iscoroutinefunction(bot_analyzer.analyze_message_combined)


def test_bot_analyzer_combined_llm_never_replaces_local():
    """CRITIQUE : la couche 1 reste toujours calculée, même si LLM échoue."""
    from utils import bot_analyzer

    async def _run():
        # Force LLM disabled → uniquement layer_local présent.
        os.environ['CODEFORGE_LLM_MOD_DISABLED'] = '1'
        try:
            r = await bot_analyzer.analyze_message_combined(
                group_type='public', key_id='k2',
                content='casino gagnez argent facile cliquez vite',
            )
            assert r['layer_local'] is not None
            assert r['layer_local']['layer'] == 'local'
            assert r['layer_local']['score'] > 0, "Couche déterministe TOUJOURS calculée"
            # LLM disabled → None
            assert r['layer_llm'] is None
            # Combined = max => local score
            assert r['combined_score'] == r['layer_local']['score']
        finally:
            os.environ.pop('CODEFORGE_LLM_MOD_DISABLED', None)

    asyncio.run(_run())


def test_bot_analyzer_llm_error_does_not_break_local():
    """Si le LLM lève une exception, la couche 1 reste valide."""
    from utils import bot_analyzer

    async def _run():
        with patch.object(bot_analyzer, '_llm_analyze_subtle',
                          new=AsyncMock(return_value={'layer': 'llm', 'error': 'boom'})):
            r = await bot_analyzer.analyze_message_combined(
                group_type='public', key_id='k3',
                content='connard va crever',
            )
            # Local détecte quand même les mots-clés.
            assert r['layer_local']['score'] > 0
            # LLM en erreur = layer_llm présent mais avec 'error'.
            assert r['layer_llm']['error'] == 'boom'
            # Score combiné = local (llm score absent → 0).
            assert r['combined_score'] == r['layer_local']['score']

    asyncio.run(_run())


def test_bot_analyzer_llm_prompt_targets_subtle_harassment():
    """Le prompt LLM doit cibler explicitement le harcèlement SUBTIL."""
    from utils import bot_analyzer
    p = bot_analyzer._LLM_SYSTEM_PROMPT.lower()
    assert 'harc' in p or 'subtil' in p
    assert 'is_suspicious' in p
    assert 'json' in p


def test_alert_doc_stores_both_layers_separately():
    """Le message d'alerte inséré par groups/send doit contenir
    layer_local + layer_llm distincts."""
    content = (BACKEND / 'routes' / 'social_routes.py').read_text()
    assert '"layer_local": analysis.get("layer_local")' in content
    assert '"layer_llm": analysis.get("layer_llm")' in content
    assert 'analyze_message_combined' in content


def test_mentions_router_exists_and_registered():
    p = BACKEND / 'routes' / 'mentions_routes.py'
    assert p.exists()
    txt = p.read_text()
    assert 'build_mentions_router' in txt
    assert '/mentions/list' in txt
    assert '/mentions/unread-count' in txt
    assert '/mentions/mark-read' in txt
    assert '/mentions/mark-all-read' in txt
    # Server registers it.
    server = (BACKEND / 'server.py').read_text()
    assert 'build_mentions_router' in server


def test_mentions_endpoints_are_signed():
    """Toutes les routes /mentions/* doivent requérir la preuve ECDSA
    (verify_signed)."""
    from routes import mentions_routes
    src = inspect.getsource(mentions_routes)
    # 4 endpoints -> 4 appels verify_signed.
    assert src.count('await verify_signed(') >= 4


def test_mention_notif_hides_author_when_anonymous():
    """Vérifie le contrat de /groups/send : notif insérée avec
    author_hidden=True et sans from_key_id/pseudo/handle quand l'auteur
    est anonyme."""
    content = (BACKEND / 'routes' / 'social_routes.py').read_text()
    # La branche anonyme n'ajoute pas from_key_id etc.
    idx = content.find('"author_hidden": sender_is_anonymous')
    assert idx > 0
    # Après cette insertion, la propagation des champs auteur est
    # conditionnée par `if not sender_is_anonymous:`.
    guard = content.find('if not sender_is_anonymous', idx)
    assert 0 < guard < idx + 3000
    # Champs d'identité stockés SEULEMENT dans ce bloc conditionnel.
    tail = content[guard: guard + 800]
    assert 'from_pseudo' in tail
    assert 'from_public_handle' in tail
    assert 'from_key_id' in tail


def test_mentions_router_sanitize_never_leaks_hidden_author():
    """`_sanitize` doit ne PAS exposer from_pseudo/handle/role si
    author_hidden=True."""
    from routes.mentions_routes import _sanitize
    row = {
        'notification_id': 'x', 'type': 'mention', 'group_type': 'public',
        'message_id': 'gm', 'ts': 't', 'read': False, 'author_hidden': True,
        'from_pseudo': 'LEAK', 'from_public_handle': 'LEAKHANDLE',
        'from_role': 'creator', 'from_key_id': 'kx',
    }
    out = _sanitize(row)
    assert out['author_hidden'] is True
    assert 'from_pseudo' not in out
    assert 'from_public_handle' not in out
    assert 'from_role' not in out
    assert 'from_key_id' not in out
    # Cas non-caché : les champs sont bien exposés.
    row['author_hidden'] = False
    out2 = _sanitize(row)
    assert out2['from_pseudo'] == 'LEAK'
    assert out2['from_public_handle'] == 'LEAKHANDLE'


def test_journal_panel_has_three_tabs():
    """Le composant AnonymityJournalPanel expose maintenant 3 onglets :
    bot / staff / anon."""
    p = Path('/app/frontend/src/components/AnonymityJournalPanel.jsx').read_text()
    # Le testid est construit dynamiquement : `journal-tab-${k}`.
    assert 'journal-tab-${k}' in p
    # Les 3 clés existent dans les TabButton k="bot" etc.
    assert 'k="bot"' in p and 'k="staff"' in p and 'k="anon"' in p
    # Affiche bien les 2 couches d'alerte bot.
    assert 'layer-local' in p and 'layer-llm' in p
    # Repère la Créa : hotspot des refus répétés.
    assert 'journal-refusal-hotspots' in p


def test_journal_panel_uses_moderation_endpoints():
    p = Path('/app/frontend/src/components/AnonymityJournalPanel.jsx').read_text()
    assert '/moderation/alerts/list' in p
    assert '/moderation/decisions/list' in p


def test_mention_notifier_component_exists_and_mounted():
    """iter150 — MentionNotifier remplacé par MentionsBell dans le header."""
    p = Path('/app/frontend/src/components/MentionsBell.jsx')
    assert p.exists()
    src = p.read_text()
    assert 'mentions-bell-btn' in src
    assert 'mentions-panel-close' in src
    assert 'mention-item-' in src
    # Anonymous-safe: label neutre si auteur caché.
    assert 'Quelqu' in src
    # Discord-style : badge rouge + navigate to conversation.
    assert 'bg-red-500' in src
    assert 'codeforge:open-conversation' in src
    # Monté dans le Dashboard (header, plus flottant).
    dash = Path('/app/frontend/src/pages/Dashboard.js').read_text()
    assert 'import MentionsBell' in dash
    assert '<MentionsBell' in dash
