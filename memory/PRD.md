# CodeForge AI - PRD

## Statut : PHASES 1 → 5 LIVRÉES + Migration Auth + Polish (Avril 2026)

### 30 Avril 2026 — Session 23 — Audit + Resend + Bouton renvoi
- **P1 Mode email réel (Resend)** : code prêt, attend seulement `RESEND_API_KEY` dans `/app/backend/.env` (3000 emails/mois gratuits)
- **P2 Audit complet** : ruff + ESLint 100% propres. 133 lignes de code mort supprimées (dead code après `return` dans `/export/mobile/`). Tests backend refactorés pour refléter le nouveau flow cross-tab
- **P3 Bouton "Renvoyer le lien"** : `POST /api/auth/resend-verification` rate-limité 3/10 min/email. UI avec cooldown visuel (bouton désactivé 10 min après un 429)
- **Tests** : 54 passed / 3 skipped. iter_23 all green

### 30 Avril 2026 — Session 22 — Cross-tab auto-unlock + TTL 5 min
- TTL lien magique réduit de 30 min → 5 min
- Messages français exacts (valide vs expiré)
- Poll `/api/auth/verification-status` toutes les 2s par l'onglet d'origine
- Token single-use : 2ème poll après consommation = expired
- `GET /api/guide` : guide dépannage GitHub accessible en HTML stylé

### 30 Avril 2026 — Session 21 — Migration Email/Password + Magic Link
- **ABANDON** d'Emergent Auth + Google OAuth natif (bugs récurrents, pas de clés)
- Auth classique Email + MDP + lien magique (bcrypt + sessions MongoDB)
- Routes : `POST /auth/register`, `GET /auth/verify-email`, `POST /auth/login`, `POST /auth/resend-verification`, `GET /auth/verification-status`, `GET /auth/me`, `POST /auth/logout`
- Mode démo : `verification_link` retourné dans la réponse si `RESEND_API_KEY` absent
- Frontend : onglets Connexion/Inscription, email mémorisé via `localStorage.codeforge_last_email`
- Sécurité : bcrypt, brute-force 5 fails/15min/email, index unique users.email, `password_hash` jamais retourné

### Phases livrées antérieurement
- **Phase 1** — Auth Google fixée (remplacée par Email/Password le 30/04/2026)
- **Phase 2** — Auto-deploy GitHub Actions webhook ✅
- **Phase 3** — Durcissement sécurité + perf + UX onboarding ✅
- **Phase 4** — Polish UI/UX glassmorphism ✅
- **Phase 5** — Tests automatisés + monitoring + service worker + tooltips ✅

## Routes actives (auth)
- `POST /api/auth/register` — email+password → lien magique (5 min)
- `POST /api/auth/resend-verification` — renvoi rate-limité (3/10 min/email)
- `GET /api/auth/verify-email?token=xxx` — consomme le lien magique, pas de cookie
- `GET /api/auth/verification-status?token=xxx` — polling cross-tab
- `POST /api/auth/login` — email+password → session (cookie + body)
- `GET /api/auth/me` — user courant (sans password_hash)
- `POST /api/auth/logout` — clear session
- `POST /api/auth/sms/send|verify` — mode démo SMS (inchangé)
- `GET /api/guide` — guide dépannage GitHub en HTML

## Routes retirées
- `POST /api/auth/session` (Emergent Auth) → 404
- `GET/POST /api/auth/google/login|callback` (Google OAuth natif) → 404

## Next steps
- **P1** : Ajouter `RESEND_API_KEY` pour activer le mode email réel (user input)
- **P4** : Rédaction détaillée du moteur de création IA (Ollama offline + GPT-4o online, illimité)
- **P5** : Reprendre SMS gratuit Free Mobile API (backlog)

## Santé du projet
- Lint Python : 0 warning (ruff all clean)
- Lint JS : 0 warning (ESLint all clean)
- Tests : 54 passed / 3 skipped (happy-path redeploy gated par `RUN_REDEPLOY_HAPPY_PATH=1`)
- Sécurité : auth email robuste, pas de leak de data, bcrypt, brute-force protection, rate limit renvoi
- Performance : index MongoDB sur users.email, email_verifications.token, user_sessions.session_token, login_attempts, resend_attempts
