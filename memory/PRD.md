# CodeForge AI - PRD

## Statut : PHASE 3 COMPLÈTE (Avril 2026)

### Phases livrées
- **Phase 1** — Auth Google fixée (callback dédié, upsert session, axios interceptor) ✅
- **Phase 2** — Auto-deploy GitHub Actions → webhook `/api/admin/redeploy` ✅
- **Phase 3** — Durcissement sécurité + perf + UX onboarding ✅

### Phase 3 — détails
1. **Webhook robuste** : `/api/admin/redeploy` utilise `git fetch + reset --hard origin/main` au lieu de `git pull` (résout les divergences). Backup/restore automatique de `backend/.env` et `frontend/.env` autour du reset (les `.env` sont trackés par GitHub). Réponse JSON enrichie : `commit`, `git_fetch`, `git_reset`, `env_preserved`.
2. **Hot-reload via touch** : `touch backend/server.py` au lieu de `sudo supervisorctl restart` en background → évite une race condition avec uvicorn watchfiles qui laissait supervisor en STOPPED.
3. **GitHub désactivé proprement** : `GITHUB_CLIENT_SECRET` vidé dans `.env` (était un OAuth secret invalide pour push_to_github qui requiert un PAT).
4. **Sudoers vérifié** : `sudo -n supervisorctl restart backend` fonctionne sans password.
5. **Lazy-load des routes protégées** : `React.lazy()` + `Suspense` pour Dashboard/Create/Chat/GuidedWizard. 4 chunks séparés en build prod (157 kB main + 4 chunks 2-26 kB).
6. **Onboarding interactif** : `react-joyride@3.0.2` avec tour 4 étapes au premier login (storage flag `codeforge_onboarded_v1`). Composant `/app/frontend/src/components/Onboarding.jsx`.
7. **Tests Pytest régression** : `/app/backend/tests/test_redeploy_webhook.py` (3 passés / 2 skipped intentionnellement, le happy-path est gated par `RUN_REDEPLOY_HAPPY_PATH=1` car il déclenche un reset destructeur).

### Fonctionnalités complètes
| Fonctionnalité | Statut |
|----------------|--------|
| Landing | ✅ |
| Dashboard + Stats + onboarding | ✅ |
| Wizard (35+ templates) | ✅ |
| Create (12 suggestions) | ✅ |
| Auth Google | ✅ |
| Auth SMS (démo Twilio) | ✅ |
| Génération IA (GPT-4o via Emergent) | ✅ |
| Export Mobile (PWA) | ✅ |
| Export Desktop (EXE via electron-builder + wine) | ✅ |
| Export Customizer (8 palettes + GitHub push) | ⚠️ GitHub désactivé (PAT requis) |
| Historique chat projet | ✅ |
| Menu contextuel (clic droit) | ✅ |
| Auto-deploy GitHub Actions | ✅ |
| Lazy-loading routes | ✅ |
| Onboarding tour | ✅ |
| Tests régression backend | ✅ |

### Architecture
```
Backend: FastAPI + MongoDB + Emergent GPT-4o
Frontend: React + Vite/CRA + TailwindCSS + Shadcn UI + Framer Motion + react-joyride
Auth: Google OAuth + SMS (démo Twilio)
Desktop: Electron + electron-builder + wine
Mobile: PWA
GitHub: PyGithub (désactivé tant que PAT absent)
CI/CD: GitHub Actions → webhook → git fetch+reset+touch
```

### Configuration .env
```
# obligatoires
MONGO_URL, DB_NAME, EMERGENT_LLM_KEY, DEPLOY_SECRET
# optionnelles
TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_VERIFY_SERVICE_SID  # vide → demo mode
GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET (PAT)                      # vide → push_to_github désactivé
```

### Backlog (Phase 4 et au-delà — à valider avec l'utilisateur)
- 🔵 P0 — User va fournir un PAT GitHub avec scope `repo` → activer push_to_github + permettre `git rm --cached backend/.env` pour ne plus tracker les secrets
- 🟡 P1 — Tests E2E Playwright dans `.github/workflows/` (Google Login, SMS demo, génération app)
- 🟢 P2 — Sentry/LogRocket pour tracking erreurs frontend
- 🟢 P2 — i18n complet (anglais en plus du français)

### Phase finale (annoncée par utilisateur)
Phase 4 (en attente du brief utilisateur) puis Phase 5 (vérification finale + tests intégrés sur toutes les phases).

---
**Dernière mise à jour : 28 avril 2026 — Phase 3 livrée et testée**
