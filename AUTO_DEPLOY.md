# Auto-Deploy Setup (one-time, ~5 minutes)

After this is configured, every `git push` to `main` automatically deploys
to the live Emergent workspace — **no manual `git pull` ever needed again**.

## How it works

```
push → GitHub Actions → POST /api/admin/redeploy → git pull && restart backend
```

## One-time setup

### 1. Create the workflow file

The auto-deploy webhook endpoint is already deployed (see `backend/server.py`
`/api/admin/redeploy`). The matching GitHub Actions workflow YAML is **NOT**
in this repo because pushing to `.github/workflows/` requires a PAT with the
`workflow` scope (the standard PAT used to push code only doesn't have it).

Create the file manually via the GitHub web UI:

1. Go to https://github.com/Ph1nt0m-oss/save → **Add file** → **Create new file**
2. Filename: `.github/workflows/auto-deploy.yml`
3. Paste the content below:

```yaml
name: Auto-Deploy to Emergent

on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - name: Trigger redeploy webhook
        run: |
          if [ -z "${{ secrets.DEPLOY_URL }}" ] || [ -z "${{ secrets.DEPLOY_SECRET }}" ]; then
            echo "::warning::DEPLOY_URL or DEPLOY_SECRET secret missing — skipping."
            exit 0
          fi
          HTTP=$(curl -s -o /tmp/resp.json -w "%{http_code}" \
            -X POST "${{ secrets.DEPLOY_URL }}/api/admin/redeploy" \
            -H "X-Deploy-Secret: ${{ secrets.DEPLOY_SECRET }}" \
            --max-time 30 || echo "000")
          echo "HTTP $HTTP"
          cat /tmp/resp.json || true
          [ "$HTTP" = "200" ] || { echo "::error::Redeploy returned HTTP $HTTP"; exit 1; }

      - name: Verify new commit deployed
        if: success()
        run: |
          if [ -z "${{ secrets.DEPLOY_URL }}" ]; then exit 0; fi
          sleep 15
          DEPLOYED=$(curl -s "${{ secrets.DEPLOY_URL }}/api/health" | python3 -c "import sys,json; print(json.load(sys.stdin).get('commit','?'))" || echo "?")
          EXPECTED="${GITHUB_SHA::7}"
          echo "Expected: $EXPECTED | Deployed: $DEPLOYED"
          [ "$DEPLOYED" = "$EXPECTED" ] && echo "::notice::✅ Commit $EXPECTED is live" || echo "::warning::Mismatch"
```

4. Commit straight to main.

### 2. Generate a strong random secret

```bash
openssl rand -hex 32
# → e.g. "a3f8c91d…"
```

### 3. Add the secret to the deployed backend

In the Emergent workspace where the backend runs, add to `backend/.env`:

```
DEPLOY_SECRET=<the-secret-from-step-2>
```

Then `sudo supervisorctl restart backend` once.

### 4. Add 2 secrets to the GitHub repo

Settings → Secrets and variables → Actions → New repository secret:

| Name            | Value                                                     |
|-----------------|-----------------------------------------------------------|
| `DEPLOY_URL`    | `https://no-code-builder-25.preview.emergentagent.com`    |
| `DEPLOY_SECRET` | the same secret as in step 2                              |

### 5. Test it

Make any tiny change, push to `main`, and watch:

- Actions tab on GitHub → **Auto-Deploy to Emergent** workflow runs
- Should see `✅ Commit XXXXX is live`
- The deployed `/api/health` endpoint reports the new commit hash

## Security

- The webhook endpoint requires the `X-Deploy-Secret` header to match.
- Without `DEPLOY_SECRET` set in the backend env, the endpoint returns 503.
- Sudoers must allow `supervisorctl restart backend` (already the case on
  Emergent containers).

## Disabling

Delete the `DEPLOY_SECRET` entry from `backend/.env` and restart — the webhook
will return 503. The workflow then no-ops gracefully.
