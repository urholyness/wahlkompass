# CLAUDE CODE — END-TO-END HANDOFF (Germany, live on Cloudflare)

**You are Claude Code running on George's machine.** You have what the cloud
session that built this repo did **not**: open internet (to reach the German
data APIs) and the ability to deploy. George runs nothing by hand — **you do the
ingestion, the release build, and the deploy.** Your job: take this repo from
"verified preview" to **live end-to-end on Cloudflare Pages with real Bundestag
data**, Germany only.

> Why this handoff exists: the Cowork cloud sandbox that wrote this code is
> network-restricted (it cannot reach `dip.bundestag.de`, `dawum.de`,
> `abgeordnetenwatch.de`, or `bundestag.de` — 403 at the egress proxy), and the
> desktop bridge has no network either. So live pulls + deploy must run where you
> are. Everything below the "BUILD" line is already done and tested; everything
> under "YOUR TASKS" is yours.

---

## What this is
Wahlkompass — a belegbasierter (evidence-based) Wahlkompass. A citizen answers
~32 concrete policy statements; the tool scores every party by evidence-derived
positions (roll-call votes > programmes > coded data), client-side, no user data
collected, deterministic (no ML in the scoring path), shipped as signed static
"data releases". Signature feature: **Sagen vs. Tun** (says-vs-did divergence).
Full design: `wahlkompass-consolidated-design-v1.2.md` (authoritative) +
`wahlkompass-architecture-v1.1-amendments.md`. Frontend design: the wireframes
in the Claude Design handoff (`wahlkompass-frontend-design-spec.md`).

**Scope now: Germany / Bundestag only, end to end.** UK/EU/US are later and get
their own ingestion pipeline (different APIs) reusing this scoring core. Do not
build them now.

**Non-negotiables (D1–D6, enforced by the code + tests):** score concrete
statements not categories; client-side only; deterministic scoring; releases not
a live DB; descriptive never predictive; no ML in the score path. Keep the §9
bias suite and `reproduce.py` green on every release.

---

## BUILD — already done & verified (don't redo; extend)
- `pipeline/src/aggregation.py` — v1.2 aggregation engine (τ·ρ·item_weight, admission rule, confidence, Sagen/Tun). 28/28 tests green.
- `pipeline/src/scoring.py` — reference match scorer S(P), CI half-widths, ties-as-ties, <10 low-coverage. **The frontend JS scorer is a byte-parity port of this (verified equal).**
- `pipeline/src/ingestors/bundestag_xml_parser.py` — roll-call XML → per-Fraktion direction=(Y−N)/(Y+N), participation item_weight, unified-abstention exclusion, FCI.
- `pipeline/src/ingestors/dip_api_client.py` — DIP REST client (reads `DIP_API_KEY` from env).
- `pipeline/src/probes/` — reachability probes for bundestag XML / dip / dawum.
- `tools/reproduce.py` — independent verifier; reads methodology from the release; exact byte-identical compare.
- `tools/release_builder.py` — statements+parties+evidence → v1.2 aggregation → signed bundle (`data-releases/2026.11.0-preview/`, Ed25519). **PROVISIONAL data, labelled `meta.preview=true`.**
- `tools/build_frontend.py` → `frontend/dist/index.html` — self-contained mobile core flow (Start · Fragebogen · Ergebnis · Beleg-Zug · Methodik) on the design tokens, bundle inlined.
- `pipeline/tests/` — aggregation, parser, reproduce, scoring, **bias suite (§9: determinism, party-symmetry, mirror, no-imputation)**.

Sanity check before you start:
```bash
cd pipeline && PYTHONPATH="$PWD:$PWD/.." python -m unittest discover -s tests -q
cd .. && PYTHONPATH="pipeline" python tools/reproduce.py data-releases/2026.11.0-preview   # -> SUCCESS
```

---

## YOUR TASKS (in order)

### 0. Repo + secrets
- `git init` if needed; commit the current tree as the baseline. Add `.gitignore` (already provided): `.env`, `__pycache__`, `.venv`, `node_modules`, `_backup_*`, `frontend/dist` optional.
- **DIP key is a credential — never commit it.** George has one (provided out-of-band; may be the public demo key). Put it in `.env` as `DIP_API_KEY=…` and load via env. Set the same value as a Cloudflare/CI secret later.
- Public DIP demo key expired end of 05/2026 — if George's key 401s, register a fresh free key at `dip.bundestag.de` (Base URL `https://search.dip.bundestag.de/api/v1/`, auth header `Authorization: ApiKey <key>` or `?apikey=<key>`).

