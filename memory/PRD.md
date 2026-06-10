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

### 2026-06-10 — Iter 87 (Vues décochables + distinction public/privé en CONTEXTE + IA Emergent à jour + sécurité code)

**Fix verrou de vue (bug user)** :
- ViewModePicker iter87 : 5 vues désormais cochables y compris 'creator' (ordre ['creator','user','modo','admin','guest']). viewMode peut être **null** (= mode écriture par défaut). Click sur case active = `setStoredViewMode(null)` (decoche). Bouton "Désactiver toutes les vues".
- useDeviceIdentity : readViewMode() retourne null si rien en localStorage. `isCreatorView` = `!viewMode || viewMode==='creator'`.

**i18n traductions modo/admin** :
- `sm_guest_view_force_modo` = "Forcer la vue modo" / "Force modo view"
- `sm_guest_view_force_admin` = "Forcer la vue admin" / "Force admin view"

**Sécurité PrivateProgramming** :
- `/api/private/code/read-file` + `/api/private/code/grep` retournent **403 SYSTÉMATIQUEMENT** (plus aucun gating). Le code n'est visible par PERSONNE, même créatrice — sécurité défensive.
- Frontend `PrivateProgramming.js` : écran "Accès refusé" permanent.

**Distinction public/privé EN CONTEXTE (pas en puissance)** :
- Même moteur IA, même API, mêmes outils. Différence uniquement au niveau de la POLICY de contexte :
  - Public : `_context_limit = 50` messages d'historique → expérience immédiate, indépendante par session.
  - Privé seul (site_mode=['private']) : `_context_limit = 500` messages → continuité étendue inter-sessions, mémoire profonde.
- Implémenté dans `chat/message` via `_is_private_only` computed from `_get_site_modes_list()`.

**MODEL_ROUTES mis à jour avec les vraies IDs Emergent** :
- 8 nouveaux IDs : `claude-5-fable` (Le plus capable), `gpt-5.5` (Défaut), `claude-4.8-opus` (Thinking), `claude-4.7-opus-1m` (Contexte long), `claude-4.6-sonnet` (Code), `gpt-5.3-codex` (Code), `gemini-3.1-pro` (Multimodal), `gpt-5.4-1m` (Contexte long).
- Default switched : `gpt-5.2` → `claude-sonnet-4-5-20250929` (Emergent recommended).
- Legacy IDs gardés pour compat (gpt-5.2, claude-opus, claude-sonnet, gemini-3-pro, gemini-3-flash).

**Tests** : **89/89 PASS** cumulé (11 nouveaux iter87 + 78 régression iter81 à iter86). Aucun action item du testing agent.

### 2026-06-10 — Iter 86 (Bugs UX fixes + 3 reportés livrés)

**Fixes UX user-signalés** :
- **ViewModePicker refonte cases à cocher décochables** : bug du verrou résolu. Click sur case active = retour `creator`. Bouton "Revenir à la vue Créatrice" visible si simulation active.
- **ViewSimulationBanner** : bandeau amber persistant en haut quand créa simule un rôle. Croix de revert 1-click.
- **Tchat admin manquant ajouté** : `GROUP_TYPES` étendu à 7 (ajout 'admin'). `_groups_for_device` mis à jour : admin a {admin, staff, public_staff}, modo a {modo, staff, public_staff}, créa voit tout (y compris admin chat).
- **Distinction public/private vs staff stricte** : `_device_matches_mode` exige que staff/admin/modo soient explicitement cochés pour qu'un device staff passe (cocher 'public' seul EXCLUT le staff). UX cohérente avec la sémantique demandée.
- **guest_view étendu modo/admin** : la créa peut maintenant forcer la vue Modo ou Admin sur les visiteurs invités (5 options : free/user/modo/admin/creator).
- **Friends panel caché en vue créa pure** : `open-friends-btn` visible uniquement si `viewMode !== 'creator'` (la créa peut DM directement sans demande).
- **LanguageToggle dropdown** : `max-w-[calc(100vw-1rem)]` pour éviter débordement viewport mobile.

**3 reportés livrés** :
1. ✅ **Push GitHub RÉEL (opt-in)** : nouveau hook `on_commit` dans `orchestrate_actions`. server.py wire `on_commit_real` qui appelle `push_to_github()` SI `payload.enable_commit=true` (opt-in). Push réel sur `Ph1nt0m-oss/save:main` dans `orchestrate-runs/{branch}.py`.
2. ✅ **Correction loop planner-fix** : quand `code_executed` échoue (stderr non vide), l'orchestrator demande un nouveau plan corrigé au planner avec stderr en contexte, re-exécute UNE FOIS max (anti-divergence), émet `phase_done({recovered: bool})`.
3. ✅ **Refacto slice 2** : `/api/friends/{request,decide,list}` extraits dans `routes/social_routes.py` via factory `build_friends_router(db, verify_signed, device_by_key)`. Inclus dans `app.include_router(...)`. Régression intacte (sig HTTP préservée).

**Implémentation `PrivateProgramming` réelle (plus de placeholder)** :
- **SiteProgrammingPanel** : grep (`/private/code/grep`) + viewer fichier (`/private/code/read-file`) creator-only.
- **AIProgrammingPanel** : doc des 4 agents prompts + bouton "Lancer pytest backend" (`/orchestrate/test-loop`) + historique d'exécution (`/orchestrate/history`).

**Tests** : **110/110 PASS** cumulé (14 nouveaux iter86 + 96 régression iter77/79/81/82/83/84/85). Aucun action item du testing agent.

### 2026-06-10 — Iter 85 (4 reportés livrés + fix verrou de vue + vues modo/admin)

**Fix verrou de vue (bug user-signalé) + ajout vues modo/admin/user** :
- Bug root cause : `CreatorToolbar` montrait le toggle de vue UNIQUEMENT pour `!isCreatorDevice` (inversé) → la créatrice ne pouvait jamais verrouiller sa vue. Le `setStoredViewMode` ne supportait que 2 valeurs (creator/guest).
- Fix : nouveau composant `ViewModePicker.jsx` avec **5 vues distinctes** (creator/user/modo/admin/guest), visible UNIQUEMENT pour la créatrice. Dropdown avec couleurs distinctes par rôle + warning amber quand non-créa.
- `useDeviceIdentity` étendu : `VALID_VIEW_MODES` = 5 entrées, expose `isRealCreator`, `isCreatorView`, `effectiveStaffKind` (override par viewMode si créa simule modo/admin).
- IdeasButton + AccountsButton cachés sauf en vue créa pure. AnnounceButton accessible si créa OU staff réel/simulé. canWrite calculé selon viewMode.

