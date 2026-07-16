# Wahlkompass — Architecture v1.1 Amendments

**Applies to:** `wahlkompass-de-architecture-v1.md` (v1.0) · **Type:** Delta release
**Rationale:** Folds in the accepted items from external review; rejects prediction-engine features with a new design principle. v1.0 remains canonical; this document amends it the same way a data release amends positions — explicitly, with reasons.

---

## A1. New design principle D6 — Descriptive, never predictive

Added to §0 after D5:

> **D6 — The platform describes; it never forecasts.** No feature may output a probability, likelihood, expectation, or timeline about future political behavior — coalition formation odds, pledge-delivery probability, legislative timelines, ministry allocation. Every prediction requires judgment calls with no mechanical anchor, and every wrong forecast becomes evidence of partisanship. Descriptive backward-looking measurement from T1/T2 documents (e.g. "this pledge entered the Koalitionsvertrag and became law on date X") is permitted; anything with a future tense is not. Feature proposals are tested against D6 before effort estimation.

This principle rejects, by name and permanently: a Delivery Index, coalition-formation probability, "who gains ministries" simulation, and free-form scenario forecasting ("how likely is affordable housing legislation in two years?"). The descriptive slice of that demand ships as the **Koalitionsvertrag-Tracker** (A5).

## A2. Country-agnostic core, per-country evidence configuration

§5 schema changes:

```sql
CREATE TABLE country (
    code          CHAR(3) PRIMARY KEY,          -- ISO 3166-1 alpha-3: DEU, KEN, NLD ...
    name          TEXT NOT NULL
);

CREATE TABLE legislature (
    id            SERIAL PRIMARY KEY,
    country_code  CHAR(3) NOT NULL REFERENCES country(code),
    name          TEXT NOT NULL,                -- Bundestag, Landtag NRW, National Assembly ...
    level         TEXT NOT NULL,                -- national | regional
    seats         INT NOT NULL,
    majority      INT NOT NULL
);

-- party.level and election gain legislature_id FK; statement.election_id unchanged.
```

The evidence tier table (§3.2) becomes **per-legislature configuration**, not global constants: which sources exist at which tier, their access method, and their coverage caveats are a config file (`evidence_config/{legislature}.yaml`) reviewed by the methodology board per jurisdiction. Honest framing for the roadmap: **the methodology ports; the source mapping is rebuilt per country.** Germany's T1 relies on namentliche Abstimmungen, which cover only a fraction of Bundestag votes; other parliaments differ more. "Country = X plugs in" is true for the schema and false for the editorial work — the second country (a Landtag) is deliberately chosen to be the cheapest proof of portability.

## A3. Policy objects above statements

§5 addition. Statements remain the scoring unit (D1 unchanged). A persistent `policy` entity sits above them for navigation, reuse, and longitudinal display:

```sql
CREATE TABLE policy (
    id            SERIAL PRIMARY KEY,
    slug          TEXT NOT NULL UNIQUE,          -- e.g. 'nuclear-energy-de'
    name_de       TEXT NOT NULL,
    aliases       TEXT[],                        -- search & entity-linking
    topic         TEXT NOT NULL
);
ALTER TABLE statement ADD COLUMN policy_id INT REFERENCES policy(id);
```

Enables: cross-election position tracking ("Partei X zur Kernenergie, 2021 → 2026"), evidence reuse when a statement is re-worded between elections, and the policy-explorer surface in the frontend. Scoring never touches `policy` — a policy page is an aggregation view over its statements' released positions. Longitudinal display is backward-looking only (D6-compliant).

## A4. Pipeline-AI scope, expanded and fenced

§6 amendment. Permitted LLM/ML uses inside the editorial pipeline, all human-gated: candidate-passage retrieval, entity extraction and linking, duplicate detection across documents, coder-facing bill summaries, translation drafts for future jurisdictions, semantic search inside the review portal. Two hard fences added:

1. **No model output ever becomes an evidence item, direction value, or position without dual human sign-off** (unchanged from v1.0, restated as the fence).
2. **No LLM-generated user-facing text** without named human editorial sign-off and on-page labeling. Violating this collapses the §8 AI-Act posture and is treated as a release-blocking defect, not a style issue.

## A5. Phase 6 — Koalitionsvertrag-Tracker (descriptive pledge accounting)

New roadmap phase, firewalled from the match score. Scope: for the sitting government, each Koalitionsvertrag pledge is linked (dual-coded, same evidence rules) to its outcome documents — bill introduced, passed, amended, struck by BVerfG, abandoned — with dates. Output is a ledger, not an index: no fulfillment percentage headline (a single number smuggles the judgment calls back in), just per-pledge status with receipts and per-party attribution *only where a T1/T2 document assigns responsibility* (e.g. ministry ownership in the agreement itself). Methodology to be aligned with existing academic pledge-fulfillment research before build; board sign-off required on the status vocabulary.

## A6. Graph capability — position restated, no change

External review pushed Neo4j. v1.0 §5 already provides the answer this amendment confirms: relational core now, graph as a possible *analytical sidecar* if committee/lobbying/amendment network research materializes in Phase 5+, never in the serving path. The v1.0 schema is third-normal-form over explicit entities and ports to a property graph mechanically; no schema change is needed today to keep that door open. Closed as designed.

---

**Changelog:** +D6 · +country/legislature entities · +evidence_config per legislature · +policy entity · pipeline-AI list expanded with two fences · +Phase 6 Koalitionsvertrag-Tracker · Neo4j request closed without change.
