# CodeForge AI - PRD

## Statut : PHASE 4 COMPLÈTE (Avril 2026)

### Phases livrées
- **Phase 1** — Auth Google fixée (callback dédié, upsert session, axios interceptor) ✅
- **Phase 2** — Auto-deploy GitHub Actions → webhook `/api/admin/redeploy` ✅
- **Phase 3** — Durcissement sécurité + perf + UX onboarding ✅
- **Phase 4** — Polish UI/UX (Login, AuthCallback, Dashboard, glassmorphism) ✅

### Phase 4 — détails (iter_17 ALL GREEN)

**9. Login.js**
- Spinner Loader2 + texte "Redirection vers Google..." sur le bouton Google pendant la redirection
- Toast d'erreur affiché si query param `?error=xxx` (messages français pour `access_denied`, `invalid_request`, `server_error`, défaut)
- Animations Framer Motion stagger sur l'apparition du formulaire (logo, titre, boutons)
- Fix StrictMode subtil : `setTimeout` non-cleanup pour éviter que le double-invoke de useEffect ne tue le timer

**10. AuthCallback.js**
- 3 phases distinctes : `processing` (spinner + "Bienvenue, Marie..."), `success` (check vert + confetti 1s), `error` (icône warning + bouton "Réessayer")
- Confetti `canvas-confetti` aux couleurs de la marque (#E4FF00 + #00FF66 + blanc)
- Bouton "Réessayer" sur erreur → renvoie vers `/login` (au lieu de l'auto-redirect frustrant)
- Récupération du nom user via `response.data.name` ou fallback email

**11. Dashboard.js**
- Composant `UserMenu` (avatar Shadcn + dropdown) avec stats temps réel via `/api/user/stats` :
  - Projets créés (count MongoDB)
  - Plan actuel ("Gratuit illimité")
  - Dernier login (avant-dernière session)
  - Membre depuis (created_at user)
- Bouton de déconnexion dans le dropdown
- Composant `EmptyProjectsState` désigné si 0 projet :
  - SVG illustration animée (cercles concentriques rotatifs + carré jaune pulsant)
  - 2 CTAs : "Lancer l'assistant guidé" + "Créer librement"
  - Glow background gradient

**12. Glassmorphism + hover states**
- 4 cards mode (chat/create × online/offline) : `bg-white/[0.03] border-white/10 backdrop-blur-xl`
- Hover : `-translate-y-0.5` + `shadow-[0_8px_30px_rgba(228,255,0,0.2)]` (variantes par couleur de carte)
- Bouton wizard gradient : ajout du même hover-shadow
- Police Chivo (titres) + IBM Plex Sans (body) conservées

### Onboarding (Phase 3 + corrections Phase 4)
- `react-joyride@3.0.2` : 4 steps en français, déclenché 1× via flag `localStorage.codeforge_onboarded_v1`
- Selectors robustes via `data-tour="wizard"|"create"` (fonctionnent avec et sans projets)
- Persistance sur 3 chemins : Terminer, Passer (skip), X close
- API v3 correcte : `buttons: ['back','skip','primary','close']` per-step + `onEvent` au lieu de `callback`
- `hideOverlay` per-step → l'utilisateur peut continuer à interagir avec le reste de l'app

### Architecture
```
Backend: FastAPI + MongoDB + Emergent GPT-4o
Frontend: React + CRA + TailwindCSS + Shadcn UI + Framer Motion + react-joyride + canvas-confetti
Auth: Google OAuth + SMS (démo Twilio)
Desktop: Electron + electron-builder + wine
Mobile: PWA
GitHub: PyGithub (désactivé tant que PAT absent)
CI/CD: GitHub Actions → webhook → git fetch+reset+touch
```

### Fonctionnalités complètes
| Fonctionnalité | Statut |
|----------------|--------|
| Landing | ✅ |
| Login (toast erreur + spinner Google + animations) | ✅ |
| AuthCallback (confetti + nom user + retry) | ✅ |
| Dashboard (avatar + stats + empty state + glassmorphism) | ✅ |
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
| Onboarding tour (4 steps + persistance robuste) | ✅ |
| Tests régression backend | ✅ |

### Backlog (à valider avec utilisateur)
- 🔵 P0 — Phase 5 : QA finale (test integration toutes phases) + mission finale (annoncée)
- 🟡 P1 — User va fournir un PAT GitHub avec scope `repo` → activer push_to_github + retirer .env du tracking git
- 🟢 P2 — Sentry/LogRocket pour tracking erreurs frontend
- 🟢 P2 — i18n complet (anglais en plus du français)

### Configuration .env
```
# obligatoires
MONGO_URL, DB_NAME, EMERGENT_LLM_KEY, DEPLOY_SECRET
# optionnelles
TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_VERIFY_SERVICE_SID  # vide → demo mode
GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET (PAT)                      # vide → push_to_github désactivé
```

---
**Dernière mise à jour : 28 avril 2026 — Phase 4 livrée et 100% testée (iter_17 ALL GREEN)**