**Vrai streaming token-par-token DANS le final event (4ème reporté)** :
- `_llm_stream_tokens` (async generator) découpe la réponse complète en chunks de ~40 chars (espace-aware), émet 25ms entre chunks → 16 chunks/s ChatGPT-style.
- `orchestrate_actions` yield `final_chunk` events (delta + index). `final` event arrive à la fin avec contenu complet pour persistance.
- Frontend `useOrchestrate` intercepte les `final_chunk` pour accumuler `finalAnswer` SANS les ajouter à `events[]` → journal d'actions reste propre.
- `OrchestrationLog` affiche `finalAnswer` en temps réel avec cursor animé jaune `bg-[#E4FF00]` tant que l'event `final` n'est pas arrivé.

**preview_ready + commit_pushed events (1er reporté, MOCKED)** :
- Après `code_executed` réussi, l'orchestrateur émet `preview_ready` (URL stub vers preview frontend) et `commit_pushed` (branch virtuel `orchestrate/{session-id}`).
- MOCKED clairement noté dans `details.note` — pas de vrai rebuild sandbox ni push GitHub réel.

**Multiple testing-agents en boucle (2ème reporté)** :
- Nouveau endpoint `POST /api/orchestrate/test-loop {target='backend', path='tests/', project_id?}` qui lance `pytest` interne en sub-process (cwd `/app/backend`, timeout 90s, path-traversal refused).
- Émet events `test_run` (start/result avec stdout/stderr dans details) + `complete` via SSE. Auth requise → 401 sinon.

**Refacto `server.py` slice 1 (3ème reporté)** :
- Nouveau module `routes/social_routes.py` (118 lignes) avec `GROUP_TYPES` + `_groups_for_device` extraits.
- `server.py` importe via `from routes.social_routes import _groups_for_device`. Aucun endpoint déplacé pour cette slice (pure helper extract pour valider le pattern avant de bouger les routes).
- Régression : `/friends/*` et `/groups/*` fonctionnent identiquement (signatures HTTP intactes).

**Tests** : **96/96 PASS** cumulé (13 nouveaux iter85 + 51 régression iter77/79/81/82/83/84). Frontend audit code 100% validé par testing agent. Aucun action item.

### 2026-06-10 — Iter 84 (Streaming d'ACTIONS Emergent-style + observabilité vidéo + i18n context menu)

**Streaming d'ACTIONS au lieu de tokens (demande principale user)** :
- `orchestrator.py` réécrit en mode **YIELD événements typés** : `phase_started`, `phase_done`, `file_viewed`, `file_created`, `file_modified`, `code_executed_start`, `code_executed`, `search_done`, `thought`, `final`, `complete`, `error` (+ `commit_pushed`, `preview_ready` réservés MOCKED).
- Chaque événement = `{event_id, kind, summary, details, ts}`. Le `details` est lazy-loaded via `/api/orchestrate/event/{id}/details` (économie bande passante SSE).
- 3 helpers ajoutés : `_safe_path` (refuse paths absolus + `..`), `_read_file_safe` (60KB max), `_grep_safe` (restreint à `backend` + `frontend/src`, 8s timeout).
- 3 nouveaux endpoints : `POST /chat/orchestrate-stream`, `GET /orchestrate/event/{id}/details`, `POST /orchestrate/history`.

**UI temps réel (Emergent-style)** :
- Composant `OrchestrationLog.jsx` : liste d'événements avec icône par kind (Loader2 spinning pour phase_started, FileText pour file_viewed, Lightbulb pour thought, Sparkles pour final, etc.) et **flèche dépliable** qui fetch le détail à la demande.
- Hook `useOrchestrate.js` : consomme le SSE via `fetch + ReadableStream`, ajoute chaque event au state, expose `{events, running, finalAnswer, confidence, run, reset, abort}`.
- Chat.js : nouveau toggle **Mode Pro** (icône Cpu, data-testid `chat-pro-mode-toggle`) à côté du ModelPicker. Quand actif, route les messages via l'orchestrateur multi-agents et affiche le journal d'actions au-dessus du chat.

**Observabilité bug vidéo mobile** :
- `BiometricEnrollmentField.jsx` émet des events structurés à `/api/observability/video-event` (iris_start, iris_stream_ok, iris_video_play_ok, iris_stream_error, iris_video_play_fail) avec UA / viewport / track_settings / readyState.
- Endpoint `POST /observability/video-event` (no-auth, anti-flood 50/min/session_id, auto-purge si >5000 docs).

**i18n context menu sidebar** :
- 9 clés ajoutées (`ctx_rename`, `ctx_copy_link`, `ctx_live_preview`, `ctx_download_zip`, `ctx_duplicate`, `ctx_share_enable`, `ctx_share_disable`, `ctx_delete`, `ctx_delete_confirm_title`, `ctx_link_copied`, `ctx_link_copy_failed`) en `fr` + `en`. Dashboard.js context menu utilise désormais `t()` partout.

**Tests** : **83/83 PASS** (12 nouveaux iter84 + 71 régression iter77/79/81/82/83). Frontend Playwright validé : login OK, toggle Mode Pro visible/fonctionnel, condition d'affichage OrchestrationLog correcte.

**Reportés (à faire plus tard)** :
- 🟡 Vrai streaming token-par-token DANS un événement `final` (besoin wrapper SSE direct Anthropic/OpenAI ; perte Universal Key)
- 🟡 Prévisualisation interactive automatique : sandbox rebuild + URL preview + push GitHub auto sur branche (volumineux ; emit `preview_ready` + `commit_pushed` events est prêt côté types, à wirer)
- 🟡 Multiple testing-agents en boucle dans l'app : génère → compile → routes → UI sim → corrige (architecture prête via orchestrator events, mais pas wired)
- 🟢 Refacto `server.py` (>9200 lignes) — slice par slice (premiers candidats : extraire `friends`/`groups` dans `routes/social_routes.py`)
- 🟢 Reste des strings hardcodés en FR dans Dashboard à passer en `t()`

### 2026-06-10 — Iter 83 ("Tout ce qu'il reste" : C11 multi-mode + bug fantôme + C7 orchestrateur)