### 1. Live ingestion (this is the part only you can run)
Turn the probes/clients into real ingesters writing verified `evidence_item`s. Sources, all Germany:
| Source | Auth | Gives | Tier |
|---|---|---|---|
| Bundestag roll-call XML (`bundestag.de/parlament/plenum/abstimmung/liste` → per-vote XML) | none | namentliche Abstimmungen | T1 |
| DIP API (`search.dip.bundestag.de/api/v1`) | `DIP_API_KEY` | bills/Anträge/Drucksachen | T1 |
| abgeordnetenwatch v2 (`www.abgeordnetenwatch.de/api/v2`) | none | party/candidate positions, cross-check | T3 |
| dawum (`api.dawum.de`) | none | polls → seat projection (coalition view) | — |
| Wahl-O-Mat 2025 (bpb) + Manifesto Project (WZB) | extract / free reg | self-declarations, coded programmes | T2/T3 |

- Fetch → SHA-256 → store raw → parse (deterministic) → propose `evidence_item`s. Roll-call parsing is done (`bundestag_xml_parser`); write the **bill↔statement linking** step (the one human-judgment mapping — for now auto-propose candidates and label them provisional; real releases need dual-coding via `portal/`).
- Keep everything idempotent (nightly cron friendly).

### 2. Statement set (honest scope)
The board-approved 32 is deliberately slow editorial work (D1). For the first live release, use a **provisional preview set** and keep `meta.preview=true` + the label visible in the UI (already wired). Options, pick with George: (a) keep the 15 in `release_builder.py`, (b) swap in the real Wahl-O-Mat 2025 theses (sort bpb licensing before any non-preview launch), (c) George's own list. Promotion to a board-approved release is a data change, **no code change**.

### 3. Real release
- Generate a **held signing key** (don't ship the ephemeral demo key): `minisign -G` or an Ed25519 key kept in a secret store; wire it into `release_builder.py` in place of the per-run keypair. (Design wants an eventual 2-of-3 ceremony — fine to start single-key.)
- Run `release_builder.py` against the **real ingested evidence** → new `data-releases/<tag>/`.
- `reproduce.py <release>` MUST pass. Run the `pipeline/tests` §9 bias suite. A red suite blocks the release.

### 4. Frontend for production
- `build_frontend.py` currently **inlines** the bundle for the preview. For deploy, switch the `RELEASE` const to `fetch()` the signed bundle from the CDN **and verify the Ed25519 signature in-browser** (SubtleCrypto `Ed25519`; the builder emits `meta.signature_b64`, `meta.pubkey_b64`, `meta.signed_payload`, plus `release.sig`/`pubkey.ed25519`). Pin the pubkey in the build. Show the Prüfsiegel from the real verification result; on failure, block with the "Signatur fehlt" state.
- Then build out the rest of the wireframes (desktop "Bloomberg" terminal, Koalitionen from `dawum` seats + an exclusions matrix, Sagen-vs-Tun screen, Themen). Mobile core flow is done.
- Keep the neutrality hard rules (equal-size party chips, ties-as-ties, "keine belegbare Position" as a designed state, CI always shown, all ballot parties).

### 5. Deploy (Cloudflare — George has an account)
- `frontend/dist` is the static site. Deploy with Wrangler: `npx wrangler pages deploy frontend/dist --project-name wahlkompass`. First deploy → live on `https://wahlkompass.pages.dev`.
- Put the signed release bundle on the same origin (e.g. `frontend/dist/release/…`) or R2; long-cache immutable release-tagged paths, short-cache `meta.json`.
- Custom domain when George buys it: `demokratie.de` (target) — for now a `.app` is fine; add it in Cloudflare Pages → Custom domains and set DNS. **Serve only via the CDN; never off raw GitHub URLs.**

### 6. Automate + verify (fast-follow)
- GitHub Action (open egress): nightly `ingest → release_builder → reproduce → tests → wrangler deploy`. DIP key + signing key as GH secrets.
- Independent **release monitor** on separate infra (a scheduled Action outside the prod project) that re-fetches the bundle, re-verifies the signature + reproduces positions, and alerts on mismatch (design §7).
- Port `scoring.py` → `engine/` TypeScript module and add a CI test asserting it matches `scoring.py` on a golden user set (the frontend JS is already parity-checked; this makes it a first-class module).

---

## Definition of done (first live release)
1. `wahlkompass.pages.dev` (or the domain) loads, questionnaire → ranked results with CI, Beleg-Zug shows real vote extracts with source links + hashes, Sagen-vs-Tun fires on real divergences.
2. The served bundle is signed and **verifies in-browser**; `reproduce.py` regenerates `positions.json` from `evidence.json` exactly.
3. §9 bias suite + all pipeline tests green in CI.
4. `meta.preview=true` and the preview label are visible until a board-approved statement set + dual-coded links replace the provisional data.
5. No user-data path exists (grep + review); no ML in the scoring path.

## Key files
`wahlkompass-consolidated-design-v1.2.md` · `v1.2-reconciliation.md` · `tools/release_builder.py` · `tools/build_frontend.py` · `tools/reproduce.py` · `pipeline/src/{aggregation,scoring}.py` · `pipeline/src/ingestors/*` · `pipeline/tests/*` · `frontend/dist/index.html` · `data-releases/2026.11.0-preview/`
