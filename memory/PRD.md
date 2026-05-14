# CodeForge AI — Product Requirements

## Original problem statement
Plateforme zero-code permettant à des non-développeurs de décrire une application
en langage naturel et d'obtenir le code source (Web/PWA/Desktop). Mode hors-ligne
(Ollama) ou en ligne (Emergent LLMs). Export ZIP + GitHub. UI Glassmorphism.

## Core requirements
- Chat AI ultra-réactif, sélecteur de modèles (silent fallback budget-limit)
- Sandbox Python avec REPL + matplotlib
- i18n 16 langues (RTL Arabic inclus)
- Identité par appareil cryptographique (ECDSA P-256 WebCrypto, non-extractible)
- Modes de site 4-états : `public` / `private` / `creator` / `guest`
- Système de rôles : `creator` / `approved` / `pending` / `revoked`
- Sharing public + Live preview iframe
- Backup GitHub natif (fusionné avec download ZIP)

## CHANGELOG

### 2026-02-14 — Iter 48 (current)
- **Fix CRITIQUE #3** : Approval flow conditionnel sur `site_mode` → en mode `public` ou `guest`, plusieurs appareils peuvent se connecter sur le même email SANS approbation (l'utilisateur ne devait pas être bloqué en public). L'approbation ne se déclenche qu'en `private` ou `creator`.
- **#1 "Annulé" → "Refusé"** dans les badges d'historique (action revoke). Le bouton à côté de chaque ligne devient **"Annuler"** (icône Undo2) au lieu de "Révoquer" (trash) — il appelle le nouvel endpoint `/devices/decisions/undo`.
- **Nouvel endpoint `POST /api/devices/decisions/undo`** (créateur uniquement) : annule une décision en remettant l'appareil en `pending`, avec snapshot complet pour les actions destructives (revoke/disconnect recréent la ligne dans `device_keys` depuis le snapshot stocké sur la décision).
- **`_log_decision`** étendu : snapshot du `public_key_jwk` + label sur les actions revoke/disconnect → permet une vraie restauration.
- **#2 Profile mobile** : `min-h-[100dvh]` + `pb-32` avec `safe-area-inset-bottom` (iOS notch) ; section "Ma clé d'appareil" déplacée tout en bas du tab Info (après "Tes données RGPD") comme demandé. `touch-action: pan-x` sur le code pour que le swipe horizontal ne bloque pas le scroll vertical de la page.
- **Backend testing** : 12/12 pass (iter_48.json), aucun bug critique.

### Iter 47
- 8 corrections : Revoke par ligne, Annulé/Refusé, Clear history, Export TXT, Profile mobile, Send to creator, mask History pour non-créateurs, fix session mobile.

### Iter 46
- "session expired" idempotency, labels d'appareils lisibles, bannière d'attente enrichie, suppression "Appareils enregistrés" sur revoke/disconnect, "Envoyer au créateur" + side-panel historique.

### Iter 45
- WebAuthn "Déclarer un vol", 4-tier site mode, view-mode toggle, cleanup DB initial.

## Backlog (priorisé)

### P1
- **Resend Email Domain Verification** : actuellement en sandbox, magic links envoyés uniquement au dev. Le user doit vérifier un domaine sur resend.com pour libérer l'envoi.
- **Sécuriser le polling `/auth/session-request-status`** : ajouter rate-limit (testing agent l'a noté en mineur)

### P2
- Auto-détection Ollama lorsque mode hors-ligne sélectionné
- Refactor `server.py` (5800 lignes) en sous-routers : `routes/auth_routes.py`, `routes/devices_routes.py`, `routes/projects_routes.py`
- Audit a11y (focus rings, screen-reader labels sur les modals)

### P3
- Stripe subscription pour features premium (export quotas, multi-créateurs)
- Push notifications (web-push API) pour les session_requests / device approvals
- Backup automatique S3-compatible
- Visualiseur de diff entre versions générées

## Test credentials
Voir `/app/memory/test_credentials.md`.

## Architecture rapide
```
/app/backend/
  server.py              # FastAPI, LLM routing, SSE, sessions, WebAuthn (5800 LOC)
  device_auth.py         # ECDSA verify + canonical JWK
  routes/                # PWA + Desktop export sub-routers
/app/frontend/src/
  components/
    CreatorToolbar.jsx           # SiteMode + History + ViewMode toggle
    DeviceManager.jsx            # creator panel
    NotificationBell.jsx         # creator-only, SSE pending count
    SessionRequestNotifier.jsx   # in-app approval modal
    TheftRecoveryDialog.jsx      # login-page WebAuthn flow
    BiometricEnrollButton.jsx    # DeviceManager WebAuthn enroll
    ViewModePreviewBanner.jsx    # banner when creator previews as guest
    SiteLockedOverlay.jsx        # full-screen lock in creator-only mode
    SiteModeBadge.jsx            # 4-state dropdown
  hooks/useDeviceIdentity.js     # role/site_mode/viewMode/canWrite/SSE
  lib/
    deviceIdentity.js            # ECDSA WebCrypto + attestation flow
    webauthnClient.js            # WebAuthn create/get with b64url framing
```