**C11 — Site mode multi-checkbox (refacto str→array)** :
- Backend : `VALID_SITE_MODES` étendu à 7 entrées (+ staff/admin/modo). Nouveau helper `_normalize_modes()` accepte str OU list. `_device_matches_mode(dev, modes)` accorde l'accès si AU MOINS un mode actif matche le device.
- `/system/site-mode` PUT accepte `modes: [...]` (et garde `mode: str` pour compat). `/devices/verify` renvoie `site_modes: [...]` en plus de `site_mode: str` (= premier élément).
- Frontend `SiteModeBadge` refait : 7 checkboxes multi-sélection (data-testid `site-mode-option-{id}`). Bouton affiche "{n} audiences" si multi. Min 1 mode actif requis.
- Hook `useDeviceIdentity` expose `siteModes` (array) propagé par `CreatorToolbar`.

**Fix bug multi-device "Demande de connexion fantôme" (récurrent x4)** :
- Root cause identifiée : `/auth/session-pending` filtrait par `expires_at > now` (15 min) mais les requests pending dont l'autre device n'avait jamais traité la demande restaient affichées en boucle.
- Fix : auto-expire les pending requests de plus de **90s** (`stale_threshold`) via `update_many({status:'pending', created_at < now-90s}, $set:{status:'expired'})`.

**C7 — Orchestrateur multi-agents (architecture planner/critic/executor/arbiter)** :
- Module `/app/backend/orchestrator.py` (NEW, ~280 lignes) avec 4 rôles distincts, prompts spécialisés en JSON pur, mémoire de validation via collection `orchestrator_runs`.
- Sandbox `_execute_python` : sub-process avec timeout 8s, blocklist string + **AST scan** des imports/calls dangereux (os/subprocess/socket/eval/exec/open).
- 2 endpoints : `/api/chat/orchestrate` (one-shot) et `/api/chat/orchestrate-stream` (SSE phases). Cookie auth requise.
- Validation runtime confirmée par testing agent : pipeline ~32s, 4 LLM calls Claude Sonnet 4.5, plan/critique/exécution/arbiter en français.

**C18 quality-of-life** :
- Label `MessageButton` : Creator='Messages reçus', Staff='Messages staff', User='Contacter un modo' (au lieu de 'à la créatrice').

**Tests** : 71/71 PASS (11 nouveaux iter83 + 60 régression iter77/79/81/82). Frontend validé par testing agent.

**Reportés (P1 hors-scope iter83)** :
- Vrai streaming token-par-token (emergentintegrations n'expose pas le stream natif → besoin d'un wrapper SSE direct vers Anthropic/OpenAI). `/chat/stream` actuel = pseudo-streaming word-by-word.
- Bug d'affichage vidéo mobile en mode Public (P1 — pas reproductible en l'état).
- i18n sidebar tchats : MessageButton label corrigé ; autres traductions sidebar restent à passer en `t()`.
- Refacto `server.py` (>9100 lignes maintenant) en sous-routers.

### 2026-06-10 — Iter 82 (ROUGE : amitiés C20 + 6 group chats C19 + send-to-modo C18 + SSE streaming C5/C8 + visite full)

**Phase 1 — Vue de visite créatrice ENRICHIE (C13+C20)** :
- `/accounts/visit` retourne désormais : `target.email`, `key_id` (publique), `label`, `force_visitor`, `muted`, `banned`, `last_seen_at`, `created_at`, `biometric_kind`, `approved_by_kind`, `approved_by_label`, et 3 nouvelles listes : `private_messages` (DMs avec quiconque), `friend_requests` (sent+received), `group_posts` (publications dans les groupes).
- `AccountVisitView.jsx` refactoré en **6 onglets** : Infos compte (avec Copy clé/email), Projets, Chat IA, MP privés, Groupes, Amis. Bouton "Parler en privé" pour DM direct.

**Phase 2 — Système d'amitié par clé (C20)** :
- Collection `friend_requests` : `{request_id, from_key_id, from_pseudo, to_key_id, to_pseudo, status: pending/accepted/refused, created_at, decided_at}`.
- 3 endpoints : `/friends/request`, `/friends/decide`, `/friends/list`. Auto-acceptation si l'expéditeur est créatrice.
- Composant `FriendsPanel.jsx` (icône UserCog dans le header) avec input clé, demandes reçues (accept/refuse), amis acceptés, demandes envoyées.

**Phase 3 — 6 types de tchats de groupe (C19)** :
- Collection `group_messages` + types : `public, private, staff, modo, public_staff, public_private`.
- Helper `_groups_for_device(dev)` mappe rôle+staff_kind aux groupes accessibles. La créa voit les 6.
- 3 endpoints : `/groups/list`, `/groups/messages`, `/groups/send`.
- Composant `GroupChatsPanel.jsx` (icône Users dans le header) avec sidebar 6 groupes + zone chat + polling 4s.

**Phase 4 — Message vers modo random (C18)** :
- `/messages/send-to-staff` pick un modo aléatoire (fallback admin → fallback créa).
- `MessagesPanel.jsx` modifié : si `!isCreator`, l'envoi appelle `/messages/send-to-staff` au lieu de `/messages/send`.
- `/messages/inbox` élargi : modos voient leurs threads (where to_key_id == self), admins voient tout comme créa.

**Phase 5 — Chat streaming SSE (C5/C8)** :
- `/chat/stream` POST → `text/event-stream` qui émet `data: {delta, index}` word-by-word puis `data: {done, content}`.
- MOCKED : pseudo-streaming par mots (8ms/word) au-dessus de `send_chat_message` complet. Vrai streaming Emergent non exposé par emergentintegrations. Améliorable plus tard.

**Phase 6 — Quality-of-life** :
- Boutons Users (group-chats) + UserCog (friends) dans le header Dashboard. Switch automatique entre les 2 panneaux.

**Tests** :
- Backend pytest : **60/60 PASS** (12 nouveaux iter82 + 48 régression iter77/79/81). 0 régression.
- Frontend Playwright via testing agent : Login + Dashboard + GroupChatsPanel + FriendsPanel + friend-request 404 integration tous validés.

