# Auto-Deploy Setup (one-time, ~3 minutes)

After this is configured, every `git push` to `main` automatically deploys
to the live Emergent workspace — no manual `git pull` ever needed again.

## How it works

```
push → GitHub Actions → POST /api/admin/redeploy → git pull && restart backend
```

## One-time setup

### 1. Generate a strong random secret

```bash
openssl rand -hex 32
# → e.g. "a3f8c91d…"
```

### 2. Add the secret to the deployed backend

In the Emergent workspace where the backend runs, add to `backend/.env`:

```
DEPLOY_SECRET=<the-secret-from-step-1>
```

Then `sudo supervisorctl restart backend` once.

### 3. Add 2 secrets to the GitHub repo

Settings → Secrets and variables → Actions → New repository secret:

| Name            | Value                                                     |
|-----------------|-----------------------------------------------------------|
| `DEPLOY_URL`    | `https://no-code-builder-25.preview.emergentagent.com`    |
| `DEPLOY_SECRET` | the same secret as in step 1                              |

### 4. Test it

Make any tiny change, push to main, and watch:

- Actions tab on GitHub → `Auto-Deploy to Emergent` workflow runs
- Should see "✅ Deploy verified — commit XXXXX is live"
- The deployed `/api/health` endpoint will report the new commit hash

## Security

- The webhook endpoint requires the `X-Deploy-Secret` header to match.
- The secret is never logged.
- Without `DEPLOY_SECRET` set, the workflow no-ops gracefully.
- Sudoers must allow `supervisorctl restart backend` for the backend user
  (already the case on Emergent containers).

## Disabling

Delete the `DEPLOY_SECRET` entry from `backend/.env` and restart — the endpoint
will return 503 to any caller. The workflow will then no-op.
