# Test Credentials

## SMS Login (mode démo Twilio)
- Pas de clés Twilio configurées → mode démo actif
- N'importe quel numéro fonctionne (ex: `+33612345678`)
- Le code de vérification est imprimé dans l'UI au lieu d'être envoyé par SMS

## Google OAuth
- Flux Emergent-managed
- Login via bouton "Continuer avec Google" sur `/login`
- Redirige vers `/auth/callback` puis `/dashboard`

## Webhook Auto-Deploy (Phase 2)
- DEPLOY_SECRET dans `/app/backend/.env` : `748ca32d60fa5367d3ba872e11d07fb8367296b9556ad0400c8cdd9a0e52314f`
- Endpoint : `POST /api/admin/redeploy` avec header `X-Deploy-Secret: <secret>`
- ⚠️ Ne PAS appeler ce endpoint avec le bon secret pendant les tests — il déclenche `git reset --hard` qui efface les changements locaux non poussés sur GitHub

## Tests pytest régression
```
cd /app && python3 -m pytest backend/tests/test_redeploy_webhook.py -v
```
Attendu : 3 passed, 2 skipped (le happy-path est gated par `RUN_REDEPLOY_HAPPY_PATH=1`).

## Backend URL preview
`https://no-code-builder-25.preview.emergentagent.com` (depuis `/app/frontend/.env REACT_APP_BACKEND_URL`)
