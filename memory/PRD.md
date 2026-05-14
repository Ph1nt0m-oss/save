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

### 2026-02-14 — Iter 47 (current)
- **#1 Bouton "Révoquer" sur chaque ligne d'historique** → CreatorToolbar history side-panel.
- **#2 "Révoqué" → "Annulé"** dans toutes les langues (FR + EN), `dec_revoke` + `role_revoked` mis à jour.
- **#3 Bouton "Vider l'historique"** + endpoint `POST /api/devices/decisions/clear` (créateur uniquement) — supprime `device_decisions` sans toucher aux états réels.
- **#4 Bouton "Exporter"** côté frontend → génère un .txt téléchargé `codeforge-history-YYYY-MM-DD.txt` avec toutes les entrées (clé complète + action + label).
- **#5 Profile mobile fixé** : `overflow-hidden` → `overflow-x-hidden pb-16` ; section "Ma clé d'appareil" déplacée AVANT "Mot de passe oublié" (accessible sans scroll infini) ; layout stack mobile (clé sur sa ligne, boutons en dessous).
- **#6 "Envoyer au créateur"** déjà fonctionnel via `/api/devices/send-to-creator` (côté toolbar Profile, non-créateurs uniquement).
- **#7 Bouton Historique masqué pour non-créateurs** : `isCreatorDevice && (...)` dans CreatorToolbar.
- **#8 Fix "session expirée" sur mobile** : poll → si `approved` → vérifier `/auth/me` avec le nouveau token AVANT navigate ; remplacement de `navigate()` par `window.location.replace('/dashboard')` (force re-bootstrap propre de l'AuthProvider, contourne tous les edge-cases mobile Safari).
- **`/devices/revoke` idempotent** : accepte un target déjà supprimé (retourne `{success:true, existed:false}`) — nécessaire pour la révocation depuis l'historique.
- **Backend testing** : 12/12 pass (iter_47.json), aucun bug critique.

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
