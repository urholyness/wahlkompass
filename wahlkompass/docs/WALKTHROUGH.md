# Wahlkompass — how it works, end to end

A walkthrough of the whole machine: what happens to real Bundestag data on its
way to a number on screen, the exact math in the middle, the guarantees that keep
it neutral, and what is left to reach a public, board-approved launch ("Z").

Everything below is what the code actually does today (see `pipeline/src`,
`tools/`), against live sources, with `meta.preview = true` until a Beirat signs
off the statement set and the coding.

---

## 1. The shape of the thing

A citizen answers concrete policy statements. For every party the tool shows how
close that party is to them — and every number is one tap from the documents that
produced it. Three properties make it unusual:

- **Evidence-based**, not self-declaration only: a party's position is derived
  from what it *did* (roll-call votes) and *said* (programme), not from a
  questionnaire the party filled in.
- **Client-side and reproducible**: the scoring runs in your browser; the inputs
  are a signed, publicly re-computable data bundle. No account, no server, no user
  data. A million users cost the same as one.
- **Honest about ignorance**: where there is no admissible evidence, the cell is
  "keine belegbare Position" — never a guessed 0.

---

## 2. The pipeline (five stages)

```
 (1) INGEST ─────► (2) CODE ─────► (3) AGGREGATE ─────► (4) SIGN ─────► (5) SERVE
 live sources     what each vote    the v1.2 math       held Ed25519    static bundle
 (deterministic)  means (gated)     (deterministic)     key             on Cloudflare
```

### (1) Ingest — deterministic, automated
Pulls raw material from open sources and content-addresses every byte
(`pipeline/src/ingest/`, cache in `pipeline/data/raw/`):

| Source | Gives | Tier |
|---|---|---|
| Bundestag roll-call **XLSX** (`bundestag.de`) | namentliche Abstimmungen, per-Fraktion tallies | T1 |
| **DIP** API (`search.dip.bundestag.de`) | bill/Antrag metadata | T1 context |
| **abgeordnetenwatch** v2 | per-mandate votes, Drucksache links (cross-check) | T3 |
| **dawum** (`api.dawum.de`) | polls → seat projection (Koalitionen) | — |
| party **Wahlprogramme** 2025 (PDF) | stated positions | T2 |

Note from reality: the Bundestag retired per-vote **XML** in the 2025/26 relaunch,
so the parser reads XLSX (`bundestag_xml_parser` → `bundestag_xlsx_parser`).

### (2) Code — the one human-judgment step (gated)
Raw data is not evidence until someone decides *what it means*:

- **T1 (votes):** for each (vote, statement), does a *Ja* affirm or reject the
  statement? Coded in `pipeline/data/links/links.json`. This is the only place a
  vote can be misread, so it is deliberately conservative — and where a party's
  Ja/Nein is off-axis (an opposition *Nein* that means "not far enough", or a
  coalition *Nein* that is procedural), that party is excluded from the link and
  falls to "keine belegbare Position". Same rule for every party.
- **T2 (programmes):** verbatim quotes are proposed, then **mechanically verified**
  — `t2_verify.py` downloads the party's programme PDF and confirms the quote
  appears in it (whitespace/hyphenation-insensitive but otherwise exact). A
  paraphrase is dropped. Only quotes that are really in the document survive.

For the preview this coding is assisted (LLM-proposed, machine-verified); a
board-approved release requires **human dual-coding** via the `portal/`. Coding is
data, not code — replacing it changes no Python.

### (3) Aggregate — deterministic (the methodology; §3 below)
`release_builder.py` runs the v1.2 engine over statements × parties × evidence and
writes `positions.json`.

### (4) Sign — held key
The builder hashes the exact bytes of every content file into a manifest and signs
the manifest with a held **Ed25519** key (`release.sig`, `pubkey.ed25519`,
`meta.signed_payload`). Single key today; a 2-of-3 ceremony later.

### (5) Serve — static, verified in the browser
`build_frontend.py` emits a static site that **fetches** the bundle and, before
rendering a single number, verifies it in the browser: pinned pubkey → Ed25519
signature over the manifest → SHA-256 of every file. Any mismatch blocks with
"Signatur fehlt". The Prüfsiegel is the *result* of that check, not decoration.

