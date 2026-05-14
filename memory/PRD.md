# CodeForge AI - PRD

## Statut : VERSION P3 — STABLE & SÉCURITÉ RENFORCÉE (Mai 2026)

### 14 Mai 2026 — Session 44 (suite 3) — Identité d'appareil cryptographique + modes du site
- **🔐 Identité cryptographique par appareil (WebCrypto ECDSA P-256, non-extractable)** :
  - `/app/frontend/src/lib/deviceIdentity.js` : génère une paire ECDSA P-256 dans le navigateur avec `extractable:false`. La clé privée est stockée comme `CryptoKey` dans IndexedDB → JS ne peut PAS l'exporter en bytes bruts (closest browser-level "secure element"). La clé publique (JWK x,y) sert d'ID partageable.
  - `key_id = sha256(canonical_jwk)` — identifiant public stable. Affiché dans le DeviceManager.
  - Concurrence sécurisée : `_ensurePromise` + `_attestPromise` en module-cache empêchent la double-génération de paires (React StrictMode).
  - `signNonce()`, `attestDevice()`, `withCreatorProof()`, `exportPublicKeyShareCode()`, `parsePublicKeyShareCode()` — API complète.
- **⚙️ Backend `/app/backend/device_auth.py` + endpoints server.py** :
  - Verify signature ECDSA P-256 (P1363 64 bytes → DER pour `cryptography`).
  - `POST /api/devices/register` (public) : idempotent, dedup auto-collapse, 1er device → role=`creator`, suivants → `pending`.
  - `POST /api/devices/challenge` + `POST /api/devices/verify` (public) : nonce 32-bytes URL-safe, single-use.
  - `GET /api/system/site-mode` (public) : retourne mode courant.
  - `PUT /api/system/site-mode` (creator-only) : preuve signature requise.
  - `POST /api/devices/list|approve|revoke|disconnect|promote-creator|add-by-key` (creator-only).
  - Index unique MongoDB sur `device_keys.key_id`.
- **🎚️ 4-modes du site (Public / Privé / Créateur / Invité)** :
  - `Public` : tout le monde accède (paramètre actuel).
  - `Privé` : seuls `creator` + `approved` peuvent s'authentifier.
  - `Créateur` : seuls les `creator` peuvent s'authentifier (utile pour maintenance).
  - `Invité` : tout le monde peut explorer (lecture seule, à compléter avec gates UI).
- **🖼️ UI** :
  - `SiteModeBadge.jsx` (Landing + Login) : dropdown 4-options pour créateurs, badge readonly pour les autres. Mode actuel : globe/lock/crown/eye-off.
  - `DeviceManager.jsx` (modal accessible via `UserMenu → Autres identifiants`) : 
    * Pour TOUS : code de partage de leur clé publique (à donner au créateur hors-ligne).
    * Pour CRÉATEUR : liste tous les devices avec rôle + dernière connexion, boutons Approuver/Créateur (avec mot de passe)/Déconnecter/Supprimer + champ "Ajouter par clé".
  - `useDeviceIdentity()` hook : auto-attestation au mount, expose `keyId, role, siteMode, canAccess, refresh`.
- **📧 Email auto-prefilled per-device** :
  - Login pré-remplit l'email du dernier compte utilisé sur CET appareil uniquement (clé localStorage `device_email:<keyId>` — autres appareils n'y ont pas accès).
  - Mot de passe JAMAIS mémorisé.
  - Erreurs login déjà spécifiques (`login_password_wrong`, `login_email_unknown`) — pas de message générique.
- **📚 Tutoriel** : nouvelle slide #7 "Identité d'appareil & modes du site" ajoutée à `Discover.js` (mock visual ECDSA + grille des 4 modes). Traductions FR/EN complètes (`d_t7/d_b7` + `d_t8/d_b8`). Autres langues : fallback EN.
- **🧪 Tests live** : script Python avec génération ECDSA + sign + verify confirme register/challenge/verify/set-site-mode → 200 OK. Screenshot Landing confirme dropdown créateur 4-modes apparaît, autres appareils voient le badge readonly.
- **Limitations connues (non bloquantes)** :
  - Pas de notification temps-réel (SSE/WebSocket) quand un nouveau pending arrive — le créateur doit ouvrir DeviceManager manuellement.
  - Mode "guest" → enforcement UI partiel : il faut désactiver les boutons d'action côté frontend si role !== creator/approved.
  - Email à elsa.barroca2@gmail.com pour notifications : non câblé (Resend nécessite API key utilisateur).
  - Autres langues d_t7/d_b7/d_t8/d_b8 : fallback EN actif (à traduire dans une prochaine passe).


### 13 Mai 2026 — Session 44 (suite 2) — Live Preview iframe + Cloner + Partage public viral + Détection Ollama + Arabe étendu
- **🖼️ Live Preview iframe inline** dans le Dashboard : dès qu'un projet web avec `generated_code` est sélectionné, un panneau `live-preview-panel` apparaît sous le header, avec iframe sandboxée (`allow-scripts allow-forms allow-popups allow-same-origin`), boutons "Ouvrir dans un onglet" et "✕ fermer", badge "Public" si partagé.
- **🧬 `POST /api/projects/{id}/duplicate`** : clone un projet (nouveau `project_id`, nom suffixé "(copie)", reset `is_public/share_slug`). Bouton "Cloner ce projet" ajouté au menu contextuel Dashboard (`project-ctx-duplicate`, icône `Copy` ambre).
- **🌐 Partage public viral** :
  - `POST /api/projects/{id}/share {enable: bool}` → génère/désactive un slug ASCII unique. Renvoie URL absolue (utilise `FRONTEND_URL` ou `REACT_APP_BACKEND_URL` côté backend).
  - `GET /api/share/{slug}` (PUBLIC, sans auth) → renvoie metadata + files. Champs sensibles (`user_id`, `ai_source`) projection-exclus.
  - `GET /api/share/{slug}/preview` (PUBLIC) → HTML rendu sandbox.
  - Route frontend `/share/:slug` → composant `SharedPreview.jsx` : bandeau sticky avec nom/desc + CTA jaune "Crée la tienne" → boucle virale.
  - Menu contextuel : "Partager publiquement" / "Désactiver le partage" (`project-ctx-public-share`, icône `Share2`). Slug + URL auto-copiés au presse-papier avec toast actionnable.
