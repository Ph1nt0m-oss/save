# CodeForge AI - PRD

## Statut : VERSION ULTIME PHASE 6 — STABLE & PRODUCTION-READY (Mai 2026)

### 1er Mai 2026 — Session 30 — Forgot password "set then confirm" + Dashboard cleanup
- **NEW forgot-password flow** : utilisateur saisit email + nouveau mdp + confirmation → backend hash et stocke en attente sur le token (30 min) → email "Veuillez cliquer ici pour confirmer la réinitialisation de votre mot de passe" → clic = mdp appliqué + sessions invalidées + redirect /login. Endpoint `GET /api/auth/confirm-password-reset?token=`.
- **Dashboard** : pill central "En ligne/Hors ligne" SUPPRIMÉ. Email + avatar style Google → en haut à droite (UserMenu trigger affiche l'email complet, plus le nom). Pill email dupliqué dans la sidebar SUPPRIMÉ.
- **Tests** : iter_30.json — Backend 9/9 PASS, Frontend complet PASS, 0 issue.

### 1er Mai 2026 — Session 29 — Voice mics + Sidebar profile + ChatGPT mic + Paperclip + Login red error
- **Chat AI conversationnel** : `/api/chat/message` réécrit. Mode online → Emergent GPT-4o (~3s, conversationnel "Bonjour ! Comment puis-je t'aider…"). Mode offline → Ollama uniquement. Sinon fallback localisé court 12 langues. Plus de message Ollama setup imposé.
- **Login error inline rouge** : "Mot de passe incorrect" sous le champ password (rouge), bordure rouge, clear sur edit. `data-testid='auth-error'`.
- **Dashboard sidebar bottom** restructurée : pill email (non-cliquable, avatar initiale) → Mon profil → Changer de compte → Déconnexion (rouge). "IA Disponible" supprimé. `data-testid='sidebar-profile-pill|btn|switch-account-btn|logout-btn'`.
- **Mic ChatGPT-style** : envoi vocal en blanc/noir (au lieu de rouge). Dictée reste neutre.
- **Trombone (📎)** : nouveau composant `AttachMenu`, présent sur Chat + Create. Trois sources : appareil (file picker), presse-papier (`navigator.clipboard.read`), URL (input). `data-testid='attach-btn|menu|from-device|from-clipboard|from-url|url-form|url-submit'`.
- **Footer Landing** : liens "Comment ça marche" + "CGU & Confidentialité" traduits 12 langues. `data-testid='footer-how-it-works|legal'`.
- **Chat header responsive** : preview buttons compacts (icon-only) <sm, wrap natural sur 360px (overflow=NO confirmé).
- **Viewport** : `user-scalable=yes, max-scale=5` (zoom navigateur autorisé).
- **Tests** : iter_29.json — backend 5/5 + frontend mostly PASS (1 bug `mode==='signin'` vs `'login'` corrigé par testing agent, 1 chat preview overflow corrigé manuellement).

### Backlog P2 (prochaine session)
- **Wizard rebuild** : multi-select plateforme (web/app/logiciel), multi-select type, génération IA noms (baguette magique), génération IA design avec import pièce jointe, étape personnalisation à 2 textareas (design + fonctionnement) avec auto-description, écran récapitulatif final
- **Profile settings expansion** : thème, contraste, accent color, notifications, device ID
- **Reset mot de passe nouveau flow** : saisie nouveau mot de passe d'abord puis email de confirmation (au lieu de l'inverse actuel)
- **Add/Remove email accounts** flow complet (mot de passe + confirmation email)

### 1er Mai 2026 — Session 28 — Voice mics + i18n complète + Responsive
- **Voice transcription** : `/api/voice/transcribe` (OpenAI Whisper via Emergent LLM Key). Composant `VoiceRecorder` (mode `send` instantané, mode `dictate` rempli champ).
- **2 micros par chat** sur Chat & Create. Tooltips/erreurs traduits 12 langues.
- **Tutorial step 4 (Chat)** mentionne les 2 micros 🎙️ dans toutes les langues.
- **Responsive** : Landing/Discover/Dashboard/Chat/Create breakpoints sm/md/lg/xl (text-3xl→8xl), `overflow-x-hidden`, `truncate`, `whitespace-nowrap`, exports/labels masqués sm:inline. Plus besoin de zoom 30%.
- **Tests** : iter_28.json — tous PASS.

