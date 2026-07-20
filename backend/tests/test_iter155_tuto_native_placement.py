"""iter155 — Restaurer placement d'origine du tuto (top primaire) +
décalage CreatorToolbar vers la gauche sur Landing.
"""
from pathlib import Path


TUT = Path("/app/frontend/src/components/InteractiveTutorial.jsx").read_text()
LANDING = Path("/app/frontend/src/pages/Landing.js").read_text()


def test_tutorial_placement_top_first_native_flow():
    """Le placement d'origine « top primaire, fallback auto » est restauré."""
    assert "candidates = ['top', 'bottom', 'right', 'left', 'center']" in TUT


def test_no_more_hardcoded_navbar_threshold():
    """Plus de règle fixe `rect.top < 120` — l'algorithme est purement
    basé sur la mesure d'overflow (spec iter155)."""
    idx_fn = TUT.find('function computeBubblePos(')
    idx_next_fn = TUT.find('function highlightRect(')
    body = TUT[idx_fn: idx_next_fn]
    assert 'rect.top < 120' not in body


def test_tutorial_bubble_stays_topmost():
    """Portal + z-[9999] : le tuto est TOUJOURS au premier plan."""
    assert 'createPortal(tree, document.body)' in TUT
    assert 'z-[9999]' in TUT


def test_landing_creator_toolbar_shifted_left():
    """iter155 — La barre latérale du haut (CreatorToolbar + Français) est
    décalée vers la gauche via `mr-6 sm:mr-12 md:mr-20` sur le container."""
    assert 'mr-6 sm:mr-12 md:mr-20' in LANDING
    # Le décalage s'applique bien au container qui contient CreatorToolbar.
    idx = LANDING.find('mr-6 sm:mr-12 md:mr-20')
    tail = LANDING[idx: idx + 400]
    assert '<CreatorToolbar' in tail
