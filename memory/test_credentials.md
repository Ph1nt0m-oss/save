# Test Credentials

## Email/Password Auth (NEW — flow principal)
- Inscription via `/login` → onglet "Inscription" → Email + Mot de passe (≥6 char) + Nom (optionnel)
- Mode démo actif (pas de `RESEND_API_KEY`) → le lien de vérification est renvoyé **directement dans la réponse** du `POST /api/auth/register` sous la clé `verification_link`
- Le lien est aussi affiché dans l'UI sous la forme d'un encadré cyan cliquable
- Cliquer le lien → `GET /api/auth/verify-email?token=xxx` → utilisateur vérifié + session créée + redirect `/dashboard`
- Connexion suivante : onglet "Connexion" → email pré-rempli via `localStorage.codeforge_last_email` + mot de passe

### Test user à créer à la volée (exemple curl)
```bash
API=$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d '=' -f2)
EMAIL="test_$(date +%s)@gmail.com"

# Register
curl -s -X POST "$API/api/auth/register" -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"Pass1234\",\"frontend_url\":\"$API\"}" | python3 -m json.tool
# Copier le token depuis verification_link

# Verify
curl -s "$API/api/auth/verify-email?token=<TOKEN>" | python3 -m json.tool

# Login
curl -s -X POST "$API/api/auth/login" -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"Pass1234\"}" | python3 -m json.tool
```

### Règles
- Brute-force : 5 tentatives incorrectes / 15 min / email → 429
- Password min. 6 chars, email validé par regex
- Inscription sur un email existant **vérifié** → 409
- Inscription sur un email existant **non-vérifié** → nouveau lien magique (pas d'erreur)

## SMS Login (mode démo Twilio)
- Pas de clés Twilio configurées → mode démo actif
- N'importe quel numéro fonctionne (ex: `+33612345678`)
- Le code de vérification est imprimé dans l'UI au lieu d'être envoyé par SMS

## Google OAuth
- **SUPPRIMÉ**. Plus d'Emergent Auth, plus de Google OAuth natif.
- Remplacé par Email/Password + magic link.

## Webhook Auto-Deploy (Phase 2)
- `DEPLOY_SECRET` dans `/app/backend/.env` : `748ca32d60fa5367d3ba872e11d07fb8367296b9556ad0400c8cdd9a0e52314f`
- Endpoint : `POST /api/admin/redeploy` avec header `X-Deploy-Secret: <secret>`
- ⚠️ Ne PAS appeler ce endpoint avec le bon secret pendant les tests — il déclenche `git reset --hard`

## Tests pytest
```bash
cd /app && python3 -m pytest backend/tests/ -v
```

## Backend URL preview
`https://no-code-builder-25.preview.emergentagent.com` (depuis `/app/frontend/.env REACT_APP_BACKEND_URL`)

## FRONTEND_URL (backend/.env)
Ajouté : `FRONTEND_URL=https://no-code-builder-25.preview.emergentagent.com` — utilisé en fallback pour construire le lien magique si le body `frontend_url` n'est pas fourni.
