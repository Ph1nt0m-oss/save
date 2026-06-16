"""iter128.5 — Tests pour : bannière simulation avec pseudo cible + persona créa.

Vérifie :
  - `setStoredViewMode` accepte un 2e arg `{visitTargetPseudo}` qui est
    stocké dans localStorage et exposé via `readVisitTarget()`.
  - `ViewSimulationBanner` affiche "Tu vois actuellement le compte de
    {pseudo}" si `visitTarget` non-null.
  - `Dashboard.onVisitAccount` passe le pseudo cible.
  - `CreatorChatPersonaBar` existe, exporte `useCreatorChatPersona` et
    rend persona/IA-reply/visible togglés selon le state.
  - `MessageSendIn` accepte `persona_override` ; `/messages/send`
    stocke les méta-données persona uniquement pour la créa.
"""
from __future__ import annotations
from pathlib import Path

FRONT = Path("/app/frontend/src")
BACK = Path("/app/backend")


def _read(p, base=FRONT):
    return (base / p).read_text(encoding="utf-8")


def test_set_stored_view_mode_supports_visit_target():
    src = _read("hooks/useDeviceIdentity.js")
    assert "VISIT_TARGET_KEY" in src
    assert "visitTargetPseudo" in src
    assert "readVisitTarget" in src


def test_view_simulation_banner_renders_visit_target_pseudo():
    src = _read("components/ViewSimulationBanner.jsx")
    assert "readVisitTarget" in src
    assert "le compte de" in src
    assert "visitTarget" in src


def test_dashboard_passes_target_pseudo_on_visit():
    src = _read("pages/Dashboard.js")
    assert "visitTargetPseudo" in src
    assert "targetPseudo" in src


def test_creator_chat_persona_bar_exists():
    p = FRONT / "components/CreatorChatPersonaBar.jsx"
    assert p.exists()
    src = p.read_text(encoding="utf-8")
    # Hook et composant
    assert "useCreatorChatPersona" in src
    assert "export default function CreatorChatPersonaBar" in src
    # Personas
    assert "id: 'ai'" in src
    assert "id: 'owner'" in src
    assert "id: 'creator'" in src
    # Toggles
    assert "persona-ai-reply-toggle" in src
    assert "persona-visible-toggle" in src
    # Créa physique uniquement
    assert "device.role !== 'creator'" in src


def test_message_send_accepts_persona_override():
    src = _read("routes/messages_routes.py", base=BACK)
    assert "persona_override" in src
    # Le backend valide via la signature créa
    assert "is_creator_sender" in src
    # Métadonnées persistées
    assert '"persona_id"' in src
    assert '"persona_pseudo"' in src
    assert '"persona_avatar"' in src
    assert '"visible_to_target"' in src
    assert '"ai_replies"' in src


def test_persona_overrides_ignored_for_non_creator():
    """Si non-créa envoie persona_override, le code l'ignore."""
    src = _read("routes/messages_routes.py", base=BACK)
    assert "persona = (payload.persona_override or {}) if is_creator_sender else {}" in src
