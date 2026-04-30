# CodeForge AI - PRD

## Statut : VERSION ULTIME — STABLE & PRODUCTION-READY (Avril 2026)

### 30 Avril 2026 — Session 24 — VERSION FINALE
- **Mot de passe oublié** : `/auth/forgot-password` + `/auth/reset-password` (TTL 30 min, rate-limit 3/10 min, single-use, invalide toutes les sessions)
- **Page `/reset-password`** frontend (form + validation + écran d'erreur si lien expiré)
- **Auto-logout 401** : intercepteur axios global, redirige vers `/login?reason=session_expired`. Exempte les endpoints d'auth + pages publiques (anti-loop)
- **Cleanup task** asyncio (toutes les 10 min) : purge tokens expirés, sessions périmées, rate-limit >24h, auth_errors >7j
- **Health check enrichi** : `/api/health` → `{checks: {mongo, resend, ollama, github}}`
- **Idle timeout 1h** + bannière dismissible dans `/login`
- **Bug fix critique** trouvé par testing agent : AuthContext 401 interceptor redirigeait depuis pages publiques → patch (exempt /, /login, /sms-login, /verify-email, /reset-password + /api/auth/me)
- **Tests** : 72 passed / 3 skipped (DEPLOY_SECRET-gated)

### Sessions précédentes
- **Session 23** : Bouton "Renvoyer le lien" + audit (133 lignes code mort supprimées)
- **Session 22** : Cross-tab auto-unlock + TTL 5 min + messages français exacts + `/api/guide` HTML
- **Session 21** : Migration Email/Password + Magic Link (abandon Emergent Auth + Google OAuth)
- **Phase 5** : Tests automatisés + monitoring + service worker
- **Phase 4** : Polish UI/UX glassmorphism
- **Phase 3** : Sécurité + perf + UX
- **Phase 2** : Auto-deploy GitHub Actions
- **Phase 1** : Auth (remplacée par Email/Password)

## Routes actives
### Auth
- `POST /api/auth/register` (TTL 5 min, brute-force 5/15 min)
- `POST /api/auth/resend-verification` (3/10 min/email)
- `GET /api/auth/verify-email?token=xxx`
- `GET /api/auth/verification-status?token=xxx` (polling cross-tab)
- `POST /api/auth/login`
- `POST /api/auth/forgot-password` (NEW)
- `POST /api/auth/reset-password` (NEW)
- `GET /api/auth/me`
- `POST /api/auth/logout`
- `POST /api/auth/sms/send|verify` (mode démo)

### Système
- `GET /api/health` (checks détaillés)
- `GET /api/metrics` (auth_errors_24h, total_users, etc.)
- `GET /api/guide` (guide dépannage HTML)
- `POST /api/admin/redeploy` (webhook auto-deploy GitHub)

### Routes RETIRÉES (404)
- `POST /api/auth/session` (Emergent Auth)
- `GET/POST /api/auth/google/login|callback`

## Environnement
- `RESEND_API_KEY` ✅ — mode email RÉEL
- `EMAIL_FROM` : `CodeForge AI <onboarding@resend.dev>`
- `EMAIL_REPLY_TO` : `commandes.et.publicites@gmail.com` (silencieux)
- `FRONTEND_URL` configurée
- `MONGO_URL`, `DB_NAME`, `EMERGENT_LLM_KEY` configurés

## Santé du projet
- **Lint Python** : 0 warning
- **Lint JS** : 0 warning
- **Tests** : 72 passed / 3 skipped
- **Sécurité** :
  - bcrypt pour passwords
  - Brute-force 5/15 min/email
  - Rate-limit forgot-password 3/10 min
  - Rate-limit resend-verification 3/10 min
  - Tokens single-use (verify-email, reset-password)
  - Reset password invalide toutes sessions du user
  - Pas d'enumeration d'email (réponse neutre)
  - `password_hash` jamais retourné dans les réponses
  - Index unique sur users.email
  - 401 auto-clear côté frontend
- **Performance** : indexes MongoDB sur tous les lookups critiques + cleanup task background
- **Reliability** : health check avec checks détaillés, cleanup auto, intercepteur axios robuste

## Backlog futur
- **P1** : Documentation détaillée moteur de création IA (Ollama offline + GPT-4o online, illimité)
- **P2** : SMS gratuit Free Mobile API
- **P3** : Domaine custom DNS pour Resend (gratuit avec Cloudflare Registrar)
- **P4** : Refactoring server.py (>2700 lignes) en routes/ modules
- **P5** : Page Profil/Paramètres user (changement email, suppression compte RGPD)