- **🤖 Détection auto Ollama** : `GET /api/system/ollama-status` (public, sans auth) ping `localhost:11434/api/tags` avec timeout 1.5s. `ModelPicker.jsx` appelle cet endpoint au mount → grise/disable les modèles hors-ligne avec bandeau "⚠ Moteur d'IA local non détecté" quand Ollama inaccessible.
- **🇸🇦 Arabe étendu** : bloc `ar` enrichi avec les clés Dashboard (`dashChat`, `dashCreate`, `dashWhatToDo`, `dashChatDescOn`, `dashCreateDescOn`, badges On/Off, hints, infos en/hors ligne, stats Landing). Fallback en anglais pour les clés résiduelles.
- **🧪 Tests** : `testing_agent_v3` iter_44 → **11/11 GREEN** sur backend live. Regression file créé : `/app/backend/tests/test_iter44_new_endpoints.py`. Frontend validé visuellement (screenshot `/share/<slug>` parfait).
- **Limites supprimées comme demandé** : la cascade itère sans `max_attempts` (8 modèles multi-providers). Toutes les nouvelles fonctionnalités sont sans cap (pas de quota duplicate, share, etc.).


### 13 Mai 2026 — Session 44 (suite) — Arabe + Bouton ZIP fusionné GitHub
- **🇸🇦 Langue arabe ajoutée (16ème langue)** :
  - Bloc de traductions `ar` créé dans `LanguageContext.js` (translations communes + login + dashboard).
  - Ajout `ar` dans `SUPPORTED_LANGS` (drapeau 🇸🇦, label `العربية`).
  - Ajout `ar` dans `TRANSLATED_LANG_NAMES` pour les 16 langues × 16 langues : ex. "العربية (Arabic)" en anglais, "العربية (Arabe)" en français, etc.
  - **Mode RTL automatique** : déjà supporté via `RTL_LANGS = ['ur','ar','he','fa']` dans `LanguageContext.useEffect`. Test live → `dir="rtl" lang="ar"` appliqué, layout entièrement inversé.