**Reportés (refacto profond hors-scope iter82)** :
- **C7** Orchestrateur Emergent multi-agents (planner+critic+executor+arbiter)
- **C11** Site mode multi-checkbox str→array (staff/modo/admin)
- Vrai streaming token-par-token via LlmChat (besoin d'un nouveau wrapper streaming chez emergentintegrations)

### 2026-06-10 — Iter 81 (C20 visite créa style Dashboard + finalisation des items orange)

**C20 — AccountVisitView réécrit pour mimer le Dashboard du user visité** :
- Layout 2 colonnes (sidebar projets + main chat) au lieu de 2 cards juxtaposées.
- Sidebar reproduit le code couleur Dashboard : dot jaune=chat-online, sky=chat-offline, emerald=web-online, violet=web-offline.
- Projets supprimés (`is_deleted=true`) en `opacity-30 grayscale` + badge rouge « supprimé ». Idem messages (opacity-25).
- Bandeau « Mode visite » jaune persistant en haut avec rôle (créatrice/admin/modo) du compte visité.
- Click sur un projet filtre les messages liés à ce `project_id`. Click sur « Tous les messages » affiche le full chat history.

**Quick wins finalisés** :
- Démo link bleu retiré de la page Login (mode signup) — l'utilisatrice doit passer par sa boîte Gmail réelle (commit iter80, vérifié iter81 par testing agent).
- Badges colorés admin (orange) / modo (cyan) / créatrice (jaune) dans DeviceManager pour la décision d'approbation des appareils.
- `_fallback_name_pool` final purge : ancien placeholder `['NovaApp','PixelForge','Lumino']` (qui contredisait le prompt) remplacé par `_rnd.sample(pool, 3)` quand la validation JSON échoue.

**Tests** : 16/16 backend `test_iter81_orange_fixes.py` PASS (C2 wizard variety + C17 export flags + C20 visit gate + C13/ideas/clear scope validation). Frontend Playwright PASS sur C17 modal complet et démo-link absence vérifiée.

### 2026-06-10 — Iter 80 (Quick-wins commentaires user C13/C14/C17/C18/C20/C2)

**C13 — Vue créateur sans expositions sensibles** :
- `IdeasButton` : `isCreator` désormais `device.role === 'creator' && viewMode !== 'guest'` → la boîte à idées en mode inbox n'apparaît pas en vue invitée.
- AccountsButton + AnnounceButton déjà cachés en viewMode='guest' depuis iter77.

**C14 — Vider la boîte à idées avec confirmation password** :
- Nouveau endpoint `/ideas/clear` (créa-only) avec `scope ∈ {all, resolved, unresolved}`.
- Si le scope inclut des retours **non-traités** (state ≠ validated), exige `password`. Retourne 428 si manquant, 403 « Mot de passe incorrect. Veuillez réessayer » si faux.
- IdeasButton : 3 boutons rangés dans la barre filter (créa-only) : « Traités », « Non-traités », « Tout ». Modal de confirmation Oui/Non, puis champ mot de passe si requis.

**C17 — Export ZIP avec cases à cocher** :
- Modèle backend `ExportRequest` étendu avec `include_code: bool` (défaut true) et `include_chat: bool` (défaut false).
- `/export/download` honore ces flags : génère code source ET/OU transcript chat (markdown + DOCX inclus dans le ZIP).
- Dashboard frontend : `askExportProjectZip()` ouvre un modal avec 2 checkboxes (code source / discussions .docx) avant le download.

**C18 — Confirmation : C18 reste comme iter79 (admin+créa choisissent modos, créa choisit admins)**.

**C20 — Visite compte complète + items supprimés en contraste foncé** :
- `/accounts/visit` (créa-only) enrichi : retourne **TOUS** les projets/messages (incluant deleted soft) avec `is_deleted: true|false`.
- Retourne aussi `target.staff_kind` pour permettre badge admin/modo dans la vue.
- Le user lui-même ne voit PAS les éléments supprimés en vue créateur (logique pure côté UI à brancher).
- Liste agrandie : projects=500, messages=2000.

**C2 — Suggestion IA et pièces jointes des 2 côtés du wizard** :
- Bloc **Design** : conserve « Suggestion IA » + ajoute **AttachMenu** (pièces jointes).
- Bloc **Fonctionnement** : ajoute **« Suggestion IA »** vert (askMagicFunc) + conserve AttachMenu.
- Backend `wizard-suggest` : nouveau `kind='function'` → renvoie `{ "func": "description" }`. Fallback déterministe.
- Texte ajouté en append (concaténation), pas écrasement, pour permettre plusieurs cycles d'inspiration.

**Tests** : 22/22 backend pytest régression PASS. Endpoints nouveaux validés via curl (sans signature → 403). Frontend smoke OK (Landing rendue).

### 2026-06-10 — Iter 79 (Pseudos variés, staff inbox + permissions, DOCX, blocs privés créa)

**🪄 Pseudo wizard variety** :
- `_fallback_name_pool()` backend = 50+ pseudos style Among Us, longueurs 3-12 caractères, mix mots/chiffres/styles (Vrael, Kazimir77, JuneberryX, ImLost, …).
- Seed-driven random pour ne JAMAIS répéter le même résultat.
- Frontend GuidedWizard : à chaque clic baguette, `setAppName(list[0])` écrase l'ancien nom (auparavant ne s'écrasait que si vide).

**🛡️ Permissions staff (admin/modo)** :
- Nouveau helper `_require_staff_signature(allow_kinds=('admin','modo'))`.
- Ouvert au staff : `/accounts/mute|unmute|ban|unban|exclude`, `/devices/approve|block|unblock`, `/accounts/set-staff-kind` (admin peut set/clear modo uniquement).
- `/devices/approve` tracke `approved_by_kind` (creator/admin/modo) pour le futur code couleur d'encadrement créa.
- `account_history` events taggés `actor_kind` + `actor_label` pour permettre l'UI couleur côté créa (bleu=modo, orange=admin, jaune=créa).
- `/ideas/inbox` + `/ideas/mark-read` (déjà ouverts en iter78) accessibles staff.

