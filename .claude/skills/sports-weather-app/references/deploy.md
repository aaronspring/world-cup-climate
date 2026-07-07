# Deploy to GitHub Pages

The scaffold ships `.github/workflows/pages.yml`, which builds the data + frontend
and publishes to Pages. Out of the box it uses the **demo** source, so the site
works with no secrets.

## One-time setup

1. Create the GitHub repo `owner/name` (the same `--repo` you passed to the
   scaffolder — the name must match, because the Vite `base` is `/name/`).
2. Push the scaffolded project to `main`.
3. In the repo: **Settings → Pages → Source → GitHub Actions**.
4. The workflow runs on push; the site appears at
   `https://<owner>.github.io/<name>/`.

## The base path must match the repo name

`frontend/vite.config.ts` sets `base: "/<name>/"`. Project Pages are served from
that sub-path, so a mismatch yields 404s on assets and data. If you rename the
repo, update `base` (and re-scaffold or edit by hand). For a **user/org page**
(`<owner>.github.io`) or a custom domain at the root, set `base: "/"`.

## What the workflow does

```
push to main / twice-daily cron / manual dispatch
  └─ build job
       uv run python backend/recompute.py --source demo   # regenerates frontend/public/data
       npm install && npm run build                       # tsc + vite -> frontend/dist
       upload-pages-artifact (frontend/dist)
  └─ deploy job -> deploy-pages
```

`frontend/public/data/` is git-ignored and rebuilt in CI, so committed data never
goes stale. The twice-daily cron keeps demo data re-rendering "today"; with the
IFS source it picks up fresh forecast cycles.

## Switching to live forecast data

1. Add a repo secret `ARRAYLAKE_TOKEN` (an `ema_...` token with access to the
   open IFS repo): **Settings → Secrets and variables → Actions**.
2. In `pages.yml`:
   - install the extra: change the recompute step to
     `run: uv sync --extra ifs && uv run python backend/recompute.py --source ifs`
   - pass the secret: add
     `env:` → `ARRAYLAKE_TOKEN: ${{ secrets.ARRAYLAKE_TOKEN }}` to that step.
3. Optionally align the cron to your forecast provider's write times (the parent
   world-cup-climate uses `30 7,19 * * *`, ~5 min after the long IFS runs land).

The IFS data pull is slow, so the workflow already sets
`concurrency: { group: pages, cancel-in-progress: false }` to let an in-progress
run finish rather than cancel it.

## Local preview before deploying

```bash
uv run python backend/recompute.py --source demo
cd frontend && npm install && npm run build && npm run preview
```

A green `npm run build` (it runs `tsc --noEmit` first) plus
`uv run python backend/test_recompute.py` is the bar before pushing.