### 1er Mai 2026 — Session 27 — Layout 3-colonnes & i18n complète Landing/Discover
- **Landing** :
  - Navbar reorganisée : `[LanguageToggle gauche] · [CodeForge AI centré] · [Découvrir droite]`
  - Héro : Connexion à GAUCHE / Inscription à DROITE, **les deux en outline (plus de jaune)**
  - z-index navbar passé à `z-30` (fix dropdown langues qui était bloqué par le héro)
- **Discover** : header `[LangToggle + Quitter] · [CodeForge AI + Étape X/7] · [Connexion]` (même layout 3-colonnes)
- **Dashboard** : header reorganisé `[Sidebar toggle + LangToggle] · [CodeForge AI centré] · [Tutoriel + Exports + UserMenu]`. Nouveau bouton `data-testid=dashboard-tutorial-btn` qui mène à /discover.
- **i18n complet 12 langues** : ajout de ~50 clés Landing (`l_*`) + Discover (`d_*`) + `dashTutorial` dans **fr, en, es, pt, de, nl, ru, zh, zh-TW, hi, bn, ur**. La page d'accueil ET le tutoriel se traduisent intégralement.
- **Tests** : iter_27.json — 14/14 frontend acceptance criteria PASS, 0 issue restant.

### 1er Mai 2026 — Session 26 — Refonte UX (Landing, Discover, Dashboard, i18n)
- **Landing** : bouton top droit `Découvrir` (au lieu de Connexion), héro `Inscription` (primaire jaune) + `Connexion` (outline)
- **Discover (/discover)** : tutoriel interactif 7 étapes avec **mock-écrans dédiés** (Dashboard, Wizard, Création, Chat, Aperçu app, Hors-ligne, CTA final). Navigation flèches Précédent/Suivant + clavier ← →. Tout autre clic affiche un toast "🔒 Connecte-toi…". Bouton final "S'inscrire" + "Connexion" en haut.
- **Dashboard** :
  - Bouton toggle sidebar projets dans le header (style ChatGPT, `PanelLeftClose/Open`) — toujours visible.
  - "Changer de compte" déplacé dans la sidebar projets (bas).
  - **Un seul bouton de déconnexion** (UserMenu dropdown). Grille bottom (Switch/Logout) supprimée.
  - Tous les textes utilisent `t()` (avant : hardcoded FR/EN).
  - Toggle FR/EN inline supprimé — remplacé par le composant `LanguageToggle` complet (12 langues).
- **Sélecteur de langue** : drapeaux 🇫🇷🇬🇧🇪🇸🇵🇹🇩🇪🇳🇱🇷🇺🇨🇳🇹🇼🇮🇳🇧🇩🇵🇰 + nom natif complet (`English`, `Español`, `中文 (简体)`, …).
- **AI multilingue** : `Create.js` envoie `language` à `/api/ai/generate-complete-app`. Le prompt backend ajoute une `language_directive` pour que l'IA produise UI/README/explanation dans la langue choisie.
- **Tests** : iter_26.json — 4/4 backend pytest + 14/14 frontend acceptance criteria PASS.

### 30 Avril 2026 — Session 25 — Pack P1+P2 (VERSION FINALE)
- **Page Profil/Paramètres** (`/profile`) avec 4 onglets :
  - Info : nom, email, dates, type d'auth, **export RGPD JSON**
  - Mot de passe : changement avec MDP actuel + invalidation des autres sessions
  - Email : changement avec lien de confirmation envoyé au nouvel email
  - Zone dangereuse : suppression compte avec confirmation "SUPPRIMER" (cascade delete RGPD)
