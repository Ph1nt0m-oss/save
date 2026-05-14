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

### 2026-02-14 — Iter 49 (current)
**Backend (15/15 tests passing)** :
- **Restauré** : Gmail one-device-at-a-time **indépendamment de site_mode** (le bug précédent a été corrigé en iter 46 via idempotency, donc OK de réactiver).
- **`PUT /system/site-mode`** : accepte `guest_view` (forçage de vue pour les invités) ; déconnecte les sessions affectées au switch :
  - `creator` → toutes sessions non-créateur supprimées
  - `private` → sessions non-(creator/approved) supprimées
- **`/devices/verify`** retourne `kick_reason` (`kick_creator_only`, `kick_private`, `kick_blocked`, `kick_revoked`, `null`)
- **Nouveau role `blocked`** + endpoints `/devices/block` (créateur) et `/devices/unblock`
- **`/devices/send-to-creator`** → 403 si bloqué avec message dédié "Votre demande a été formulée de nombreuses fois…"
- **`_log_decision`** filtré : ne persiste QUE `approve`/`revoke`/`promote` (filtrage demandé)
- **`/auth/register`** : `pseudo` requis (3-30 char), unique (index partial), `Créatrice` réservé

**Frontend** :
- **SiteLockedOverlay** adapté avec `kickReason` + messages localisés + bouton "Voir en mode invité" (uniquement en mode private)
- **CreatorToolbar** : history filtrée à 3 actions, badges **vert** (Accepté), **rouge** (Refusé), **orange** (Créateur) ; boutons **Bloquer** (renforcé après 2 refus) et **Débloquer** + bouton **Annuler** (undo)
- **SiteModeBadge** : sous-options pour le mode `guest` (libre / forcer user / forcer creator)
- **Profile** : clé d'appareil avec `break-all` (wrapping multiligne propre, plus de scroll horizontal)
- **Login** : champ pseudo requis dans l'inscription, validation 3-30 chars
- **Translations** ajoutées (FR+EN) : `kick_*`, `signup_pseudo_*`, `hist_block/unblock/blocked/unblocked`, `sm_guest_view_*`, `dec_promote` ("Créateur" au lieu de "Promu créateur")

**Différé (Phase C, ~3-4h chaque)** :
- Système de messagerie privée bidirectionnelle créateur ↔ utilisateur (depuis page de connexion même en privé)
- Générations IA en arrière-plan (refactor major : nécessite background tasks + polling pour reprise après reconnexion)

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
