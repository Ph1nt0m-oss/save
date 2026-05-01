# Test Credentials

## Email/Password Auth (flow principal — mode RÉEL Resend activé)
- Inscription via `/login` → onglet **Inscription** → Email Gmail + Mot de passe (≥6 char) + Nom (optionnel)
- Mode RÉEL : email Resend envoyé depuis `CodeForge AI <onboarding@resend.dev>` avec Reply-To silencieux vers `commandes.et.publicites@gmail.com`
- Lien magique TTL **5 min** ; cliquer le lien certifie le compte → l'onglet d'origine se déverrouille automatiquement (polling 2s) et navigue vers `/dashboard`
- Bouton **"Renvoyer le lien"** dans le banner d'attente (rate-limit 3/10 min/email)
- Si banner déclenche un 429, bouton désactivé visuellement pendant 10 min

## Forgot Password (REWRITTEN iter_30 — "set then confirm" flow)
- Lien "Mot de passe oublié ?" sous le bouton Connexion → bascule en mode `forgot`
- Saisir email + nouveau mot de passe + confirmation (≥6 chars)
- POST `/api/auth/forgot-password` `{email, password, frontend_url}` → backend hash le nouveau mdp et le stocke en attente sur le token (30 min)
- Resend envoie "Veuillez cliquer ici pour confirmer la réinitialisation de votre mot de passe"
- Clic sur le lien → GET `/api/auth/confirm-password-reset?token=xxx` applique le mdp + invalide toutes sessions + page HTML succès → redirect /login
- Token single-use, expire 30 min
- Rate-limit 3/10 min/email

## Test user actif
- **Email** : `test_dash_1777658375@gmail.com`
- **Password** : `Pass1234` (état actuel — l'agent de test a effectué un round-trip change → restauré)

## Idle Timeout (NEW iter_24)
- 1h sans activité (mouse/keyboard/touch/scroll/wheel/visibility) → logout auto + `/login?reason=idle`
- Bannière orange dismissible avec bouton X (data-testid `idle-logout-banner` + `idle-logout-banner-close`)

## Auto-redirect Session Expirée (NEW iter_24)
- Tout endpoint `/api/*` qui retourne 401 (sauf endpoints d'auth eux-mêmes et `/auth/me`) déclenche auto-clear localStorage + redirect `/login?reason=session_expired`
- Pages publiques (/, /login, /sms-login, /verify-email, /reset-password) exemptées → pas de redirect en boucle

## SMS Login (mode démo Twilio)
- N'importe quel numéro fonctionne ; le code s'imprime dans l'UI

## Test user à créer (curl)
```bash
API=$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d '=' -f2)
EMAIL="test_$(date +%s)@gmail.com"
# 1. Register
curl -s -X POST "$API/api/auth/register" -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"Pass1234\",\"frontend_url\":\"$API\"}"
# Avec RESEND_API_KEY active : email envoyé. Sinon mode démo : verification_link dans la réponse.
# 2. Verify avec le token reçu par email ou dans la réponse
# 3. Login
curl -s -X POST "$API/api/auth/login" -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"Pass1234\"}"
```

## Endpoints critiques
- `POST /api/auth/register` (5 min TTL)
- `POST /api/auth/resend-verification` (3/10 min/email)
- `GET /api/auth/verify-email?token=xxx`
- `GET /api/auth/verification-status?token=xxx` (polling)
- `POST /api/auth/login` (brute-force 5/15 min/email)
- `POST /api/auth/forgot-password` (3/10 min/email, neutral msg si user inconnu)
- `POST /api/auth/reset-password` (single-use, invalide toutes sessions)
- `GET /api/auth/me` (Bearer / cookie)
- `POST /api/auth/logout`
- `GET /api/health` (checks mongo/resend/ollama/github)
- `GET /api/guide` (HTML guide dépannage)
- `GET /api/metrics` (auth_errors_24h, etc.)

## Routes RETIRÉES
- `POST /api/auth/session` (Emergent) → 404
- `GET/POST /api/auth/google/login|callback` (OAuth natif) → 404

## Webhook Auto-Deploy
- `DEPLOY_SECRET` dans `/app/backend/.env`
- Endpoint : `POST /api/admin/redeploy` avec header `X-Deploy-Secret`

## Cleanup task (NEW iter_24)
- Background task asyncio toutes les 10 min : purge tokens expirés, sessions périmées, rate-limit data >24h, auth_errors >7j

## Backend URL preview
`https://no-code-builder-25.preview.emergentagent.com`

## ENV importants
- `RESEND_API_KEY` : ✅ configurée — mode email RÉEL actif
- `EMAIL_FROM` : `CodeForge AI <onboarding@resend.dev>`
- `EMAIL_REPLY_TO` : `commandes.et.publicites@gmail.com` (catch-all silencieux)
- `FRONTEND_URL` : `https://no-code-builder-25.preview.emergentagent.com`
