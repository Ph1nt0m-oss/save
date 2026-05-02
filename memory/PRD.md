# CodeForge AI - PRD

## Statut : VERSION P2 — STABLE & PRODUCTION-READY (Mai 2026)

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

