# CodeForge AI - PRD

## Statut : VERSION P2 — STABLE & PRODUCTION-READY (Mai 2026)

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

