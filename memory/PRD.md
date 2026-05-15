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

### 2026-02-15 — Iter 64 (Fix mobile toast "session expirée" + filtres ideas créatrice)

**🐛 Hotfix critique signalé sur mobile** (screenshot user) :
- Le toast « Ta session a expiré côté serveur » apparaissait toujours sur Android malgré le `sessionStorage` flag d'iter63 — cause : `sessionStorage` est éphémère (perdu à la fermeture d'onglet sur mobile).
- **Correctif** :
  1. Toast `?reason=session_expired` **complètement supprimé** de `Login.js` — l'URL est juste strippée silencieusement.
  2. Flag `codeforge_session_pending` migré `sessionStorage` → `localStorage` avec **TTL 15 min** (JSON `{request_id, email, until}`).
  3. **Restauration auto** du `pendingApproval` au mount de Login.js si le flag est encore valide → la polling reprend même après fermeture/réouverture d'onglet mobile.

**✨ Filtres Idées/Bugs/Autres côté créatrice** (`IdeasButton.jsx`) :
- Badges colorés par kind (Bug rouge, Idée jaune, Autre cyan) sur chaque message reçu.
- 3 cases à cocher de filtre (Bug/Idée/Autre) + bouton « Tout cocher/décocher ».
- Toggle « Trier par type » : groupe les messages dans l'ordre Bug → Idée → Autre, en préservant la chronologie dans chaque groupe.
- Filtres + tri **persistés en localStorage** (codeforge_ideas_filters, codeforge_ideas_sort_kind) → survivent aux reloads.

**Multi-device illimité confirmé** : 3 logins simultanés depuis 3 device_keys différents → 3 demandes pending parallèles en base, A peut les approuver indépendamment, les sessions cohabitent.

**Tests iter64** : 17/17 backend pytest PASS (iter63 6/6 + iter62 11/11) · Frontend smoke mobile 420x900 PASS (zero toast) · Restauration pending banner + cleanup TTL expiré tous OK · IdeasButton filters/sort/persistence verified.

### 2026-02-15 — Iter 63 (Multi-device session-pending définitivement réparé)

**🔧 Corrections critiques du flux multi-appareils** :