- **Magic Link Login** : bouton "Connexion par lien magique (sans mot de passe)" sur Login → `POST /api/auth/magic-link` rate-limited 3/10min, polling cross-tab existant
- **Page `/how-it-works`** : doc moteur IA en 7 sections (gratuit illimité, online GPT-4o, offline Ollama, wizard, exports, sécurité, technique)
- **Page `/legal`** : CGU + RGPD + Cookies (3 onglets, query param `?tab=`)
- **Bouton Feedback flottant global** : icône MessageCircle en bas-droite (au-dessus du badge Emergent), modal avec types bug/suggestion/other, stocké en MongoDB + email admin via Resend
- **Cleanup**: suppression définitive de `AuthCallback.js` (résidu Google Auth), strip silencieux de `#session_id=` dans App.js
- **`verify-email`** étendu pour gérer `purpose=email_change` (race-check si email pris entre-temps)
- **Tests** : **100 passed / 3 skipped** (DEPLOY_SECRET-gated)

### Sessions précédentes
- **Session 24** : Forgot/Reset password + cleanup task background + health check enrichi + idle timeout 1h
- **Session 23** : Bouton "Renvoyer le lien" + audit (133 lignes code mort)
- **Session 22** : Cross-tab auto-unlock + TTL 5 min + `/api/guide` HTML
- **Session 21** : Migration Email/Password + Magic Link (abandon Emergent Auth + Google OAuth)
- **Phase 5** : Tests + monitoring + service worker
- **Phase 4** : Polish UI/UX glassmorphism
- **Phase 3** : Sécurité + perf + UX
- **Phase 2** : Auto-deploy GitHub Actions
- **Phase 1** : Auth (remplacée)

## Routes actives FINALES
### Auth
- `POST /api/auth/register`
- `POST /api/auth/resend-verification`
- `GET /api/auth/verify-email` (gère verify + email_change + magic_login)
- `GET /api/auth/verification-status` (polling cross-tab)
- `POST /api/auth/login`
- `POST /api/auth/magic-link` ✨ NEW
- `POST /api/auth/forgot-password`
- `POST /api/auth/reset-password`
- `POST /api/auth/change-password` ✨ NEW
- `POST /api/auth/change-email` ✨ NEW
- `GET /api/auth/me`
- `DELETE /api/auth/me` ✨ NEW (cascade RGPD)
- `GET /api/auth/export` ✨ NEW (export RGPD JSON)
- `POST /api/auth/logout`
- `POST /api/auth/sms/send|verify` (mode démo)

### Système
- `GET /api/health` (checks détaillés)
- `GET /api/metrics`
- `GET /api/guide` (HTML)
- `POST /api/feedback` ✨ NEW
- `POST /api/admin/redeploy`

### Routes RETIRÉES (404)
- `POST /api/auth/session` (Emergent Auth)
- `GET/POST /api/auth/google/login|callback`

## Routes frontend
- `/` Landing
- `/login` (avec magic-link, forgot-password, footer how-it-works/legal)
- `/sms-login`
- `/verify-email?token=xxx`
- `/reset-password?token=xxx`
- `/dashboard` (protected)
- `/create`, `/wizard`, `/chat` (protected)
- `/profile` ✨ NEW (protected, 4 tabs)
- `/how-it-works` ✨ NEW (public)
- `/legal` ✨ NEW (public, ?tab=cgu|privacy|cookies)

## Santé du projet
- **Lint Python** : 0 warning ✅
- **Lint JS** : 0 warning ✅
- **Tests** : **100 passed / 3 skipped** ✅
- **Sécurité** : bcrypt + brute-force + rate-limits + tokens single-use + cascade delete + auto-clear 401 + idle 1h
- **Performance** : 8 indexes MongoDB + cleanup task background 10 min
- **RGPD** : export JSON + suppression cascade + page Confidentialité

## Backlog futur
- **P3** : Domaine custom DNS pour Resend
- **P4** : SMS gratuit Free Mobile API
- **P5** : Refactoring server.py en routes/ modules
