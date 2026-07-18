# Nightly CI setup (GitHub Actions → Cloudflare Pages)

The workflow `.github/workflows/nightly.yml` rebuilds the signed release from
live sources every night and redeploys it. It runs the **deterministic** part of
the pipeline only:

```
ingest (votes/polls/DIP/seats) → verify T2 quotes vs PDF → assemble evidence
  → aggregate (v1.2) → sign (held key) → reproduce.py → tests → build frontend → deploy
```

The **coding** step (programme-quote extraction, vote↔statement alignment) is
*not* in CI — it is committed data (`pipeline/data/links/links.json`,
`pipeline/data/t2/`) and changes only through a human-gated run. New roll-call
votes and fresh poll numbers are picked up automatically; party positions change
only when a human re-codes them.

## Required repository secrets

Set these at **GitHub → repo → Settings → Secrets and variables → Actions**:

| Secret | What it is | How to get it |
|---|---|---|
| `DIP_API_KEY` | Bundestag DIP API key | from `.env`; register a free key at dip.bundestag.de |
| `RELEASE_SIGNING_KEY_B64` | base64 of the **held** Ed25519 PEM | see below — must be the SAME key used locally, or the pinned pubkey in the frontend won't match |
| `CLOUDFLARE_API_TOKEN` | token with **Account › Cloudflare Pages › Edit** | Cloudflare dashboard → My Profile → API Tokens |
| `CLOUDFLARE_ACCOUNT_ID` | your account id | Cloudflare dashboard URL / Workers & Pages sidebar |

### Producing `RELEASE_SIGNING_KEY_B64`

The signing key must be identical to the local `release-signing-2026.sec`, because
the frontend pins the public key at build time. Produce the base64 locally and
paste it into the secret (never commit it, never echo it in a workflow):

```bash
# from the wahlkompass/ directory
base64 -w0 release-signing-2026.sec        # Linux
base64 -i release-signing-2026.sec | tr -d '\n'   # macOS
# Windows PowerShell:
[Convert]::ToBase64String([IO.File]::ReadAllBytes("release-signing-2026.sec"))
```

`release_builder.py` reads `RELEASE_SIGNING_KEY_B64` from the environment before
falling back to the file path in `RELEASE_SIGNING_KEY`, so CI needs only the
base64 secret.

## Alternative: Git-connected Pages (no wrangler in CI)

Instead of the `wrangler-action` deploy step you can connect the repo in the
Cloudflare dashboard (**Workers & Pages → Create → Pages → Connect to Git →
`wahlkompass`**, build output directory `wahlkompass/frontend/dist`, no build
command). Then the nightly job's commit-back of the regenerated `frontend/dist`
auto-deploys, and you can drop the Cloudflare secrets from Actions.

## Manual run

Trigger any time from **Actions → nightly-release → Run workflow**, or locally:

```bash
cd wahlkompass && python tools/run_pipeline.py
npx wrangler pages deploy frontend/dist --project-name wahlkompass
```