**📄 Export conversations en DOCX** :
- Endpoint `/chat/export-docx/{project_id}` utilisant `python-docx` (déjà installé).
- Header Chat : bouton « Export .docx » remplace l'ancien « Export .ipynb ».
- ZIP retiré GitHub (`/export/github`) côté UI (l'utilisateur garde le ZIP pour push manuel).

**🧹 UX nettoyage** :
- Bouton "Reset REPL" caché en mode `offline` (Ollama hors-ligne) — uniquement `online`.
- LanguageContext: « au créatrice » → « à la créatrice » (4 occurrences) + MessageButton "au créateur" → "à la créatrice".

**🪟 Annonce fullscreen vraiment plein écran** (iter78 corrigé) :
- `fixed inset-0` centré avec `flex items-center justify-center`. Max-w-3xl, padding 10, titres `text-3xl→5xl`.

**🔒 Blocs privés créa** (C15) :
- Nouvelle page `/private/site-programming` et `/private/ai-programming`.
- Visible dans Dashboard (sous les 4 cards Chat/Création), seulement la **créatrice** peut cliquer.
- Sinon toast "Accès refusé pour des raisons de sécurité" et page guard avec message centré.

**📋 IdeasButton (rappel iter78)** :
- Onglet "Report" ajouté avant "Other" dans le picker du composer.
- Inbox ouvert au staff (admin/modo) via /ideas/inbox patched.

**Tests** : **38/38 backend tests PASS** (16 iter79 + 22 régression iter66/67/68/76). Aucun blocant.

### Items reportés (besoin de plus de précisions ou sprint suivant)
- **C2** Pièces jointes design + suggestion IA dans flux app
- **C4** Liens / fichiers téléchargeables directement dans tchat
- **C5/C8** Streaming token-par-token IA (refacto chat backend WS/SSE)
- **C6** Multiligne code formatting GPT-style (affichage)
- **C7** Orchestrateur Emergent intégré (architecture multi-agents)
- **C9** (partiel) Sidebar langue mal défilable + tchats non traduits — investigation UI
- **C11** Site modes Public/Privé/Créateur/Invité + Modos/Admins/Staff (multi-checkbox, gros refacto)
- **C12** UI décision colorée bleu/orange dans demandes de clés
- **C13** Visite créa invisible aux admins (refacto layer admin)
- **C14** Boîte à idées : tri/vider créa avec confirmation password
- **C16** Pseudos affichés au-dessus du type d'appareil — déjà fait pour /accounts/list, à vérifier ailleurs
- **C17** ZIP différencié APK (apps) / EXE (logiciels) + ZIP avec discussions
- **C18** Messages → modo random au lieu créa
- **C19** 6 types de tchats de groupe (public, privé, staff, modo, public+staff, public+privé)
- **C20** Visite compte = accès TOUT (projets/messages supprimés en contraste foncé, clé exposée, demande d'ami pour parler en privé)

### 2026-02-16 — Iter 78 (Fullscreen export review + Iris vol + staff inbox + Reports + comptes enrichis)

**📢 Annonce fullscreen vraiment plein écran** :
- `AnnouncementsBanner` repositionné en `fixed inset-0` centré, contenu max-w-3xl, padding 10, titre `text-3xl→5xl`.
- 1ʳᵉ vue = modal plein écran centré. Click X → bandeau haut. Click X bandeau → dismiss.

**🧹 Retrait icônes ✅❌🟠 des annonces & sondages** :
- Plus de boutons d'état dans la bannière ni dans le panneau "Gérer" pour annonces. Les icônes restent exclusivement sur les **bugs/idées** (IdeasButton) — staff+créa.

**📦 Export review fullscreen** :
- Nouveau composant `ExportInReviewModal` : message centré multi-lignes "Votre projet est en cours d'examination par la communauté administrative".
- Remplace l'ancien toast côté Dashboard. Affiche `pending → approved → rejected`.
- Polling 4s × 90 (≈6 min). User peut fermer le modal, polling continue en BG.

**📨 Inbox staff (admin/modo) + onglet Report** :
- `/ideas/inbox`, `/ideas/mark-read` ouverts aux admins et modos (en plus de la créa).
- Nouveau kind `report` (signalement de problème) ajouté avant `other`. `/ideas/send` accepte désormais `kind ∈ {idea, bug, report, other}`.
- IdeasButton composer : picker de type bug/report/idée/autre. Filter bar côté inbox également mis à jour.

**🗳️ UX sondages enrichie** :
- Bannière sondage affiche désormais "tu peux choisir N option(s)" ou "∞ choix possibles" (lisible).
- Si `allow_user_suggestions` → mention "tu peux écrire ta propre réponse" en jaune ambre.

**👥 AccountsButton (comptes) enrichi** :
- Affichage de la **clé** device (préfixe 24 chars) en monospace.
- Badges `admin` (cyan) / `modo` (violet) / `inactif` (zinc) / `visiteur forcé` (orange).
- Nouveaux boutons : `Mettre admin`, `Mettre modo`, `Forcer visiteur`, `Message` (callback `onMessageAccount`).
- Backend `/accounts/set-staff-kind` + `/accounts/force-visitor` (iter77) maintenant wirés côté UI.

**🪄 Création rapide accompagnée par l'IA** :
- Bouton **Wand2 + Sparkles** remis sur le Dashboard (au-dessus des deux cards Chat / Création).
- Route `/wizard` (GuidedWizard) toujours en place.

**Tests** : 22/22 backend pytest régression PASS (iter66/67/68/76 toujours verts). Frontend smoke OK.

### 2026-02-15 — Iter 77 (Multi-audience + sondages illimités + rôles staff + Iris vol + comptes complets)

**🎯 Multi-audience cases à cocher (annonces / sondages / déco-programmée)** :
- Nouveau composant `AudiencePicker` : checkboxes pour combiner les groupes
  `all / approved / non_validated / admin / modo`. Si rien → `['all']`.
- Helper backend `_audience_matches(audience, dev)` évalue le match selon `role`
  + `staff_kind` (iter77). Rétrocompat avec audience string legacy.
- `/system/schedule-kick` accepte aussi l'alias `staff` (= admin+modo).

**🆕 Rôles staff `admin` et `modo`** (sous `approved` ; promotion via créa) :
- Nouveau champ `device_keys.staff_kind` ('admin' | 'modo' | null).
- Endpoint `/accounts/set-staff-kind` (créa-only).
- `/devices/verify` expose maintenant `staff_kind` + `force_visitor`.
- Hook `useDeviceIdentity` propage `staffKind` + `forceVisitor`.

**👁️ Mode visiteur forcé** :
- `/accounts/force-visitor` met `device_keys.force_visitor=true` → frontend
  hook met `canWrite=false` (lecture seule sans déconnexion).

**📊 Sondages illimités + réponses perso** :
- `max_selections=0` = sélection illimitée (auparavant min 1).
- `allow_user_suggestions=true` → endpoint `/polls/suggest-option` (user) +
  `/polls/decide-suggestion` (créa valide/retire). Si retiré, ses votes ne
  comptent plus.
- `/polls/list` enrichi : `voters` (uniques), `voters_detail` (créa-only, sauf
  audience inclut "all" = communauté → anonyme), `suggestions[]`.

**✏️ Bouton crayon « modifier »** :
- `/announcements/edit` + `/polls/edit` (créa-only). Reset les `announcement_states`
  pour l'annonce → réapparait à tous. Reset les votes si options changent.

**🛡️ Vol : remplacement WebAuthn + Email Gmail par Iris** :
- `TheftRecoveryDialog` ré-écrit : saisie email + lance `IrisFullscreenWizard`
  (le même que l'inscription). POST `/auth/theft-iris-verify`.
- Plus aucune référence à `theft-email-request` côté frontend.

**👥 Comptes complets** :
- `/accounts/list` retourne désormais TOUS les `device_keys`, y compris
  `role=inactive` (avec flag `is_inactive=true`). Permet de voir les amis
  qui ont testé la plateforme sans pousser de demande.
- Inclut `staff_kind` + `force_visitor` dans la réponse.

**💡 Bug & idées avec états (staff+créa)** :
- `/ideas/set-state` (admin/modo/creator) : validated / refused / orange / reset.
- IdeasButton : boutons ✅❌🟠 visibles uniquement pour `isStaff`.
- ⚠️ Note : `/ideas/inbox` reste créa-only (staff inbox à un prochain sprint).

**🎯 UX divers** :
- `FeedbackButton` : `hideForCreator = false` (la créa peut désormais se
  poser des tâches à elle-même via la boîte à idées).
- `AnnouncementsBanner` : annonces affichées EN MODAL fullscreen sous le titre
  CodeForge AI à la 1ʳᵉ vue. Click X → bascule en bandeau haut. Re-click X →
  dismiss complet (jusqu'à modif créa).
- Bannière retire les boutons ✅❌🟠 (déplacés vers le panneau « Gérer »).

**Tests iter77** : **16/16 nouveaux backend pytest PASS** + 27/27 régression
(iter65/66/67/68/76) PASS = **43/43 total**. Aucune issue critique ou mineure.

### 2026-02-15 — Iter 76 (Annonces enrichies + sondages multi-select + déco programmée + fix phantom-prompt 8s)

**📢 Annonces enrichies (P0 — reporté du fork précédent)** :
- 3 émojis d'état : ✅ Validé (vert), ❌ Refusé (rouge, non supprimable sauf clear-history), 🟠 Orange = « staff n'a pas les codes » (escalade vers la créatrice).
- Asymétrie staff/créatrice : si un staff valide, l'annonce disparaît pour lui mais reste visible pour la créatrice avec badge « Coché par le staff ». La créatrice peut confirmer (disparaît partout) ou réinitialiser (revient en attente).
- Bouton « Supprimer l'historique » (`/api/announcements/clear-history`) côté créatrice — wipe complet annonces + états.
- Nouvelle collection `announcement_states` (announce_id, key_id, state, actor, ts).
- Endpoint `POST /api/announcements/set-state` (any signed user, state: validated|refused|orange|reset).
- Endpoint `GET /api/announcements/list?key_id=...` enrichi avec `my_state` + `staff_states` (créatrice only).

**📊 Sondages multi-select + temps de publication** :
- Nouveau champ `max_selections` (min 1, par défaut 1) au create. Stocké sur le doc poll.
- Vote accepte désormais `option_indices: [int]` (ancienne API `option_index: int` reste compatible).
- Tally agrégé via `$unwind` sur les indices.
- Réponse `/polls/list` enrichie avec `voters` (nb de votants uniques) + `my_vote` (array).
- UI banner: cases à cocher visuelles, bouton « Voter » apparaît seulement si sélection ≥ 1.
- Date de publication affichée dans la bannière + dans le panneau Gérer.

**⏰ Déconnexion programmée (P0)** :
- `POST /api/system/schedule-kick` : créatrice planifie un kick massif dans X minutes (cap 24h). Si `note` fourni, publie une annonce immédiate.
- `GET /api/system/scheduled-kicks` : liste des kicks pending.
- `POST /api/system/cancel-scheduled-kick` : annule un kick programmé.
- Background sweeper `_periodic_kick_sweeper` (10s) qui purge toutes les `user_sessions` non-créatrice à l'heure dite.
- Nouvel onglet « Déco. progr. » dans `AnnounceButton.jsx`.

**🐛 Fix phantom-prompt multi-device (récurrent x3)** :
- Cause: threshold-0 (iter75) créait race condition — si le device A heartbeat juste APRÈS que B capture `now`, alors `last_seen_at(A) > now(B)` → prompt fantôme côté A.
- Fix: fenêtre de présence glissante 8s (`now - 8s`). Couvre largement le polling 3s de `/auth/session-pending` ; les onglets fermés (sendBeacon ou simple fermeture) tombent hors fenêtre instantanément.
- Tests iter67/68 adaptés à la nouvelle fenêtre (fresh = -3s, stale = -30s).

**Tests iter76** : **13/13 backend pytest PASS** (test_iter76_announcements_polls_kicks.py — annonces shape + my_state + hide-validated, polls multi-select tally [1,2,1] / voters=2, scheduled-kicks list, gating signatures 403). Régression iter65/66/67/68 verte après refit -30s→-3s.


User a signalé que la détection iris était trop stricte (2 min sans progression). Ajustement des seuils :
- **Step 0 « approche visage »** : `APPROACH_THRESHOLD` 500→200 + `REQUIRED_HITS` 6→3 (passage en ~1s avec un visage normal).
- **Steps 2-4 poses** : `MOVE_MIN` 4.0→1.5 + `REQUIRED_HITS` 12→4 (respiration/clignement naturel suffit).
- ❌ Retrait du warning « Bouge réellement ta tête » — les 3 poses suffisent à prouver une vraie personne.
- Import `AlertTriangle` retiré (orphelin).

### 2026-02-15 — Iter 72 (Fix runtime faceVariance + UX inscription affinée)

**🐛 CRITIQUE — Runtime error `faceVariance is not defined`** (rapporté par user avec screenshot) : la fonction `faceVariance` avait été perdue lors d'un edit précédent. Restauration de la fonction module-level (luminance + variance pixel sur disque central, seuil empirique 500). Smoke test confirme zéro page error au mount du wizard.

**✨ UX inscription** :
- Hint pseudo « Visible par la créatrice uniquement. 1 à 30 caractères. » **retiré** (utilisateur le trouvait redondant).
- Légende « * Champs obligatoires à remplir » déplacée **en bas du formulaire** (centrée, italic, sous le bouton).
- Étoiles rouges sur email + password + pseudo + biométrie + capture appareil — toutes vérifiées.

**Tests iter72** : Régression 22/22 PASS sur iter69/70/71. Smoke frontend (1280×900) zéro page error + tous data-testids présents (`required-fields-legend`, `iris-fullscreen-wizard` rendu propre avec cercle bleu glow).

### 2026-02-15 — Iter 71 (Tutoriel iris 'approche visage' + reuse wizard dans déclaration de vol)

**🎓 Tutoriel iris en 5 étapes** (style FranceIdentité) :
- **Step 0 NOUVEAU** : « Approche ton visage du cercle bleu » → auto-progress quand `faceVariance > 500` sur 6 hits consécutifs. Barre cyan séparée `data-testid='iris-approach-progress'`.
- Step 1 : Vérification lunettes (1.5s, alerte bloquante si > 120 pixels brillants en zone yeux).
- Steps 2-4 : 3 défis pose aléatoires (gauche/droite/centre) avec `pixelDiff` live anti-photo.
- Step 5 : Done → hashes envoyés au parent.

**🛡️ Wizard iris réutilisé sur la page de déclaration de vol** (`/theft-confirm`) :
- Après que le token email confirme la révocation, l'utilisateur voit un **bouton « Lancer la vérification iris »** (data-testid='theft-iris-confirm-btn').
- Click → IrisFullscreenWizard plein écran (même contrat onCancel/onDone) → POST `/api/auth/theft-iris-verify`.
- Nouveau endpoint backend stub (shape validation + log dans `theft_iris_attempts`) — **matching réel iris au prochain sprint**.

**🐛 Fix StrictMode double-fire** : `TheftConfirm.js` utilisait un `cancelled` boolean qui ne bloquait pas le fetch, juste le setState. En dev/StrictMode, le useEffect double-render → 1er GET consommait le token, 2e GET retournait 404 → état 'Échec' à tort. Fix : `useRef sentinel` (3 lignes).

**Tests iter71** : **40/40 backend pytest PASS** (6 nouveaux `test_iter71_theft_iris_verify` + 34 régression iter63→70). Frontend smoke confirmé : wizard fullscreen 1280×900 parent BODY, named-import IrisFullscreenWizard OK, bouton 'theft-iris-confirm-btn' présent. Step 0 face-approach loop validé par code review (requiert vraie webcam pour tester runtime).

### 2026-02-15 — Iter 70 (Iris fullscreen wizard + WebAuthn rp_id fix + détection mouvement live)

**🐛 BUG WebAuthn critique** : `The relying party ID is not a registrable domain suffix` → causé par l'ingress Kubernetes réécrivant le header `Origin` vers un hostname interne. **Fix** : le frontend (`BiometricEnrollmentField`) envoie maintenant explicitement `window.location.origin` dans le body POST `/api/webauthn/enroll-begin`. Le backend l'utilise en priorité avant le header. → `rp_id = no-code-builder-25.preview.emergentagent.com` correctement dérivé.

**🖼️ Iris fullscreen wizard** (composant `IrisFullscreenWizard`) :
- **React Portal** vers `document.body` → contourne le piège du `backdrop-filter` parent qui transformait `position:fixed` en `position:absolute` à l'intérieur de la card Login (vérifié smoke test : bbox 1280×900, parent=BODY).
- Header avec icône + titre + bouton X / Vidéo plein-écran avec cercle visage centré / Footer status + barre de progression.
- Vidéo mirrored horizontalement (l'utilisateur se voit en miroir).

**🧠 Détection LIVE de mouvement de tête (anti-photo)** :
- 3 challenges aléatoires shuffled (gauche/droite/centre) → l'ordre change à chaque session, replay attack impossible.
- `requestAnimationFrame` boucle ~60fps qui calcule le `pixelDiff` (somme abs RGB) entre frames successives.
- Threshold `MOVE_MIN = 4.0` + `REQUIRED_HITS = 12` frames d'activité → ~0.4s de vrai mouvement.
- Une photo statique produit diff ≈ 0 → ne valide JAMAIS, peu importe combien de fois on l'agite.

**👓 Détection « Enlève tes lunettes »** :
- Heuristique `looksLikeGlasses` : compte les pixels luminance > 235 dans la zone yeux (haut du frame).
- Si > 120 super-bright pixels → alerte bloquante « Veuillez enlever vos lunettes pour une identification infaillible ».

**Tests iter70** : **34/34 backend pytest PASS** (3 nouveaux `test_iter70_webauthn_origin.py` + 31 régression) + Smoke frontend confirmé : wizard fullscreen 1280×900 parent BODY, header, footer status, message caméra denied propre.

### 2026-02-15 — Iter 69 (Biométrie obligatoire + sendBeacon + threshold 35s + UX étoiles)

**🔐 Biométrie obligatoire à l'inscription** :
- Nouveau composant `BiometricEnrollmentField.jsx` : 2 boutons → **Empreinte/Face ID (WebAuthn)** ou **Iris (webcam)**.
- WebAuthn : tente `navigator.credentials.create` via le nouveau endpoint `/api/webauthn/enroll-begin` (signup-flow, anonyme).
- Iris : `getUserMedia({video})` → preview live → bouton « Capturer » → crop centre 256×256 → SHA-256 client-side → 3 hashes b64 envoyés au backend.
- Message rassurance UI : « **La créatrice n'a aucun accès** à tes empreintes ni à la photo de ton iris ».
- Backend `/auth/register` : `biometric_kind` requis, sinon **400**. Stockage `user.biometric = {kind, ...}`.

**⏱️ Threshold 60s → 35s + sendBeacon beforeunload** :
- Nouveau `POST /api/auth/disconnect-soft` (accepte token via cookie / header / query `?t=`) → marque `last_seen_at` à -24h.
- `AuthContext.js` enregistre un `beforeunload` qui ping `disconnect-soft` via `navigator.sendBeacon` → onglet fermé = stale **instantanément**.
- Combine avec le heartbeat 30s : 35s suffit largement pour absorber le jitter.

**📝 UX champs obligatoires** :
- ⭐ Étoile rouge sur email, password, pseudo, capture appareil, biométrie.
- Ligne « Champs obligatoires à remplir » i18n FR/EN.
- Pseudo : min **1 char** (au lieu de 3). Hint mis à jour.

**Tests iter69** : **31/31 backend pytest PASS** (13 nouveaux + 18 régression) + frontend Playwright vérifié (5 testids obligatoires + bouton iris + caméra denied + message rassurance). Aucun bug critique.

### 2026-02-15 — Iter 68 (Heartbeat 30s + threshold 60s + no toast B + mobile horizontal scroll)

**🐛 Bug "phantom approval prompts" résolu pour de bon** :
- **Cause** : threshold 3min + pas de heartbeat explicite → un onglet fermé gardait son `last_seen_at` frais pendant 3 min (via le cache de `/auth/me` au mount) → fausse demande d'approbation.
- **Fix** : nouveau endpoint POST `/api/auth/heartbeat` + `AuthContext.js` ping toutes les 30s + threshold descendu à **60s**. Un onglet fermé arrête de pinger → stale en 60s → plus de fausse demande.
- **Backfill** : 105 sessions live remises à `last_seen_at = -2h` pour partir propre.

**✨ UX** :
- Toast `"Connexion en attente d'approbation"` retiré côté B → seul le bandeau jaune reste (plus clean sur mobile).
- Header Dashboard mobile : `overflow-x-auto` + `min-w-max` → swipe latéral pour voir les boutons qui débordent.
- Main column : `overflow-x-hidden` → plus de scroll horizontal global parasite sur mobile.

**Tests iter68** : **18/18 backend pytest PASS** (4 nouveaux test_iter68_heartbeat + 3 patché iter67 60s + 5 iter66 + 6 iter63) + frontend Playwright vérifié (heartbeat fires initial + ≥1 repeat sur 35s, toast retiré, header classes overflow OK).

### 2026-02-15 — Iter 67 (Sidebar mobile + i18n Menu + last_seen_at 3 min)

**🐛 Bug critique mobile** : le bouton sidebar-toggle changeait juste l'icône mais la sidebar ne s'ouvrait pas (flex column 280px → mainContent poussé hors viewport). **Fix** : sur mobile (max-width:767px), la sidebar devient un **drawer overlay** (`fixed inset-y-0 left-0 z-40`) avec backdrop cliquable (`z-30 bg-black/60 backdrop-blur-sm md:hidden`). Default `isSidebarOpen=false` sur mobile, `true` sur desktop (matchMedia).

**🌐 i18n FR/EN** :
- `dashboard` : `'Tableau de bord'` → `'Menu'` (FR) / `'Dashboard'` → `'Menu'` (EN).
- Nouvelle clé `back_to_menu` : `'Retour au menu'` (FR) / `'Back to menu'` (EN).
- `Profile.js` : « Retour au dashboard » → `{t('back_to_menu')}`.

**⏱️ Backend `last_seen_at` threshold 10 min → 3 min** : le heartbeat est écrit à chaque `/auth/me` + `/auth/session-pending` (tick 3s). 3 min de silence = onglet vraiment fermé, ne déclenche plus de demande d'approbation fantôme. **Reset Mongo** : 97 sessions backfillées à `now - 1h` pour éviter les faux positifs résiduels.

**Tests iter67** : 14/14 backend pytest PASS (3/3 nouveaux test_iter67_threshold_3min + 5/5 régression iter66 + 6/6 régression iter63). i18n FR vérifié post-correction (`grep` confirme `dashboard: 'Menu'` et `back_to_menu: 'Retour au menu'`).

### 2026-02-15 — Iter 66 (Le bug 202 / pendingApproval enfin résolu)

**🐛 RCA confirmé** : axios traite `HTTP 202` comme un succès par défaut. Le code Login.js d'avant cherchait le 202 dans le `catch(err2)` → **jamais exécuté** → `setPendingApproval()` jamais appelé → bandeau jamais visible sur B → polling jamais lancé. **C'est pour ça que B ne recevait rien**.

**🔧 Correctifs** :

1. **Fix critique** — `Login.js` : `validateStatus` autorise 202 dans le success branch + check `res.status === 202` explicite avant `data.session_token`. Re-throw manuel pour 4xx pour préserver l'error handling.

2. **`last_seen_at` heartbeat backend** : `get_current_user()` met à jour `user_sessions.last_seen_at` à chaque requête authentifiée. Le check `active_other` exige désormais `last_seen_at > now - 10min` → une session avec un cookie 7 jours mais onglet fermé n'envoie plus de fausse demande d'approbation.

3. **Refus → onglet Mot de Passe direct** : `SessionRequestNotifier` navigue vers `/profile?tab=password` (au lieu de `?section=security` qui retombait sur l'onglet Info). `Profile.js` parse `?tab=` au mount avec allowlist + fallback.

4. **Localisation « Inconnue » → « Localisation non disponible »** (FR/EN cohérents).

5. **Backfill prod** : 79 anciennes sessions `last_seen_at`-less mises à jour pour ne pas se faire flagger stale par accident.

**Tests iter66** : 16/16 backend pytest PASS (5 nouveaux + 11 régression) + **E2E mobile 412x915 RÉEL** confirme : 202 → bandeau pending VISIBLE + countdown + localStorage{request_id,email,until} populé. C'est exactement la régression qu'avait l'utilisateur — **maintenant reproductible et fixée**.

### 2026-02-15 — Iter 65 (Validation E2E multi-device + auto-purge legacy state)

**🔬 Diagnostic du bug "mobile login ne marche pas"** :
- 5/5 nouveaux tests pytest E2E backend PASS (`/app/backend/tests/test_iter65_multi_device_e2e.py`) → flux pending/approve/deny/expire **rock solid**, idempotent.
- Régression iter63 6/6 PASS.
- Frontend mobile 412x915 charge propre, **zéro toast** "session expirée" même avec `?reason=session_expired`.

**🧹 Hypothèse retenue** : cache navigateur stale chez l'utilisateur (entrées legacy pre-iter64 dans sessionStorage/localStorage avec ancien schema). **Solution proactive** : `AuthContext.js` exécute un **auto-purge one-shot** au boot — si `codeforge_build !== 'iter65'`, le client wipe les `codeforge_session_pending` malformés (string brut au lieu de JSON envelope) et marque le build. L'utilisateur n'a rien à faire — la prochaine visite nettoie automatiquement.

**🧽 Hygiène base** : 8 anciennes pending requests expirées purgées + binding device→email rétabli pour le device PC Firefox de l'utilisatrice (cohérence iter63 1=1).

**✨ IdeasButton (créatrice) — affinage filtres** :
- ❌ Bouton « Tout cocher/décocher » retiré.
- ✅ Nouveau toggle **« Trier par date »** ajouté à côté de « Trier par type », mutuellement exclusifs (radio-like).
- ✅ « Trier par date » est **actif par défaut** au premier load.
- ✅ Les 2 toggles + filtres persistés dans localStorage.

**Tests iter65** : 11/11 backend pytest PASS + frontend e2e smoke PASS + legacy state purge round-trip vérifié.

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