---

## 3. The methodology — the actual math

All symbols below are exactly what `pipeline/src/aggregation.py` and
`pipeline/src/scoring.py` compute. Constants live in
`pipeline/evidence_config/deu-bundestag.yaml` and are **pinned into every release**
(`methodology.json`) so the numbers are reproducible forever.

### 3.1 From a roll-call vote to a single evidence item
For a Fraktion on one namentliche Abstimmung with Y "Ja", N "Nein", E "Enthaltung":

```
direction   x  = (Y − N) / (Y + N)            # active votes only, in [−1, 1]
item_weight    = (Y + N) / (Y + N + E)        # participation share, in [0, 1]
```

A **unified abstention** (participation < 0.10) is a strategic bloc abstention
(coalition discipline, not neutrality); its `item_weight` is set to 0 — it is shown
in the drawer but never scored. Scoring a closed abstention as "0 = neutral" was a
category error the v1.2 design fixed. A display-only **Fraktion Cohesion Index**
`FCI = max(Y,N,E)/(Y+N+E)` shows intra-party division but never modifies a score.

A programme quote (T2) becomes an item with a coded `direction ∈ [−1,1]` and
`item_weight = 1`.

### 3.2 Weighting an item
Each item is weighted by three independent factors:

```
τ  = tier weight            T1 = 1.0,  T2 = 0.8,  T3 = 0.6,  T4 = 0.3   (behaviour > word > code)
ρ  = recency decay          ρ = e^(−λ · age_years),  λ = ln 2 / 4        (4-year half-life)
w  = item_weight            participation share (T1) or 1 (T2)

effective weight   wₑ = τ · ρ · w
```

T1 evidence older than **8 years** (two legislative periods) is dropped entirely —
a party that still holds the position will have re-stated it more recently.

### 3.3 The position p and its confidence c
Over the admissible items in a party×statement cell:

```
p  = Σ (wₑ · x) / Σ wₑ                                   # stance, in [−1, 1]

volume     v = 1 − e^(−Σwₑ / W₀),   W₀ ≈ 1.303           # "is there enough evidence?"  → 90% at 3 full items
agreement  a = 1 − min(1, σ),   σ = √( Σ wₑ (x − p)² / Σ wₑ )   # "does the evidence agree?"
confidence c = v · a                                     # in [0, 1]
```

Low volume (little evidence) **or** low agreement (contradictory evidence) both
lower confidence, which later *widens the error bar* — it never nudges the
position itself.

### 3.4 Admission — "keine belegbare Position"
A cell gets a position only if it is **admissible**: at least one T1/T2 item, or at
least three concordant T3 items. Otherwise `p = null` and the UI renders the
designed absence. Nothing is imputed.

### 3.5 Sagen vs. Tun (the signature feature)
Compute the position from T2 items only (`p_said`) and from T1 items only
(`p_did`). If both exist and `|p_said − p_did| > 0.5`, the cell is **divergent** —
the party's programme and its votes disagree. Mechanical, identical for every
party. (Live example in this release: SPD on Tempolimit — programme +1.0, votes
−1.0.)

### 3.6 The user match S(P) — the only computation between you and the ranking
Your answers are `u ∈ {−1, −0.5, 0, 0.5, 1}` with weight `w ∈ {1, 2}` (skips
omitted). For one party, over the statements you answered where the party has a
position:

```
S(P) = 1 − ( Σ w · |u − p| ) / ( 2 · Σ w )              # match, in [0, 1]
```

The error bar uses each position's uncertainty radius `r = 1 − c`:

```
h     = √( Σ (w·r)² ) / (2 Σ w)     # displayed half-width  → "68 % ± 9"
h_max = ( Σ w·r ) / (2 Σ w)         # conservative bound for tie-grouping
```

This is the whole scoring path: symmetric in parties (no party-specific term), no
learned parameters, no ML. A skipped statement or a `null` position is removed from
**both** numerator and denominator — never defaulted.

