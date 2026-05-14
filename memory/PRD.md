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

### 2026-02-14 — Iter 46 (current)
- **Bug fix**: "session expired" sur le 2e appareil après approbation → `/auth/session-request-status` est maintenant **idempotent** (persiste le token sur la demande, ne supprime plus, retourne `{status:"expired"}` au lieu de 404 pour les demandes inconnues). Frontend force aussi `axios.defaults.headers.Authorization` AVANT navigate.
- **Labels d'appareils lisibles** : `Galaxy S21`, `iPhone`, `Mac · Chrome` au lieu de la chaîne UA brute (via `/app/frontend/src/lib/deviceLabel.js` avec mapping Samsung).
- **Bannière d'attente enrichie** sur le 2e appareil pendant l'approbation : affiche label de l'appareil + email + hint explicatif (style cohérent avec la modale du 1er appareil).
- **`/devices/revoke` + `/devices/disconnect`** suppriment maintenant la ligne dans `device_keys` (audit conservé dans `device_decisions`) → la liste "Appareils enregistrés" reste propre.
- **WebAuthn theft-verify** supprime aussi les anciens créateurs (au lieu de les marquer 'revoked').
- **Nouveau bouton "Envoyer ma clé au créateur"** dans Profile (non-créateurs uniquement) → endpoint `POST /api/devices/send-to-creator` (vérifie la signature ECDSA, log `request_access`, met le device en pending).
- **View toggle déplacé** : retiré côté créateur (CreatorToolbar), maintenant visible UNIQUEMENT pour les invités → toggle "Vue utilisateur / Vue créateur RO" pour leur permettre de prévisualiser l'UI admin.
- **Banner de preview** mis à jour pour viser les invités (pas le créateur).
- **Historique en side-panel vertical** plein écran (au lieu d'une modale centrée) → scroll vertical infini.
- **`canWrite`** revu : ne dépend plus de la `viewMode` du créateur (le créateur a toujours `canWrite` selon site_mode) ; pour les invités, `viewMode === 'guest'` force `canWrite=false` (preview RO).
- **Backend testing** : 11/11 (iter_46.json) — flow d'approbation + cleanup vérifiés.

### Iter 45
- WebAuthn "Déclarer un vol", 4-tier site mode, view-mode toggle créateur (déprécié en iter 46), cleanup DB initial.

### Iter 44
- DeviceManager : masquage du device courant + onglet Historique (déplacé dans CreatorToolbar en iter 45, puis side-panel en iter 46).

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
