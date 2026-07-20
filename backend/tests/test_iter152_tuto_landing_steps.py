"""iter152 — Tutoriel Landing steps 4/5/6 : fallback multi-selectors +
auto-center dans la zone navbar + bubble z-[110] opaque.
"""
from pathlib import Path


TUT = Path("/app/frontend/src/components/InteractiveTutorial.jsx").read_text()


def test_step_language_supports_landing_via_common_selector():
    """Le testid `language-toggle` existe déjà sur Landing (LanguageToggle
    component), donc la cible est atteinte. Le placement auto-top gère
    le chevauchement navbar."""
    assert "id: 'auth-language'" in TUT
    # Placement auto-top pour cette étape (centre auto si dans navbar).
    idx = TUT.find("id: 'auth-language'")
    tail = TUT[idx: idx + 400]
    assert "placement: 'auto-top'" in tail


def test_step_legal_has_landing_fallback():
    """Step 5 (Comment ça marche) doit accepter link-how-it-works OU
    footer-how-it-works (fallback Landing)."""
    idx = TUT.find("id: 'auth-legal'")
    assert idx > 0
    tail = TUT[idx: idx + 500]
    assert 'link-how-it-works' in tail
    assert 'footer-how-it-works' in tail
    assert "placement: 'auto-top'" in tail


def test_step_theft_has_landing_fallback():
    """Step 6 (Vol d'appareil) doit accepter declare-theft-link OU
    theft-labelled-btn (fallback Landing via TheftButton)."""
    idx = TUT.find("id: 'auth-theft'")
    assert idx > 0
    tail = TUT[idx: idx + 500]
    assert 'declare-theft-link' in tail
    assert 'theft-labelled-btn' in tail
    assert "placement: 'auto-top'" in tail


def test_auto_top_placement_prioritizes_top_first_iter155():
    """iter155 — Retour au placement d'origine : top primaire, fallback
    auto (bottom/right/left/center) SI top ne rentre pas. La bulle reste
    NEAR la cible."""
    assert "candidates = ['top', 'bottom', 'right', 'left', 'center']" in TUT


def test_bubble_z_index_above_navbar_chips():
    """iter153 — Portal + z-[9999] pour dépasser TOUT stacking context."""
    assert 'z-[9999]' in TUT, 'overlay doit être z-[9999]'
    # Portal vers document.body pour échapper aux stacking contexts.
    assert 'createPortal' in TUT
    assert 'document.body' in TUT


def test_bubble_has_solid_background():
    """La bulle a un background opaque (#050505) et une ombre forte."""
    assert 'bg-[#050505]' in TUT
    assert 'shadow-[0_20px_60px_rgba(0,0,0,0.8)]' in TUT


def test_bubble_max_width_prevents_overflow():
    """max-w-[calc(100vw-24px)] pour tenir sur mobile."""
    assert 'max-w-[calc(100vw-24px)]' in TUT
