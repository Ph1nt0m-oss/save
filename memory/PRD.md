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

### 2026-02-14 — Iter 51 (DEFINITIVE mobile session fix)

**Root cause identifié** (troubleshoot agent) : courses parallèles entre les polls `setInterval(2500ms)` combinées à la propagation d'écriture Mongo causaient :
1. Plusieurs polls en vol simultanés
2. 401 transient sur `/auth/me` juste après l'insert
3. Interceptor axios 401 → redirect vers `/login?reason=session_expired` AVANT que `replace('/dashboard')` ne s'exécute

**Fix appliqué (testé 16/16, retest_needed=False)** :
- **Frontend** : guard `inFlight` (max 1 poll en vol), arrêt immédiat de l'interval AVANT validation, `/auth/me` retry 4× backoff (200/400/800ms), flag `sessionStorage.codeforge_session_grace_at` posé à l'approbation
- **Frontend AuthContext** : interceptor 401 respecte une fenêtre de grâce de 5s après approbation → ne redirige plus pendant cette fenêtre
- **Backend** : read-after-write check (3×50ms) sur `user_sessions.insert_one` avant de renvoyer le token, idempotency confirmée (10 polls parallèles → même token)

### Iter 50
- Messagerie privée bidirectionnelle (collection + 5 endpoints + UI bi-mode), cool-down send-to-creator (10 min), cool-down messages (30s), cache _get_site_mode 30s.
**Backend (19/19 tests passing)** :
- **Cache `_get_site_mode()`** : in-memory 30s, invalidé sur PUT `/system/site-mode`.
- **Cool-down `/devices/send-to-creator`** : 1 nudge / 10 min / clé d'appareil (429 si trop tôt).
- **Système de messagerie privée bidirectionnelle** (créateur ↔ utilisateurs) :
  - Collection `messages` + endpoints `/messages/send`, `/messages/inbox`, `/messages/thread`, `/messages/unread-count`, `/messages/delete-thread`
  - Cool-down 30s par appareil sur `/messages/send` (exempté pour le créateur — il peut répondre rapidement à plusieurs utilisateurs)
  - Limite 2000 chars/message, 100 threads dans l'inbox, 500 messages/thread
  - Marquage de lecture automatique sur `/messages/thread`
  - Blocage : appareils `blocked` reçoivent le même message localisé

**Frontend** :
- **`MessagesPanel`** : UI bi-mode (inbox + conversation côté créateur, thread unique côté utilisateur). Auto-refresh 4s. Composer avec Ctrl+Enter.
- **`MessageButton`** : variantes `floating` (FAB bouton flottant jaune, visible partout avec badge unread rouge) et `inline` (lien sur Login).
- **`/login`** : lien "Envoyer un message au créateur" même en mode privé/créateur (sans être connecté).

### Iter 49
- Gmail one-device approval restauré, kick instantané sur switch site_mode, rôle `blocked`, /devices/block & unblock, historique filtré (Accepté/Refusé/Créateur), pseudo unique requis, view-mode dans guest sub-options.

### Iter 48
- Approval flow conditionnel sur site_mode (annulé en iter 49), "Annulé"→"Refusé", bouton Annuler (undo), Profile mobile scroll.

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
