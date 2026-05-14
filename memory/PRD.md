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

### 2026-02-14 — Iter 45 (current)
- **Logique canWrite revue** : `public` → tout le monde écrit ; `guest` → personne n'écrit ; `private` → creator+approved seulement ; `creator` → creator seulement
- **Vue Créateur / Vue Invité** (`viewMode` localStorage, broadcast event) — le créateur peut prévisualiser l'app comme un invité (canWrite=false, UI admin masquée)
- **Banner persistant** "Tu prévisualises comme un invité" en haut
- **Toolbar `CreatorToolbar`** regroupe : SiteModeBadge + bouton Historique des décisions + bouton View Mode toggle
- **DeviceManager nettoyé** : suppression de l'onglet Historique (déplacé dans CreatorToolbar)
- **Profil → "Ma clé d'appareil"** affichée pour tous SAUF le créateur (les non-créateurs ne voyaient pas leur JWK sur mobile)
- **One-device-at-a-time** : `/api/auth/login` détecte un autre appareil actif → HTTP 202 `{request_id}` + ouverture d'une demande d'approbation côté 1er appareil (collection `session_requests`, TTL 10 min, géoloc IP pour @gmail.com uniquement)
- **`SessionRequestNotifier`** modal global : le 1er appareil voit la demande avec label appareil + localisation (Gmail) → Approuver / Refuser
- **WebAuthn "Déclarer un vol"** : 4 endpoints (`/webauthn/register-options|verify|declare-theft-options|verify`) + composants `BiometricEnrollButton` (DeviceManager) + `TheftRecoveryDialog` (Login)
  - Le créateur enrôle son empreinte digitale via un platform authenticator
  - N'importe quel appareil peut "Déclarer un vol" → si empreinte valide → révoque tous les autres créateurs + promeut l'appareil courant
- **DB cleanup** : suppression de toutes les `device_keys` SAUF `dev_a797438afc28c67923881d46ae2971c1` (créateur conservé)
- **Mobile zoom-out** : `body { min-width: 320px; overflow-x: hidden }` + `clamp` font-size en mobile
- **Backend testing** : 15/16 cases pass (iter_45.json)

### Iter 44 (précédent)
- DeviceManager : masquage de l'appareil courant + onglet Historique (déplacé en iter 45)
- 16 langues, RTL Arabic, neutralisation des noms d'IA

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
