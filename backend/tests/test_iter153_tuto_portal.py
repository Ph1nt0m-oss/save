"""iter153 — Portal tutoriel + décalage vertical center (spec « mets le
tuto par-dessus la barre latérale et baisse-le légèrement »).
"""
from pathlib import Path


TUT = Path("/app/frontend/src/components/InteractiveTutorial.jsx").read_text()


def test_tutorial_mounts_via_portal_to_body():
    """Le tutoriel utilise createPortal → document.body pour échapper
    aux stacking contexts parents (navbar sticky, motion.div…)."""
    assert "import { createPortal }" in TUT or "createPortal" in TUT
    assert "createPortal(tree, document.body)" in TUT


def test_tutorial_overlay_uses_top_z_index():
    """z-[9999] garantit que le tutoriel passe au-dessus de TOUT."""
    assert 'z-[9999]' in TUT


def test_center_placement_offset_down_to_reveal_target():
    """Spec : baisser la bulle en center-mode pour laisser voir les
    boutons cibles situés en haut (navbar/barre latérale)."""
    # Le clamp inclut +80 pour center.
    assert 'vh / 2 - bubbleH / 2 + 80' in TUT


def test_highlight_is_non_interactive():
    """Le halo de surlignage ne doit pas bloquer les clics."""
    # Le highlight est pointer-events-none (n'intercepte pas les clics).
    idx = TUT.find('data-testid={`tuto-highlight-${scope}`}')
    assert idx > 0
    tail = TUT[idx: idx + 300]
    assert 'pointer-events-none' in tail
