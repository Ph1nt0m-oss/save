# CodeForge AI - PRD

## Statut : VERSION ULTIME PHASE 6 — STABLE & PRODUCTION-READY (Mai 2026)

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