1. **Bug "session expirée" fantôme éliminé** :
   - Pendant un `pendingApproval` (appareil B attend l'OK de A), `sessionStorage.codeforge_session_pending='1'` est posé.
   - `AuthContext.js` interceptor 401 : skip tout redirect/clear si flag présent.
   - `Login.js` : suppression auto de `?reason=session_expired` dans l'URL au moment où on entre en pending. Toast bloqué côté useEffect aussi.
   - Flag nettoyé sur approved/denied/expired/cancel.

2. **TTL d'approbation 10 → 15 minutes** (`/auth/login` insère `expires_at = now + 15min`).

3. **Modal "Changer mot de passe (recommandé)" côté A après refus** :
   - `SessionRequestNotifier.jsx` : sur deny, plus de toast → modal dédié `data-testid='sess-deny-modal'`.
   - 2 boutons : « Changer mon mot de passe » (navigate `/profile?section=security`) + « Plus tard » (ferme). Non bloquant.

4. **Nouveau rôle silent `inactive` pour les devices** :
   - `/devices/register` : 1er device → `creator`, tous les autres → `inactive` (au lieu de `pending`).
   - `/accounts/list` + `/devices/list` filtrent `{role: {$ne: 'inactive'}}` → ces devices N'apparaissent PAS dans le panneau Créatrice tant que l'utilisateur ne fait pas explicitement `/devices/send-to-creator`.
   - Le nudge passe automatiquement `inactive` → `pending`.

5. **Déduplication 1 device-key = 1 compte** :
   - `/auth/login` : check `device_keys.email` ; si déjà bound à un autre user vérifié → `HTTP 409` avec message FR clair indiquant l'email lié.
   - Binding posé à chaque login réussi. Auto-clearing si stale (le user lié a été supprimé).

6. **Wording i18n FR/EN aligné sur la spec utilisateur** :
   - `sess_denied_body` = "Votre demande a été refusée. Veuillez réessayer avec une autre adresse mail."
   - `sess_expired_body` = "Votre demande a expiré. Veuillez réessayer ou vous reconnecter avec une autre adresse mail."
   - `sess_in_progress_body` = "Votre demande est en cours de validation. Veuillez patienter."

**Tests** : iter63 backend 6/6 pytest PASS (`/app/backend/tests/test_iter63_session_pending.py`) · Régression iter62 OK · Toast suppression vérifié end-to-end (avec/sans flag) · Modal denied + i18n vérifiés en code review.

### 2026-02-15 — Iter 62 (Capture d'écran d'appareil OBLIGATOIRE à l'inscription)

**🆕 Nouvelle exigence sécurité** :

1. **Endpoint OCR** `/api/auth/ocr-device-info` (Gemini 2.5 Flash Vision via `emergentintegrations`) — accepte image base64 (data-URL ou bare), retourne `{kind: 'phone'|'computer'|'unknown', product, model, device_name, confidence}`. Cap à ~3.5 MB.

2. **`/api/auth/register` enrichi** : exige `device_capture_kind` (`phone`|`computer`) + soit `device_capture_product`/`device_capture_model` (téléphone) soit `device_capture_name` (ordinateur). Stocké sur `users.device_capture`. Sans capture valide → 400 avec message FR explicite.

3. **Composant frontend `DeviceCaptureField.jsx`** : dropzone glassmorphism (drag-drop + click + Ctrl+V paste), redimensionne à 1600px max et JPEG 0.85 avant upload, affiche le résultat OCR (Smartphone/Monitor icon + product/model ou device_name). 5 data-testids exposés.

4. **`Login.js`** : import + state `deviceCapture` + rendu du composant entre pseudo et email en mode signup. Validation client miroir du backend (defense in depth).

**Tests** : iter62 backend 11/11 PASS (pytest `/app/backend/tests/test_iter62_device_capture.py`) · Frontend e2e PASS (dropzone visible, validation bloque submit sans capture, toast affiché, requête interceptée) · Régression login Pass1234 OK.

### 2026-02-14 — Iter 60-61 (Migration Gmail SMTP + flux complets créatrice)

- Migration Resend → **Gmail SMTP** via `aiosmtplib` (App Password). Plus de sandbox, envoi à n'importe quelle adresse.
- Mode Créatrice complet : annonces (📣), sondages, boîte à idées (💡), approbation manuelle des exports ZIP/APK/EXE, blocage/bannissement/exclusion temporaire.
- Continuité LLM en arrière-plan via `asyncio.shield` (génération continue même si client se déconnecte).

### 2026-02-14 — Iter 59 (Email no-reply définitif + fallback toujours exposé)

**🔧 Correction définitive** :

1. **Sender « no-reply »** :
   - `EMAIL_FROM` = `CodeForge AI <no-reply@resend.dev>` (Resend accepte ce local-part sur leur domaine partagé — testé OK).
   - Les 4 fallbacks codés en dur dans `server.py` (register, resend-verification, forgot-password, theft-email) tous alignés.
   - Le destinataire voit désormais **« CodeForge AI » avec l'adresse `no-reply@resend.dev`** (et plus `onboarding@resend.dev`).

2. **Fallback verification_link toujours présent** :
   - `/api/auth/register` retourne TOUJOURS `verification_link` dans la réponse, même quand `email_sent=true`.
   - `/api/auth/resend-verification` idem.
   - Frontend Login.js : affiche le bloc « Lien direct » même quand l'e-mail est marqué envoyé → l'utilisateur peut copier-coller le lien si l'e-mail tarde / atterrit en spam / est refusé par Resend (sandbox).
   - Messages FR adaptés : « Ton e-mail n'a pas pu être envoyé automatiquement — voici le lien de confirmation à coller dans ton navigateur. »

**Limitation héritée (non bloquante)** :
Resend reste en sandbox → seul `16.axelblaze.10@gmail.com` reçoit réellement les e-mails. Tous les autres voient le lien dans l'UI grâce au fallback. Pour débloquer l'envoi à tout le monde : vérifier un domaine perso sur Resend (DNS SPF/DKIM/DMARC).

**Tests** : iter59 backend 8/8 PASS · Resend ✅ 200 OK confirmé sur `16.axelblaze.10@gmail.com`.

### 2026-02-14 — Iter 57 (Delete accounts + Right-side messaging)

- **`/api/accounts/delete-one`** : creator + target_key_id → suppression complète du device_key (400 si self, 404 si introuvable, 403 si non-creator). User sessions purged.
- **`/api/accounts/delete-all`** : creator + password (bcrypt confirm) → wipe `device_keys.delete_many({key_id: $ne caller})`. Sa propre clé est préservée. Loggé dans `account_history` avec `deleted` count.
- AccountsButton.jsx : per-row **Delete** button (Trash) sur tous les non-self. Bottom-bar avec « **Vider la vue** » (local-only via `localStorage codeforge_accounts_hidden`) ⇔ « **Réafficher tout** » + « **Tout supprimer** » (call backend avec password prompt). Tab « Historique » supprimé entièrement.
- CreatorToolbar.jsx : bouton « Historique » retiré. Panneau d'historique des décisions retiré (le JSX est gone, les states résiduels seront cleanup au prochain refactor).
- MessagesPanel.jsx : passe de **modal centré** → **aside slide-from-right** (`top-0 right-0 bottom-0 w-full sm:w-[460px] md:w-[540px]`) — comme l'ancien panel d'historique.

**Tests** : iter57 backend 11/11 PASS · Frontend smoke / static grep 100% PASS · password gate sur delete-all ajouté après code review.

### 2026-02-14 — Iter 56 (Polish 2)

- **FeedbackButton (💡 jaune flottant)** visible pour TOUS sur Login/Landing (créatrice incluse). Caché uniquement sur `/dashboard` côté créatrice (qui a déjà `IdeasButton` dans le header).
- **"Supprimer le mode créatrice"** désormais **par ligne** dans le panel AccountsButton (icône `ShieldOff` rouge) — plus de barre globale en bas. Self (« Toi » badge) ou autre créatrice : le bouton apparaît uniquement quand `row.role === 'creator'`. Password obligatoire (le sien, pas celui du target).
- Backend `/api/accounts/remove-creator` étendu : `target_key_id` optionnel. Refuse si target non-creator (400) ou password incorrect (403). Log `remove_creator_self` ou `remove_creator_other` dans `account_history`.

**Tests** : iter56 backend 8/8 PASS · Frontend FeedbackButton sur /login visible, modal ouvre, soumission vide OK.

### 2026-02-14 — Iter 55 (Polish: WebAuthn fallback + Feedback unified + Message grouping)

**Réorganisation header** :
- `AccountsButton` déplacé du droit → **gauche** (entre `TheftButton` et logo) sur Landing + Dashboard. Reste caché pour non-créateurs.
- `MessageButton` reste à droite.

**TheftRecoveryDialog accessible partout** :
- WebAuthn reste le chemin par défaut quand supporté + enrolled
- **Fallback e-mail** : `/api/auth/theft-email-request` (anti-enum 200) → magic link 30 min → `/api/auth/theft-email-confirm` révoque tous les `creator|approved` keys de l'email
- Nouvelle route `/theft-confirm?token=...` avec page `TheftConfirm.js` qui consomme le token

**Login page enrichie** :
- Top-left : `TheftButton labelled` + `AccountsButton`
- Top-right : `DeviceKeyCopyButton` (icône Key, copie share-code) + `MessageButton icon`
- `FeedbackButton` (yellow Lightbulb floating) déjà global

**Feedback unifié vers Ideas system** :
- `FeedbackButton.jsx` réécrit : envoie vers `/api/ideas/send` (avec `kind: bug|idea|other`)
- **Aucune limite caractères**, **envoi vide accepté**
- Tab « Mes envois » via `/api/ideas/mine` (signed, retourne items du device)
- Anonymous OK : sans signature → sender_label = "Anonyme"
- Créateurs ne voient pas le bouton flottant (ils ont déjà `IdeasButton` dans le header)
- Backend : `IdeasSendIn.key_id` Optional + try-catch sur _verify_signed pour fallback anonymous

**MessagesPanel grouping** :
- Messages consécutifs du même expéditeur → un seul header (pseudo + date) en haut du groupe
- Header re-affiché si >10 min entre 2 messages
- Plus de duplication « Galaxy S21 / Galaxy S21 14/05/2026 23:09:54 »

**Sessions multi-appareils** (déjà OK depuis iter52, vérifié) :
- 1er appareil en attente : « Votre demande est en cours de validation. Merci de patienter. »
- Refus : reste sur login + « Demande refusée. Merci de vous connecter avec une autre adresse mail. »
- Acceptation : redirection automatique dashboard
- Expiration : « Demande expirée. Veuillez vous reconnecter ou réessayer ultérieurement. »
- Sur refus : toast actionnable « Changer mon mot de passe » côté 1er appareil

**Tests** : 15/15 backend PASS · Frontend layout Login/Landing/theft-confirm 100% PASS · 0 JS error.

### 2026-02-14 — Iter 54 (Creator power tools complete)

**Big bang — tout en une fois** :

**Backend** (~25 nouveaux endpoints, 47/47 tests PASS) :
- `/api/accounts/list` : liste de tous les comptes, pseudo + email + statuts (muted, banned, role, excluded), dédup automatique #N pour duplicates
- `/api/accounts/rename-pseudo` : créatrice renomme n'importe quel pseudo (users + device_keys)
- `/api/accounts/mute|unmute` : créatrice ne reçoit plus la notif badge pour les muted, conversation continue normalement
- `/api/accounts/exclude` : exclusion temporaire (durée requise, jamais infini, plafonnée 90 jours), purge des `user_sessions`. Verify renvoie `kick_excluded`.
- `/api/accounts/ban|unban` : ban permanent sur l'email (`banned_emails` collection, survit au re-enregistrement). Verify renvoie `kick_banned`.
- `/api/accounts/history`, `/clear` : événements modération (mute/unmute/exclude/ban/rename/delete_project/remove_creator_self)
- `/api/accounts/visit` : retourne projets (inclus soft-deleted) + chat history d'un user
- `/api/accounts/delete-user-project` : soft-delete projet (deleted_by_creator=True)
- `/api/accounts/remove-creator` : auto-demote du créatrice (bcrypt password confirm), log dans device_decisions + account_history
- `/api/ideas/send|inbox|mark-read|delete` : feedback unlimited, attaché au pseudo
- `/api/announcements/create|list|delete` : audience `all` ou `approved`
- `/api/polls/create|list|vote|delete` : 2-10 options, tally agrégé + my_vote, vote unique par device
- `/api/exports/request|decide|pending|status` : workflow d'approbation pour APK/EXE/source. Créateur auto-approve.
- `/api/creator/translate` : traduction via Emergent LLM gpt-5.2 avec fallback gracieux
- `/api/auth/update-pseudo` : édition pseudo par l'utilisateur
- Inscription : uniqueness pseudo **levée** (index partiel reste pour cohérence interne)

**Frontend** (6 nouveaux composants) :
- `AccountsButton.jsx` : panel créatrice complet (list + history tabs, rename/mute/block/unblock/exclude/ban actions, "Supprimer le mode créatrice")
- `IdeasButton.jsx` : composer côté user + inbox côté créatrice avec badge unread
- `AnnounceButton.jsx` : 3 tabs (annonce / sondage / gérer), formulaire 2-10 options
- `AnnouncementsBanner.jsx` : top-of-screen global, dismiss par localStorage
- `ExportApprovalNotifier.jsx` : modal créatrice approuve/refuse, ouvre AccountVisitView pour review
- `AccountVisitView.jsx` : full-screen, projects + messages + traduction inline
- Dashboard : export gate non-créatrice → request + polling status → toast d'état
- Profile : section pseudo-edit
- i18n : ~80 nouvelles clés FR + EN, autres locales via fallback

**Tests** : 47/47 backend PASS. Frontend Landing smoke clean.

### 2026-02-14 — Iter 53 (Layout swap + Block icons + Delete logic)

**UX rework header** :
- `TheftButton` déplacé à GAUCHE de chaque header avec label « Déclarer un vol » / « Report theft » (variant `labelled`).
- `MessageButton` déplacé à DROITE, à côté de `NotificationBell` dans Dashboard, et à côté de `LanguageToggle` dans Landing.
- `MessageButton` icon variant rend désormais le bouton immédiatement, même si `device.keyId` n'est pas encore disponible (badge unread polling attend simplement la clé). Plus de "trou" à l'affichage initial.

**MessagesPanel (côté créatrice uniquement)** :
- Icône **Block** = `Ban` (cercle barré 🚫), icône **Unblock** = `ShieldCheck`. Les deux sont affichés de façon conditionnelle selon `thread.role === 'blocked'`.
- `deleteContact` ne révoque PLUS le device (n'appelle plus `/devices/revoke`). Seul `/messages/delete-thread` est invoqué : le pseudo disparaît de la liste côté créatrice mais l'utilisateur peut toujours envoyer un nouveau message qui réintroduira le thread. Combo `Bloquer + Supprimer` = pseudo invisible côté créatrice ET utilisateur muet (sauf si la créatrice débloque manuellement via l'historique des décisions).

**Tests** : iter53 backend 10/10 PASS (4 skipped, 1 gpt-5.2 502 upstream OpenAI hors notre code). Génération en ligne validée end-to-end via Emergent claude-haiku → 200 avec `code.files`.

### 2026-02-14 — Iter 52 (Header buttons + background generation + UX polish)

**Implémentations** :
- **Boutons header global** : `MessageButton` (icon variant, badge unread) ajouté à gauche du logo dans Landing (entre Discover et logo) et dans Dashboard (à côté du LanguageToggle). `TheftButton` (icône ShieldAlert) ajouté à droite dans Landing et Dashboard. Plus visibles que l'ancienne version inline tout en bas.
- **Messages personnalisés de déconnexion** : `kick_creator_only_body` = "La personne qui a créé ce site souhaite être en privé." et `kick_private_body` = "La personne qui a créé ce site procède à quelques modifications avec ses personnes de confiance. Merci de retenter votre connexion ultérieurement." Le SiteLockedOverlay reçoit désormais explicitement `kickReason` depuis useDeviceIdentity.
- **Continuité génération en arrière-plan** : `/api/chat/message`, `/api/ai/generate-complete-app` et `/api/ai/generate-code` enveloppés par `_run_in_background` (`asyncio.shield(asyncio.create_task(coro))`). Si le client se déconnecte (ex: kick après site-mode change), la génération continue et persiste son résultat en DB. L'utilisateur retrouve la réponse au prochain `/chat/history`.
- **Hide site-mode badge non-créateurs** : `SiteModeBadge` retourne désormais `null` inconditionnellement pour `role !== 'creator'` — le sélecteur Public/Privé/Créatrice/Invité n'est plus jamais affiché aux visiteurs.
- **Sécurité après deny** : `SessionRequestNotifier` propose désormais un toast actionnable "Changer mon mot de passe" après le refus d'une demande de session.

**Test status** : iter52 smoke 8/8 PASS (backend). Frontend manuellement validé (Landing fresh visitor : badge caché, boutons message + theft visibles).

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