### 3.7 Ranking, ties, coverage
Parties sort by `S` descending. Two adjacent parties **share a rank** when their
scores differ by less than the larger of their `h_max` — ties render as ties, never
a hidden tiebreak. Below **10** answered statements the ranked list is suppressed
(low-coverage mode). Parties with no overlap are listed separately as "keine
belegbare Überschneidung". All ballot-admitted parties always appear.

### 3.8 Coalitions (descriptive, never predictive)
From the dawum seat projection: enumerate **minimal winning** coalitions (sum ≥
majority, no member droppable), minus any pair in `exclusions.json` (e.g. the CDU
Brandmauer). For each, `S(C)` is the seat-weighted mean of member `S(P)`, cohesion
`Ω(C)` is `1 − mean pairwise position spread`, and "Uneinig bei" lists the
highest-variance statements. No probability language anywhere — only "rechnerisch
möglich" vs. "durch Beschluss ausgeschlossen" (design rule D6).

---

## 4. Why you can trust a number (the guarantees)

- **D1** score concrete statements, not categories · **D2** client-side only ·
  **D3** deterministic scoring · **D4** releases, not a live DB · **D5** descriptive,
  never predictive · **D6** no ML in the score path.
- **Bias suite (§9)**, green on every release: determinism, party-symmetry, a mirror
  test (flip all answers → mirrored ranking), and no-imputation.
- **`reproduce.py`** is a *second, independent* implementation of the formulas; it
  regenerates `positions.json` from `evidence.json` and must match byte-for-byte. A
  bug in one implementation is caught by the other.
- **In-browser signature check** ties the served numbers to the held key.
- Everything above runs in CI on every release; a red check blocks the release.

---

## 5. A number, traced (real, this release)

You answer "stimme stark zu" on *Tempolimit*. GRÜNE scores 100 % on that axis.
Tap it:

```
T1 ▮ Abstimmung · 2026-07-09 · "Einführung eines allgemeinen Tempolimits 130 km/h"
   BÜ90/GR: 79 Ja, 0 Nein, 0 Enthaltungen, 6 nicht abgegeben.
   → direction = (79−0)/(79+0) = +1.0 ;  item_weight = 79/79 = 1.0
   Quelle → bundestag.de/resource/blob/…xlsx   #4b6f440f6e…
Berechnung: p = +1.00 aus 1 Beleg — belegbasiert, nicht Selbstauskunft.
```

The hash is the SHA-256 of the exact XLSX the tally came from. `reproduce.py`
turns that same evidence back into `p = +1.00`.

---

## 6. The road to "Z" (public, board-approved launch)

Done and live today: full ingestion; 80 evidence items over 15 statements (5
parties fully coded, machine-verified); v1.2 aggregation; held-key signing;
in-browser verification; mobile + desktop UI (Ergebnis, Themen, Sagen-vs-Tun,
Koalitionen, Methodik); nightly CI; deployed on Cloudflare.

Remaining, in rough order:

1. **Finish coverage** — AfD/BSW/Volt programme quotes (throttled during this
   build; complete on the next coding run) and more T1 vote links. Then re-run;
   no code change.
2. **Human dual-coding** — replace the assisted coding with two independent human
   coders via `portal/`; publish inter-coder agreement.
3. **Board-approved statement set** — swap the provisional 15 for the Beirat's set
   (target 32); the rejected-statements list is published too.
4. **Source-verify exclusions** — confirm each `exclusions.json` entry against a
   primary source (the CDU Brandmauer is provisionally coded now).
5. **Licensing** — clear Wahl-O-Mat (bpb) theses and Manifesto Project (WZB) terms
   before anything non-preview; dawum ODbL attribution is already emitted.
6. **Trust infrastructure** — independent release monitor on separate infra
   (re-fetch, re-verify, re-reproduce, alert on drift, design §7); 2-of-3 signing
   ceremony; port `scoring.py` → `engine/` TypeScript with a golden parity test.
7. **Launch** — custom domain, drop `meta.preview`, hand to the NGO.

Until step 3–6 land, the "technische Vorschau" banner stays up and the seal keeps
its promise: every number on screen can be traced to a document and recomputed
from the signed bundle.
