"""iter154 — Moteur de placement dynamique du tutoriel :
- Mesure la hauteur RÉELLE de la bulle (ResizeObserver + useLayoutEffect)
- Teste chaque candidat de placement dans l'ordre (top/bottom/left/right/center)
- Choisit le premier qui rentre ENTIÈREMENT dans le viewport
- Sinon celui qui déborde le moins (clampé aux marges)
- Recalcul à chaque changement d'étape + resize
"""
from pathlib import Path


TUT = Path("/app/frontend/src/components/InteractiveTutorial.jsx").read_text()


def test_bubble_dims_measured_at_runtime():
    """La bulle est mesurée via ref + ResizeObserver — pas de valeur fixe."""
    assert 'bubbleRef' in TUT
    assert 'useLayoutEffect' in TUT
    assert 'ResizeObserver' in TUT
    # Le state dims est initialisé mais SERA remplacé par la vraie mesure.
    assert 'setBubbleDims' in TUT


def test_computeBubblePos_accepts_real_dimensions():
    """computeBubblePos(target, placement, bubbleW, bubbleH) — pas d'H fixe."""
    assert 'function computeBubblePos(target, placement, bubbleW, bubbleH)' in TUT
    # Aucun bubbleH = 240 hardcodé dans le corps de la fonction.
    idx_fn = TUT.find('function computeBubblePos(')
    idx_next_fn = TUT.find('function highlightRect(')
    body = TUT[idx_fn: idx_next_fn]
    assert 'bubbleH = 240' not in body, 'La valeur hardcodée H=240 doit être supprimée'


def test_placement_engine_tests_multiple_candidates():
    """L'algorithme teste plusieurs candidats et choisit celui qui rentre."""
    assert 'tryPlacement' in TUT
    # Ordre de candidats dépend du placement demandé.
    assert "'auto-top'" in TUT or "'auto'" in TUT
    assert 'candidates = [' in TUT
    # Test « fits entièrement ? » (overflow === 0)
    assert 'overflow === 0' in TUT
    # Fallback : celui qui déborde le moins.
    assert 'r.overflow < best.overflow' in TUT


def test_placement_engine_clamps_final_position():
    """Le résultat est TOUJOURS clampé aux limites du viewport (jamais hors écran)."""
    idx_fn = TUT.find('function computeBubblePos(')
    idx_next_fn = TUT.find('function highlightRect(')
    body = TUT[idx_fn: idx_next_fn]
    assert 'const clamp' in body
    # Le clamp final utilise margin & viewport dims.
    assert 'clTop = clamp(top, margin' in body
    assert 'clLeft = clamp(left, margin' in body


def test_placement_recomputes_on_step_change_and_resize():
    """Le recalcul dépend de stepIdx (via current) + tick (via resize event)."""
    # Le useMemo dépend de current + tick + bubbleDims.
    assert '[target, current, tick, bubbleDims.w, bubbleDims.h]' in TUT
    # Écoute resize + scroll pour maintenir le placement.
    assert "window.addEventListener('resize', onResize)" in TUT
    assert "window.addEventListener('scroll', onResize, true)" in TUT


def test_prefer_top_and_auto_fallback_if_no_space():
    """iter155 — Placement top primaire ; l'algorithme tryPlacement teste
    chaque candidat (dans l'ordre top→bottom→right→left→center) et prend
    le premier qui rentre entièrement. Le fallback est PURE overflow-based,
    aucune règle fixe rect.top < 120."""
    idx_fn = TUT.find('function computeBubblePos(')
    idx_next_fn = TUT.find('function highlightRect(')
    body = TUT[idx_fn: idx_next_fn]
    assert "candidates = ['top', 'bottom', 'right', 'left', 'center']" in body
    # Le seuil fixe rect.top < 120 est supprimé (retour comportement natif).
    assert 'rect.top < 120' not in body