- **🐙 Bouton ZIP → ZIP + GitHub** (header Dashboard `export-source-btn`) :
  - Le bouton "ZIP" devient "**ZIP + GitHub**" et déclenche en parallèle (1) téléchargement local `.zip` (2) push automatique du projet sur le repo GitHub configuré (`projects/<slug>-<id>/`).
  - Toast d'action : "Sauvegardé sur GitHub" avec bouton "Ouvrir" → lien direct vers le dossier sur github.com.
  - Push GitHub silencieux en cas d'échec (le ZIP local reste prioritaire).
  - **Bugs backend corrigés** :
    - URL `/contents/{path}` désormais `urllib.parse.quote()`-encodée → résout les 404 sur chemins avec accents/espaces.
    - Sanitization du dossier : ASCII-only via `unicodedata.NFKD` (ex. "réservation" → "reservation"), évite les caractères problématiques côté GitHub.
    - `pushed/failed` correctement séparés (auparavant `pushed.append` se faisait même en cas d'échec).
    - `.env` `GITHUB_REPO_NAME=save` (corrigé : était `codeforge-ai` mais le token n'a accès qu'au repo `Ph1nt0m-oss/save`).
- **Test live** : `POST /api/export/github/proj_3685d73a6b6b` → `success:true`, 5 fichiers poussés (`index.html, style.css, app.js, manifest.json, README.md`), dossier visible sur https://github.com/Ph1nt0m-oss/save/tree/main/projects/Page-simple-de-reservation-avec-localStorage-proj_3685d73a6b6b ✅
- **Cascade anti-budget** : confirmée **sans aucune limite de tentatives** — itère toute la chaîne (8 modèles, multi-providers) avant de remonter une erreur.


### 13 Mai 2026 — Session 44 — Cascade silencieuse multi-modèles + i18n langues localisées + neutralisation noms IA
- **🚫 Plus jamais d'erreur "budget dépassé" visible** côté utilisateur :
  - Cascade multi-modèles implémentée dans `/api/chat/message` ET dans la génération de projets web. Si le modèle demandé renvoie un budget/quota/rate-limit/timeout/auth/overloaded/badrequest, le backend bascule **silencieusement** vers le modèle suivant de la chaîne sans afficher d'erreur à l'utilisateur.
  - Chaîne de fallback diversifiée (multi-providers pour contourner un cap par fournisseur) : modèle demandé → `claude-sonnet-4-5` → `gpt-5.2` → `gemini-3-flash` → `claude-haiku-4-5` → `gemini-2.5-pro` → `gpt-5` → `claude-opus-4-5`.
  - Seul le log backend trace la cascade (`↪️  Silent fallback succeeded on attempt N`). Le frontend reçoit uniquement la réponse de l'IA qui a réussi.
- **🌍 Sélecteur de langues "Nom natif (Traduction)"** :
  - Nouvelle constante `TRANSLATED_LANG_NAMES[uiLang][langCode]` couvrant les 15 langues × 15 langues UI.
  - `LanguageToggle.jsx` affiche désormais p.ex. "Deutsch (Allemand)" quand l'UI est en français, "Français (French)" en anglais, "日本語 (Japonais)" en français, etc.
  - Pas de doublon "Français (Français)" pour la langue active grâce à comparaison normalisée (case + diacritiques).
- **🤖 Noms d'IA neutralisés** dans Landing & Dashboard :
  - Landing stats : "GPT-5.2" → **"Multi-IA"** (puisque le ModelPicker offre le choix dynamique).
  - Filtres Dashboard : "Chat IA" / "Chat Ollama" / "Création Emergent" / "Création Ollama" → **"Chat en ligne"** / **"Chat hors-ligne"** / **"Création en ligne"** / **"Création hors-ligne"**.
  - Tooltips ronds colorés : "Discussion avec l'IA en ligne (GPT-5.2)" → **"Discussion avec l'IA en ligne"** (idem hors-ligne).
  - Toutes les traductions des 15 langues (`LanguageContext.js`) nettoyées des mentions "Ollama" et "(GPT-5.2)" — remplacées par "moteur d'IA local" / "in the cloud" / etc.
- **Tests** : backend testé en live (login + chat/message via `gpt-5.2` et `claude-opus-4-6` → tous deux répondent normalement, logs OK). Frontend screenshot Landing + dropdown langues OK.


### 3 Mai 2026 — Session 42 — Auto-import chats + ronds colorés + copier lien + personnalité Caly + durcissement sécurité login
- **Auto-création de projet pour chaque chat** : dès le 1er message utilisateur, un projet `type=chat` est créé automatiquement et apparaît dans la sidebar (`POST /api/chat/message` sans `project_id` crée le projet + retourne son id). Plus besoin du bouton "Pin to sidebar".
- **Champ `ai_mode` ajouté au modèle Project** (`online` / `offline`), avec backfill safe dans `GET /api/projects` et `GET /api/projects/{id}` (gère les legacy sans `updated_at`).
- **Ronds colorés dans la sidebar** (data-testid=project-dot-{id}) :
  - 🟡 **Jaune** `bg-yellow-400` — Chat online (IA GPT-5.2)
  - 🟢 **Vert** `bg-emerald-400` — Création online (Emergent)
  - 🔵 **Bleu** `bg-sky-400` — Chat offline (Ollama)
  - 🟣 **Violet** `bg-violet-400` — Création offline (Ollama)
  - Le rond est visible aussi pendant le rename (`opacity-70`) et n'est pas modifiable.
- **"Copier le lien" au clic droit** (data-testid=project-ctx-copy-link) — copie `{origin}/chat?project={id}` dans le presse-papier. Permet de référencer une ancienne discussion dans un nouveau chat quand on a supprimé la première. Chat.js lit `?project=X` et charge le projet correspondant.
- **Personnalité "Caly"** dans le prompt chat GPT : vif, chaleureux, direct, curieux, taquin calibré, avec opinions assumées. **INTERDIT** de proposer de créer une app/site/logiciel sauf demande explicite. C'est un vrai assistant généraliste, pas un commercial CodeForge.
- **Sécurité login renforcée** (vol d'appareil) :
  - Password input devient `type="text"` + `style={WebkitTextSecurity:'disc'}` → **Chrome ne propose plus de sauvegarder le mot de passe**, tout en conservant le masquage visuel.
  - Email **plus jamais prefill** (localStorage `LAST_EMAIL_KEY` nettoyé au mount, plus aucun `setItem` dans le flow). Chaque connexion force une saisie complète.
- **Éléments pédagogiques retirés** du dashboard :
  - Bouton "Tutorial" (dashboard-tutorial-btn)
  - Bouton "Améliorer les IA" (dashboard-improve-ai-btn)
  - Bouton "Entraîner l'IA (90j)" (dashboard-train-ai-btn)
  - Bandeau "Guided Wizard" (wizard-btn) — route `/wizard` toujours accessible
  - Modal "Bienvenue sur CodeForge AI" (`<Onboarding />`) — auto-découverte par l'utilisateur
  - Les markdowns `AMÉLIORER_LES_IA.md` et `ENTRAÎNER_CODEFORGE.md` **déplacés dans `/app/memory/`** (non-exposés publiquement) — seule l'équipe CodeForge peut y accéder.
- **Image en prévisualisation** des pièces jointes utilisateur dans le chat : vraie miniature `48x48px` avant envoi (data-testid=chat-pending-preview-N), plus l'émoji placeholder.
- **Tests** : backend 6/6 ✅ (après fix du bug KeyError: updated_at détecté par le testing agent), frontend 85% ✅ (les 2 "issues" sont des limitations de scénario de test Playwright, pas de vrais bugs).

### 3 Mai 2026 — Session 41-IV — Tutoriel administrateur « ENTRAÎNER CODEFORGE » (programme 90 jours)
- **Nouveau guide `/app/ENTRAÎNER_CODEFORGE.md`** (320 lignes, 23 Ko) — destiné à l'administrateur du site (pas à l'utilisateur final comme `AMÉLIORER_LES_IA.md`).
- **Contenu** :
  - **Protocole de sécurité** de 10 règles ouvrant le document (jamais de conscience, jamais d'auto-exécution, jamais d'accès secrets/DB non validé, kill-switch humain, etc.).
  - **Calendrier 12 semaines × 7 gestes = 84 actions** concrètes pour améliorer l'IA chaque jour en 5-15 minutes.
  - **7 axes d'amélioration** couverts : Mémoire, Personnalité, Connaissances, Compétences, Outils, Sécurité, Feedback.
  - **Cheat sheet** indiquant exactement quel fichier modifier pour quoi (prompt système, cfaction, langues, modules Python…).
  - **Procédure safe-change** en 9 étapes (commit Git avant → tester 3× après).
  - **Tableau de mesure hebdomadaire** avec 5 critères (ton/clarté/longueur/action/exactitude) pour tracer les progrès.
  - **3 annexes** : modèle de manuel de style, 15 prompts système prêts à coller, 3 mini-projets bonus.
- **Bouton "Entraîner l'IA (90j)"** ajouté au header Dashboard (`data-testid=dashboard-train-ai-btn`, icon Brain, visible en `lg:inline-flex`) → ouvre `/ENTRAINER_CODEFORGE.md` dans un nouvel onglet.
- **2 guides complémentaires** désormais disponibles :
  - `AMÉLIORER_LES_IA.md` (utilisateur final — bien utiliser l'IA)
  - `ENTRAÎNER_CODEFORGE.md` (administrateur — faire évoluer l'IA)

### 3 Mai 2026 — Session 41ter — REPL persistant + upload sandbox + export Jupyter + plotly + refactor _analyze_*
- **REPL Python persistant** : le sandbox accepte maintenant un `session_id` optionnel. Dans ce mode, le namespace est **serialisé via dill** entre chaque appel — les variables définies dans un bloc sont disponibles dans le suivant, style Jupyter. TTL 1 h d'inactivité, cap 50 sessions, LRU eviction. Nouvelle route `POST /api/sandbox/reset` pour purger un namespace.
- **Variables REPL affichées** : la réponse sandbox inclut `variables: [{name, type, repr}]` (max 30) — le frontend les affiche en chips violets sous le résultat (data-testid=code-run-variables).
- **Upload de fichiers dans le sandbox** : nouveau champ `files: [{filename, data_base64}]` dans le payload (max 6 fichiers × 10 Mo). Les fichiers sont déposés dans le `cwd` et accessibles par `open()`, `pandas.read_csv()`, `PIL.Image.open()`, etc. Bouton "Joindre" 📎 dans chaque bloc de code Python (data-testid=code-attach-btn).
- **Session REPL par projet** : dans le chat, tous les blocs de code partagent automatiquement le même `replSessionId = repl_{user_id}_{project_id}`. Toutes les exécutions s'enchaînent comme un notebook unique.
- **Bouton "Reset REPL"** dans le header du chat (data-testid=chat-repl-reset-btn).
- **Export conversation en Jupyter .ipynb** : `GET /api/chat/export-ipynb/{project_id}` — chaque message utilisateur → cellule markdown, chaque bloc ``` ```python``` ``` → cellule code (avec stdout pré-rempli quand disponible). Nbformat 4 valide, importable directement dans Jupyter/VSCode/Colab. Bouton dans le header chat (data-testid=chat-export-ipynb-btn).
- **Refactor `_analyze_*` → cfaction_engine.py** : les 5 analyzers (`analyze_pdf/docx/xlsx/pptx/sqlite`) sont maintenant des fonctions pures dans `cfaction_engine.py`. server.py délègue via wrappers `async _analyze_*`. Zero breaking change.
- **Plotly installé** (v6.7) dans le sandbox pour futurs graphiques JS interactifs (export HTML).
- **Nouvelles dépendances backend** : `plotly`, `dill`, `narwhals` (dep de plotly).
- **Tests** : backend 9/9 ✅ (REPL persistance, éphémère, upload CSV, reset, export ipynb happy+error path, régressions), frontend 100% ✅ (tous les nouveaux boutons et chips).

### 3 Mai 2026 — Session 41bis — Markdown chat + bouton Exécuter + matplotlib inline + refactor cfaction_engine
- **Rendu Markdown riche dans le chat** : nouveau composant `MessageContent.jsx` basé sur `react-markdown` + `remark-gfm` + `react-syntax-highlighter` (thème oneDark Prism) — tableaux, listes, blockquotes, liens, titres h1/h2/h3.
- **Bouton "Exécuter" + "Copier" sur chaque bloc de code** :
  - Sur les blocs ``` ```python ``` ```, bouton vert `Exécuter` (data-testid=code-run-btn) qui POST `/api/sandbox/python` et affiche inline `stdout / stderr / exit_code / duration_ms / images` (data-testid=code-run-output).
  - Bouton `Copier` (data-testid=code-copy-btn) pour tous les langages, avec feedback "Copié" pendant 1.6s.
  - Le chat devient **un mini Jupyter notebook gratuit**.
- **Capture automatique matplotlib** : le sandbox Python injecte un preamble qui patche `plt.show()` et enregistre toutes les figures dans `_figs_/*.png` avant cleanup. Les PNG sont retournés dans `images: [{filename, mime_type, data_base64}]` (cap à 6). Le parser `cfaction run_python` les inline en markdown `![figure N](data:image/png;base64,...)` dans la réponse AI.
- **System prompt renforcé** : l'IA est maintenant instruite de **TOUJOURS** utiliser `run_python` pour les demandes de graphique/courbe/visualisation (plus jamais de `/mnt/...` fantaisiste). Exécution proactive également pour les maths non triviales, simulations, tirages aléatoires.
- **Refactor server.py → cfaction_engine.py** (P2 du backlog) :
  - Nouveau module `/app/backend/cfaction_engine.py` (372 lignes) avec fonctions **pures** : `sanitize_filename`, `analyze_{pdf,docx,xlsx,pptx,sqlite}`, `build_{docx,pdf,xlsx,pptx}_bytes`, `run_python_sandbox`.
  - `server.py` passe de 4660 → 4458 lignes (-203). Les wrappers `_build_*` et `_run_python_sandbox` délèguent au module pur.
  - Pas de rupture d'API externe — tous les endpoints existants fonctionnent à l'identique.
- **Nouvelles dépendances frontend** : `react-markdown`, `remark-gfm`, `react-syntax-highlighter`.
- **Tests** : backend 17/17 ✅ (10 régressions iter41 + 7 nouveaux matplotlib/refactor), frontend 100% ✅ sur critères d'acceptance (bloc code, copier, exécuter, output).

### 3 Mai 2026 — Session 41 — Sandbox Python + mémoire chat sans limite + Live Preview + tutoriel IA
- **Mémoire conversationnelle : ZÉRO limite** (signature CodeForge) — `server.py` L2378-2391 & L2417-2429 : suppression du `.limit(21)` et du slicing. On remonte TOUTE l'historique Mongo (`find(...).sort('timestamp', 1).to_list(None)`). Vérifié : l'IA retient un prénom à travers N messages.
- **Langue dynamique assouplie** — le prompt système interpole le `lang_label` du frontend ; `language='en'` → réponse en anglais. Plus de forçage FR.
- **Sandbox Python opérationnel** :
  - Nouvelle fonction `_run_python_sandbox()` (`server.py` L3043-3113) : `asyncio.create_subprocess_exec` avec `sys.executable`, timeout dur via `asyncio.wait_for` (1-30 s, défaut 10 s), env isolé (pop de EMERGENT_LLM_KEY, RESEND_API_KEY, MONGO_URL, DB_NAME, OLLAMA_BASE_URL), `MPLBACKEND=Agg`.
  - Nouvel endpoint `POST /api/sandbox/python` (auth requise) → `{stdout, stderr, exit_code, timed_out, duration_ms}`.
  - Intégration `cfaction type=run_python` : l'IA peut terminer sa réponse par `{"type":"run_python","content":"..."}`, le backend l'exécute et **injecte inline** le résultat formaté (`▶️ Exécution Python (sandbox) :` + code-fence stdout + stderr + durée) avant de supprimer le bloc `cfaction`.
  - Modules installés : `matplotlib, sympy, beautifulsoup4, lxml, pytz, python-dateutil` (en plus des existants `numpy, pandas, requests, openpyxl, python-docx, pptx, reportlab, pypdf, httpx, PIL, yaml`).
- **Live Preview des projets** :
  - Nouvelle page `/preview/:projectId` (`ProjectPreview.js`) — iframe sandbox (`allow-scripts allow-forms allow-popups allow-same-origin`), 3 tailles responsive (desktop / tablet / mobile), bouton refresh, bouton "ouvrir dans un onglet".
  - Dashboard sidebar → menu contextuel projet → nouveau bouton **"Aperçu Live"** (`data-testid=project-ctx-preview`), caché pour projets `type=chat`.
  - Fix bug backend (découvert par le testing agent) : `get_project_preview` crashait en 500 quand `project.generated_code=None` → remplacé `project.get('generated_code', {})` par `project.get('generated_code') or {}` + dict-guard sur `.get('files')`.
- **Autofill login renforcé** (3e itération) — `Login.js` ajoute `readOnly` initial sur email+password + `onFocus={e.target.removeAttribute('readonly')}` → Chrome ne peut plus auto-remplir les champs avant interaction utilisateur. Combiné avec noms randomisés (`pwd_xxxxxx`), `data-lpignore`, `data-1p-ignore`, `data-bwignore`, honeypots cachés.
- **Tutoriel `AMÉLIORER_LES_IA.md`** (13 Ko, 10 sections) :
  - Pour débutants sans expérience : guide no-code pour améliorer les prompts, le contexte, les rôles, le sandbox, les pièces jointes.
  - 9 modèles de prompts prêts à copier-coller.
  - Exposé publiquement à `/AMELIORER_LES_IA.md` (frontend CRA static) + copie dans `/app/`.
  - Bouton "Améliorer les IA" ajouté au header Dashboard (`data-testid=dashboard-improve-ai-btn`) → ouvre le .md dans un nouvel onglet.
- **Ménage disque** : suppression des builds desktop/output (2.6 Go) avant installation matplotlib/sympy. `requirements.txt` mis à jour.
- **Tests** : `/app/backend/tests/test_iter41_sandbox_chat.py` (10 cas pytest : sandbox, chat, mémoire, langue, preview). Backend 10/10 ✅ | Frontend 100% ✅.

### 3 Mai 2026 — Session 40 — Chat full-modal : Excel/PowerPoint/code files + Python stack complet + FR strict + zéro limite
- **Python stack étendu** : `openpyxl`, `python-pptx`, `xlsxwriter`, `pypdf`, `python-docx`, `reportlab`, `Pillow`, `PyYAML` installés → `requirements.txt` gelé.
- **Analyse de pièces jointes étendue** (`/api/chat/analyze-attachment`) :
  - **XLSX** → `openpyxl` extrait toutes feuilles en tableau texte (6 feuilles × 200 lignes max)
  - **PPTX** → `python-pptx` extrait le texte de toutes les slides (60 max)
  - **SQLite / DB** → `sqlite3` liste les tables + schéma + 10 lignes exemple par table
  - **Formats texte élargis** : `.yaml/.yml/.xml/.ini/.env/.cfg/.toml/.sql/.sh/.ps1/.bat/.cmd/.rb/.go/.rs/.java/.c/.cpp/.cs/.php/.kt/.swift` + tous les `.log`
- **Génération de fichiers étendue** (bloc `cfaction`) — 17 formats supportés :
  - **docx / pdf / xlsx** (avec formules Excel) / **pptx**
  - **image** (Gemini Nano Banana)
  - Fichiers texte & code : **txt, md, csv, json, yaml/yml, xml, ini, env, sql, py, js, ts, tsx, jsx, html, css, sh, ps1, bat**
- **Regex cfaction renforcée** : capture le contenu complet entre ` ```cfaction` et ` ``` ` (DOTALL non-greedy) → plus robuste avec du code multi-ligne.
- **Système prompt élargi** :
  - « Réponds TOUJOURS en français — 0% d'anglais parasite »
  - Liste des 17 formats cfaction avec exemples JSON stricts
  - « Tu sais écrire, corriger, expliquer et simuler du code Python (pandas, numpy, requests, FastAPI, SQLAlchemy, openpyxl, python-docx, pptx, PIL, reportlab), PowerShell, CMD, Bash, JS/TS, SQL »
- **Vérification limites** : `grep -n "rate_limit|quota|messages_per|chat_limit|daily|monthly"` → **aucune occurrence** sur les 4 flows de chat. Aucune limite artificielle.
- **Tests curl validés** :
  - Excel avec formule `=A2+B2` → `Addition_A_B.xlsx` ✅
  - PowerPoint 3 slides → `Écosystèmes_marins.pptx` ✅
  - Script Python RSS → `feed.py` (2321 octets, complet, commenté en français) ✅
  - PDF analyze → extraction texte ✅
  - Image (chat roux) → PNG Gemini ✅

### 3 Mai 2026 — Session 39 — Chat multimodal : analyse fichiers + génération DOCX/PDF/image
- **Analyse de pièces jointes** dans le chat (trombone) : 
  - PDF → extraction texte via `pypdf` (40 pages max)
  - DOCX → extraction paragraphes via `python-docx`
  - Images (PNG/JPG/WEBP/GIF) → description via GPT-5.2 vision (ImageContent)
  - Texte brut (.txt, .md, .csv, .json, code) → lecture directe
  - Cap à 20 Mo par fichier, 30k chars par extraction.
  - Endpoint : `POST /api/chat/analyze-attachment` (multipart).
- **Génération DOCX / PDF / image via l'IA** :
  - Système prompt enrichi : GPT-5.2 termine sa réponse par un bloc ` ```cfaction {"type":"docx|pdf|image",...} ``` ` quand l'utilisateur demande explicitement un fichier.
  - Backend parse le bloc, génère le fichier (python-docx / reportlab / Gemini Nano Banana), stocke sur disque + collection `generated_files` Mongo, retourne `{file_id, url, filename, mime_type}`.
  - Endpoint download : `GET /api/download/generated/{file_id}` (ownership-checked).
  - 3 fonctions pures `_build_docx`, `_build_pdf`, `_build_image` + endpoints REST dédiés `/chat/generate-docx|pdf|image`.
- **Frontend Chat** :
  - Trombone : `handleAttachment` upload le fichier → analyse → stocké dans `pendingAtts`, envoyé avec le prochain message.
  - Chips de pièces jointes en attente avec bouton X pour retirer.
  - Message IA : si `download` présent → bouton de téléchargement jaune + preview inline pour les images.
  - Imports ajoutés : `Pin, Download, X`.
- **Tests curl validés** :
  - Analyse PDF → extraction texte OK ✅
  - Génération Word (Intro + Conclusion sur chiens) → filename `Petit_document___Chiens.docx` (36 Ko) ✅
  - Génération image (chat roux) → PNG via Gemini ✅
  - Download endpoint → HTTP 200 + file OK ✅

### 2 Mai 2026 — Session 38 — Chat header cleanup + Sidebar pin chats + ZIP/GitHub export per project + i18n
- **🚨 Fix crash FeedbackButton** : `TYPES is not defined` → renommé en `TYPES_T` (déjà déclaré).
- **Chat header épuré** : seul le bouton **Retour** reste (les boutons Web/App/PDF/DOCX et le titre du chat ont été retirés).
- **Épingler discussion dans la barre latérale** :
  - Bouton "Pin" 📌 (jaune) en haut de chat quand on a déjà discuté sans projet.
  - Crée un projet de type `chat`, attache les messages existants via nouvel endpoint `POST /api/chat/attach`.
  - Sidebar affiche désormais l'icône 💬 `MessageSquare` (jaune) pour les chats épinglés.
- **Export ZIP par projet** (clic-droit sidebar) :
  - Endpoint `/api/export/download` (existant) — corrigé pour accepter les projets `chat` (sans code généré) → ZIP avec README + transcript.
  - Toujours inclut un `README.md` à la racine si absent.
  - Nouveau bouton "Télécharger ZIP" dans le menu contextuel.
- **Export GitHub par projet** (clic-droit sidebar) :
  - Nouveau endpoint `POST /api/export/github/{project_id}` → push tous les fichiers + README + chat-transcript dans `projects/<safe-name>-<id>/`.
  - Nouveau bouton "Pousser vers GitHub" dans le menu contextuel + toast avec lien direct vers le dossier.
  - Vérifié par curl : push OK sur `Ph1nt0m-oss/codeforge-ai` repo.
- **i18n chat** : nouvelles clés `chatPinBtn`, `chatPinned`, `chatEmptyTitle/Online/Offline`, `chatPlaceholder` (FR + EN, fallback EN→clé).
- **Anti-autofill** : déjà actif (Session 35).

### 2 Mai 2026 — Session 37 — Upgrade GPT-4o → GPT-5.2 + prompts senior + Ollama unifié
- **Modèle** : `gpt-4o` → **`gpt-5.2`** sur les 3 routes IA (chat /api/chat/message, génération /api/ai/generate-complete-app, wizard /api/ai/wizard-suggest). Vérifié dans les logs LiteLLM (`completion() model= gpt-5.2; provider = openai`).
- **Chat AI prompt repensé** (haut de gamme conversationnel) :
  - Génération en temps réel à partir de l'historique, jamais de phrases pré-faites
  - Interprétation de l'intention réelle, adaptation au ton (pressé/frustré/curieux)
  - Garde-fous (refus malware/harcèlement/données privées tierces)
  - Identité claire (CodeForge AI, GPT-5.2 en ligne / Ollama hors-ligne)
  - Format : 1-4 phrases courtes par défaut
- **Création AI prompt repensé** (architecte + dev full-stack + QA + chef de projet) :
  - Découpage en modules (UI / data / auth / business / design / sécurité)
  - Hypothèses intelligentes (jamais 50 questions bloquantes)
  - Tests mentaux 4 couches (technique / fonctionnel / UX / robustesse) avant réponse
  - Justification des choix techniques dans `explanation`
  - Sortie JSON strict
- **Ollama config unifiée** :
  - `OLLAMA_CHAT_MODEL` (par défaut `llama3.2`) pour les chats hors-ligne (conversationnel)
  - `OLLAMA_CODE_MODEL` (par défaut `deepseek-coder:6.7b`) pour les générations hors-ligne (code)
  - Fallback en cascade : modèle spécifique → `OLLAMA_MODEL` → défaut hardcodé
  - **Historique de conversation injecté aussi côté Ollama offline** (parité online/offline)
- **Vérifié par curl** : 
  - "Bonjour" → réponse contextuelle qui propose des options
  - "Quelle IA tourne sous le capot ?" → cite GPT-5.2 + Ollama Deepseek correctement
  - "Bonjour" 2e fois → réponse contextuelle différente (pas de doublon)

### 2 Mai 2026 — Session 36 — Multi-line Create + Copy with prefixes + Mic AudioLines + AI memory
- **Create.js** : input → textarea, multi-ligne avec saut de ligne par Entrée. Bouton "Générer" pour soumettre.
- **Chat copy** : préfixe rôle invisible (`fontSize:0`) inséré avant chaque message → quand l'utilisateur copie la conversation, le presse-papier contient `Elsa : Bonjour` / `CodeForge : Salut ! …`. Pas visible à l'écran (les avatars suffisent).
- **Mic envoi vocal** : icône `AudioLines` (lucide-react) sur **cercle noir plein** + barres en **rouge** — match l'image de référence.
- **IA conversationnelle (gros fix)** :
  - Système prompt revu : interdit de dire "Salut !" deux fois, interdit de demander "peux-tu préciser ?" sur des mots-clés clairs (Chat GPT, GPT, Claude, Gemini, Ollama, Mistral...) → l'IA explique directement.
  - **Historique des 10 derniers messages chargé de MongoDB** et injecté dans le prompt utilisateur à chaque appel → la mémoire conversationnelle ne dépend plus uniquement du `session_id` LlmChat.
  - Vérifié par curl : "Bonjour" → "Salut !..." / "Chat GPT" → explication d'OpenAI / "Bonjour" (2e fois) → "Comment puis-je t'aider aujourd'hui ?" (sans "Salut !").

### 1er Mai 2026 — Session 35 — Fix crash chat + restore offline modes + i18n HowItWorks/Feedback + anti-autofill
- **🚨 Fix crash Chat** : import manquant `useAuth` ajouté → page chat ne plante plus.
- **Dashboard restauré** : 4 cartes au total (Chat online, Création online, **Chat offline (Ollama)**, **Création offline (Ollama)**) + l'Assistant guidé. Section "Mode en ligne / Mode hors ligne" en bas RETIRÉE comme demandé.
- **Microphones** : forme `rounded-full` (cercle plein) — dictée = **blanc plein**, envoi = **rouge plein**. Match l'image fournie.
- **Send-on-Enter désactivé** sur Chat + Create (textarea/input) — l'utilisateur clique le bouton Envoyer/Générer pour soumettre, évite les envois accidentels Maj+Enter sur PC.
- **HowItWorks i18n** (`HowItWorksContent.js`) : titre, intro, CTA, footer + 7 sections traduits dans 12 langues (FR/EN complets, autres langues utilisent les blocs EN par défaut + UI translateé). Sélecteur de langue ajouté en haut à droite.
- **Feedback i18n** : "Ton avis nous intéresse / Bug / Idée / Autre / placeholder / caractères / Envoyer" via clés `fb*` (FR + EN, fallback EN→clé pour les 10 autres).
- **Anti-autofill navigateur** sur Login :
  - `autoComplete="off"` sur form + `autoComplete="new-password"` sur le champ password
  - `name` randomisé à chaque rendu (déjoue les heuristiques Chrome/Safari/Firefox)
  - Attributs `data-form-type="other"`, `data-lpignore="true"`, `data-1p-ignore="true"`, `data-bwignore="true"` (LastPass / 1Password / Bitwarden ignorent)
  - 2 honeypots cachés `username/password` hors écran pour aspirer l'autofill
  - Conséquence : l'utilisateur DOIT taper son email + mot de passe manuellement → confirmation d'identité.

### 1er Mai 2026 — Session 34 — UX polish batch (avatars, feedback v2, mic colors, Made-with hidden)
- **Chat avatars** : avatar IA (rond jaune avec icône Sparkles) + avatar utilisateur (Google `user.picture` si dispo, sinon initiale). Plus de doute sur qui parle.
- **Sidebar projets** : icône de plateforme (Globe/Smartphone/Monitor) **avant** le nom, tout sur une seule ligne. Clic gauche = ouvrir le chat avec contexte projet, clic droit (long-press mobile) = menu Renommer/Supprimer (icônes avant labels, suppression en rouge).
- **Dashboard** : suppression du sous-titre "Choisissez votre mode de travail" + des 4 cartes online/offline. Conserve uniquement les 2 cartes en ligne (Chat / Création) + l'Assistant guidé.
- **Wizard tutoriel** : "Créez votre app étape par étape" → "Créez votre **projet** étape par étape" dans les 12 langues.
- **Microphones** :
  - Mic dictée (le neutre) → **blanc** (bg-white)
  - Mic envoi vocal direct → **rouge** (bg-red-500)
- **Feedback v2** :
  - Suppression de la limite de 5000 caractères
  - Trombone (📎) ajouté : pièces jointes via fichier (data URL ≤ 4 Mo), URL ou presse-papier
  - Email envoyé à `elsa.barroca2@gmail.com` (configurable via `FEEDBACK_INBOX_EMAIL`), **avec l'email de l'expéditeur masqué** dans le corps (privacy-first, comme les formulaires de contact d'entreprise)
- **"Made with Emergent"** badge masqué (display:none dans index.html).
- **Profile / Info — "Voir mon mot de passe"** :
  - **Techniquement impossible** : passwords en bcrypt one-way. Remplacé par un bouton **"Réinitialiser mon mot de passe"** qui ouvre un mini-form (nouveau mdp + confirmation) → email avec lien sécurisé (réutilise le flow forgot-password "set then confirm").
- **Auto-logout 1h inactivité** : déjà actif (session_24).

### 1er Mai 2026 — Session 33 — Legal i18n + navbar swap
- **Legal page traduite 12 langues** (`LegalContent.js`) : CGU, Privacy (RGPD), Cookies en fr/en/es/pt/de/nl/ru/zh/zh-TW/hi/bn/ur. Sélecteur de langue ajouté en haut à droite.
- **Navbar swap** (Landing + Discover) : `LanguageToggle` à DROITE, bouton principal à GAUCHE.

### 1er Mai 2026 — Session 32 — P2 batch (Wizard rebuild + Settings + Multi-comptes) + cleanup login
- **Login** : suppression du bouton "Connexion/Inscription" en double (`auth-submit-btn`). Plus qu'un seul CTA jaune par mode.
- **Dashboard sidebar** : clic gauche sur un projet ouvre désormais directement `/chat` avec le projet en contexte (mobile : tap sans maintien). Le clic-droit (long-press mobile) ouvre toujours le menu Renommer/Supprimer.
- **Chat** : header affiche le nom du projet (`chat-title`), historique chargé via `/api/chat/history?project_id=...`, message envoyé avec `project_id`.
- **Wizard refait** (`GuidedWizard.js`, 5 étapes) :
  1. Multi-select Plateformes (web/mobile/desktop) + multi-select Types (12 catégories)
  2. Nom + 🪄 baguette magique IA (3 suggestions cliquables)
  3. 2 textareas séparés : Design (visuel) + Fonctionnement (logique) — baguette magique design + 📎 trombone (fichier/presse-papier/URL)
  4. Récapitulatif lisible
  5. Génération + écran succès (APK/EXE/Web)
- **Profile** : 2 nouveaux onglets
  - **Préférences** : thème (sombre/clair/auto), contraste (normal/élevé), accent color (6 presets + color picker), notifications email/push, **Device ID** (copiable). Persisté en localStorage + backend `/api/auth/preferences`.
  - **Comptes** : liste des comptes associés (localStorage `codeforge_known_accounts`), ajout (email + mdp + email de confirmation auto), suppression (mot de passe requis pour confirmer).
- **Backend nouveaux endpoints** :
  - `POST /api/ai/wizard-suggest` (`kind=name|design`) → suggestions IA via Emergent GPT-4o
  - `GET/PUT /api/auth/preferences` → préférences utilisateur (theme, contrast, accent, notifications)
- **Tests** : SKIPPED (validation utilisateur en cours).

### 1er Mai 2026 — Session 31 — Sidebar context-menu + AI tone fix
- Clic-droit sur projet sidebar → Renommer (inline) / Supprimer (modal)
- IA conversationnelle : prompt système retravaillé, plus de jargon technique sur "Bonjour"
- Tests : iter_31.json — Backend 8/8, Frontend 100% PASS

### 1er Mai 2026 — Session 30 — Forgot password + Dashboard cleanup
- Forgot-password "set then confirm"
- Pill central "En ligne/Hors ligne" supprimé, email en haut à droite
- Tests : iter_30.json — Backend 9/9, Frontend complet PASS

### 1er Mai 2026 — Session 29 — Voice mics + Sidebar profile + Paperclip + Login red error
- Chat IA conversationnel, login error rouge inline, sidebar profil restructurée
- Mic ChatGPT-style + Trombone (3 sources) + footer Landing traduit
- Tests : iter_29.json PASS

### 1er Mai 2026 — Session 28 — Voice + i18n + Responsive
### 1er Mai 2026 — Session 27 — Layout 3-colonnes + i18n Landing/Discover
### 1er Mai 2026 — Session 26 — Refonte UX + AI multilingue
### 30 Avril 2026 — Session 25 — Pack P1+P2 (Profil, Magic Link, /how-it-works, /legal, Feedback)
### Sessions ≤24 — Auth Resend, audit, cross-tab unlock, monitoring, polish UI, sécurité, auto-deploy

## Routes actives
### Auth
- POST /api/auth/register, /resend-verification, /login, /magic-link
- POST /api/auth/forgot-password, /reset-password, /change-password, /change-email
- GET /api/auth/verify-email, /verification-status, /me, /export
- DELETE /api/auth/me
- POST /api/auth/logout
- POST /api/auth/sms/send|verify
- **GET/PUT /api/auth/preferences ✨ NEW**

### IA
- POST /api/ai/generate-complete-app
- POST /api/ai/generate-code
- **POST /api/ai/wizard-suggest ✨ NEW** (`kind=name|design`)
- POST /api/chat/message, GET /api/chat/history
- POST /api/voice/transcribe

### Système
- GET /api/health, /metrics, /guide, POST /api/feedback, /admin/redeploy

### Routes RETIRÉES (404)
- POST /api/auth/session, GET/POST /api/auth/google/login|callback

## Routes frontend
- `/` Landing, `/login`, `/sms-login`, `/verify-email`, `/reset-password`
- `/dashboard` (clic projet → `/chat` avec contexte)
- `/create`, `/wizard` (refait), `/chat` (avec project context)
- `/profile` (6 onglets : Info, MDP, Email, **Préférences ✨**, **Comptes ✨**, Danger)
- `/how-it-works`, `/legal`, `/discover`

## Backlog futur
- **P3** : Domaine custom DNS pour Resend
- **P4** : SMS gratuit Free Mobile API
- **P5** : Refactoring server.py en routes/ modules
- **P6** : Upload réel des pièces jointes du wizard (pipeline file→AI vision)
- **P7** : Bascule cross-tab entre comptes associés (OAuth-like local)

## Santé du projet
- Lint Python ✅ / JS ✅
- Sécurité : bcrypt + brute-force + rate-limits + tokens single-use + cascade delete + idle 1h
- Performance : 8 indexes MongoDB + cleanup task background 10 min
- RGPD : export JSON + suppression cascade + page Confidentialité

