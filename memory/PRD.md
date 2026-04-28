# CodeForge AI - PRD

## Statut : PHASES 1 → 5 LIVRÉES (Avril 2026)

### Phases livrées
- **Phase 1** — Auth Google fixée (callback dédié, upsert session, axios interceptor) ✅
- **Phase 2** — Auto-deploy GitHub Actions → webhook `/api/admin/redeploy` ✅
- **Phase 3** — Durcissement sécurité + perf + UX onboarding ✅
- **Phase 4** — Polish UI/UX (Login, AuthCallback, Dashboard, glassmorphism) ✅
- **Phase 5** — Tests automatisés + monitoring + service worker + tooltips ✅

### Phase 5 — détails (iter_18 ALL GREEN)

**13. Tests automatisés**
- 8 tests pytest auth routes (`/app/backend/tests/test_auth_routes.py`) :
  - `TestSMSAuth` (3) : send code en demo mode, verify wrong code 401, verify success crée session
  - `TestAuthMe` (2) : 401 unauth, 200 + user authed
  - `TestLogout` (1) : déconnexion clears session
  - `TestSessionOAuth` (1) : invalid session_id 401
  - `TestMetrics` (1) : `/api/metrics` retourne tous les champs attendus
- Smoke E2E Playwright (`test_e2e_login.py`) : landing, login render, error toast, auth retry
- **Workflow CI `.github/workflows/ci.yml`** : pytest + playwright → deploy webhook (gates broken commits, remplace l'ancien `auto-deploy.yml`)

**14. Monitoring**
- Endpoint **`GET /api/metrics`** : `auth_errors_24h`, `auth_errors_by_kind_24h`, `total_users`, `total_projects`, `active_sessions`, `ts`
- Collection MongoDB `auth_errors` alimentée par helper `log_auth_error(kind, detail)` :
  - `sms_invalid_code` (SMS verify avec mauvais code)
  - `sms_code_expired` (code expiré)
  - `oauth_session_not_found` (OAuth fail)
- **Sentry React** intégré env-gated (`/app/frontend/src/lib/sentry.js`) : no-op si `REACT_APP_SENTRY_DSN` absent. Active automatiquement quand le DSN est fourni.

**15. Performance**
- Lazy-load déjà fait en Phase 3 (Dashboard, Create, Chat, Wizard via React.lazy)
- **Service Worker activé** (`/app/frontend/public/sw.js` + `/app/frontend/src/lib/serviceWorker.js`) :
  - Cache-first pour assets statiques
  - Network-first pour `/api/*`
  - Bypass complet pour `/api/auth/*` (jamais cacher)
  - Auto-cleanup des anciens caches au activate
  - Production-only (no-op en dev)

**16. Tooltips ?**
- Composant **`FeatureHint`** (`/app/frontend/src/components/FeatureHint.jsx`) basé sur Shadcn Tooltip
- Style : icône `?` bg-white/5 hover:bg-[#E4FF00]/20, tooltip dark glassmorphism
- `stopPropagation` pour ne pas déclencher le click parent
- Intégré sur Dashboard : modes section + bouton wizard

### Fonctionnalités complètes
| Fonctionnalité | Statut |
|----------------|--------|
| Landing | ✅ |
| Login (toast erreur + spinner Google + animations) | ✅ |
| AuthCallback (confetti + nom user + retry) | ✅ |
| Dashboard (avatar + stats + empty state + glassmorphism + tooltips) | ✅ |
| Wizard (35+ templates) | ✅ |
| Create (12 suggestions) | ✅ |
| Auth Google | ✅ |
| Auth SMS (démo) | ✅ |
| Génération IA (GPT-4o via Emergent) | ✅ |
| Export Mobile (PWA) | ✅ |
| Export Desktop (EXE via electron-builder + wine) | ✅ |
| Export Customizer (8 palettes + GitHub push) | ✅ (PAT configuré) |
| Historique chat projet | ✅ |
| Menu contextuel (clic droit) | ✅ |
| Auto-deploy GitHub Actions + tests gating | ✅ |
| Lazy-loading routes | ✅ |
| Onboarding tour (4 steps) | ✅ |
| Tests régression backend (11 passés) | ✅ |
| Monitoring (`/api/metrics`) | ✅ |
| Sentry frontend (env-gated) | ✅ |
| Service Worker offline cache | ✅ |
| Tooltips contextuels (FeatureHint) | ✅ |

### Architecture
```
Backend: FastAPI + MongoDB + Emergent GPT-4o
Frontend: React + CRA + TailwindCSS + Shadcn UI + Framer Motion
         + react-joyride + canvas-confetti + @sentry/react
Auth: Google OAuth + SMS (démo)
Desktop: Electron + electron-builder + wine
Mobile: PWA + Service Worker
GitHub: PyGithub + PAT (push apps + CI)
CI/CD: GitHub Actions → pytest → playwright → webhook redeploy
```

### Configuration .env
```
# obligatoires
MONGO_URL, DB_NAME, EMERGENT_LLM_KEY, DEPLOY_SECRET
# optionnelles
TWILIO_*                                # vide → demo mode
GITHUB_CLIENT_SECRET (PAT)              # configuré → push_to_github actif
REACT_APP_SENTRY_DSN                    # vide → Sentry inactif
```

### GitHub Actions secrets requis
```
DEPLOY_URL = https://no-code-builder-25.preview.emergentagent.com
DEPLOY_SECRET = 748ca32d60fa5367d3ba872e11d07fb8367296b9556ad0400c8cdd9a0e52314f
```

### Backlog futur (à confirmer avec utilisateur)
- 🔵 P0 — Mission finale annoncée par utilisateur (en attente brief)
- 🟡 P1 — Free Mobile SMS si user obtient credentials Free Mobile (compte famille)
- 🟢 P2 — i18n complet (anglais en plus du français)
- 🟢 P2 — Sentry DSN configuré côté frontend prod (REACT_APP_SENTRY_DSN)
- 🟢 P3 — Push token GitHub utilisateur stocké pour push_to_github multi-user

---
**Dernière mise à jour : 28 avril 2026 — Phases 1-5 livrées et 100% testées**
