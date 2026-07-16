# Wahlkompass — Build Plan (Germany First)

**Baseline:** Architecture v1.0 + v1.1 amendments · **Start:** August 2026
**Strategic timing:** No federal election until ~2029 — an advantage. The platform matures against the sitting 21st Bundestag with zero election pressure, then takes its first live-election test at a Landtagswahl (target: **NRW, expected May 2027 — verify official date early in Phase 0**). By the next Bundestagswahl the methodology has survived two public cycles.

**Operating model:** Optimized for your setup — a two-person core (you + Claudia-equivalent technical capacity) plus dispatched Claude Code/Cowork agents for parallelizable engineering, plus contracted humans where the methodology demands humans. Work packages below are tagged **[AGENT]** (dispatchable, verifiable output), **[HUMAN]** (judgment/legitimacy work that must not be delegated to a model, per D4/A4), or **[MIXED]**.

---

## Phase 0 — Charter & Foundations (Weeks 1–4, August 2026)

The long-lead items start here because everything legitimacy-related has human latency.

- **W1 [HUMAN]** Verify NRW 2027 election date; confirm 21st Bundestag composition and Fraktion structure from Bundeswahlleiterin data (the plan's seat numbers are illustrative until this lands). Register DIP API key; test-pull abgeordnetenwatch v2, dawum API, Bundestag roll-call XML — one script per source proving access and format. [AGENT can write the probes; HUMAN registers keys.]
- **W1–4 [HUMAN]** Methodology board recruitment — the longest pole. Target 5: two political scientists (Manifesto-Project-adjacent — WZB is in Berlin, use proximity), one statistician, one public-law academic, one journalist/ombuds figure. Written disclosure rules from day one.
- **W2 [HUMAN]** Legal consult (one-off): entity form (gGmbH vs e.V.), GDPR posture review, AI-Act memo, bpb/Wahl-O-Mat and Manifesto Project **redistribution licensing** for verbatim extracts (§6 flag — this can reshape the evidence explorer, so it's Phase 0, not Phase 2).
- **W2–3 [AGENT]** Repo scaffolding: monorepo (`pipeline/`, `portal/`, `engine/`, `frontend/`, `releases/`), CI skeleton with the §9 test suite as failing stubs, Docker Compose for Postgres + portal, `evidence_config/deu-bundestag.yaml` v0.
- **W3–4 [MIXED]** Methodology v1 document drafted [AGENT drafts from spec §2–3], board-reviewed [HUMAN], published. Constants frozen: τ tiers, λ, W₀, admission rule.

**Exit:** methodology v1 published under board names; all six data sources probed; licensing answers in hand; entity decision made.
**Kill-switch check:** if no credible board can be recruited by W6, pause — an unboarded launch converts every future dispute into "founder's opinion."

## Phase 1 — Evidence Foundation (Weeks 5–14, Sept–Oct 2026)

Two parallel tracks. Track A is code; Track B is editorial. Track B is the schedule risk.

**Track A — Pipeline & portal [mostly AGENT]**
- WP-1.1 Roll-call ingester: Bundestag XML → raw_document (SHA-256) → per-Fraktion vote records. Deterministic; golden-file tested against 5 hand-checked Abstimmungen.
- WP-1.2 DIP ingester: bills/Anträge metadata, nightly cron, idempotent upserts.
- WP-1.3 abgeordnetenwatch + Manifesto Project ingesters (T3).
- WP-1.4 Review portal: statement CRUD, bill↔statement linking UI, dual-coding workflow (coder A/B blind, divergence >0.5 escalation queue), sign-off with actor logging, append-only audit trigger.
- WP-1.5 Aggregation engine (Python, ~150 lines): §3.3–3.4 formulas, property-tested (symmetry, monotonicity, no-imputation) + `reproduce.py`.
- WP-1.6 Release builder: positions snapshot → JSON bundle → diff → minisign signature → Git tag.

**Track B — Editorial [HUMAN]**
- WP-1.7 Statement drafting: ~60 candidates against the admission test → board-approved set of **32** covering the topic rubric. Publish the rejected list with reasons (§3.6). This is the single highest-judgment task in the entire build; do not compress it.
- WP-1.8 Bill↔statement linking for the 21st Bundestag's roll-call record to date; dual-coded.
- WP-1.9 T2 coding: Wahlprogramme 2025 + Wahl-O-Mat 2025 answer set for the 32 statements; 2 freelance coders (~10 h/wk each, political-science grad students), paired protocol.

**Exit (Milestone: internal release 0.1):** ≥85% of (parliamentary party × 32 statements) cells admissible; `reproduce.py` regenerates positions.json byte-identically on a clean machine; §9 tests 1–5 green.

## Phase 2 — Public Launch (Weeks 15–20, Nov–Dec 2026)

- WP-2.1 **[AGENT]** Scoring engine in TypeScript per §2 — pure module, ported property tests, cross-checked against Python engine on the golden user set (byte-identical scores or release blocks).
- WP-2.2 **[MIXED]** Frontend build from the design spec (companion document — Claude Design starts now, in parallel with late Phase 1): Fragebogen, Ergebnis, Beleg-Explorer, Methodik. Leichte Sprache statement variants [HUMAN-reviewed].
- WP-2.3 **[AGENT]** Static hosting + signed-bundle verification in browser; release footer pinning.
- WP-2.4 **[HUMAN]** First party right-of-reply cycle (14 days) before release 1.0 — run it even pre-launch; the process is the product.
- WP-2.5 Soft launch: no press, seed to political-science departments and civic-tech community (OKFN/Wikimedia DE orbit) for adversarial feedback.

**Exit (Milestone: public release 1.0):** an external person has reproduced positions.json from evidence.json using only the public repo. That sentence is the launch criterion.

## Phase 3 — Differentiators (Weeks 21–30, Jan–Mar 2027)

- WP-3.1 **[AGENT]** Sagen-vs-Tun computation (T1-only vs T2-only per cell) + divergence-symmetry audit (§9.7) in CI.
- WP-3.2 **[MIXED]** Divergence UI + per-cell share-image watermarking (release tag + URL baked into any rendered cell).
- WP-3.3 **[AGENT]** Coalition simulator: dawum ingestion → seat projection under current electoral law (630/316, Sperrklausel + Grundmandatsklausel per BVerfG 2024) → feasibility filter → Ω. Exclusion matrix compiled **[HUMAN]** with T2 refs.
- WP-3.4 **[HUMAN]** Second right-of-reply cycle — the first release containing divergence flags. Expect the first real fight here; the board earns its existence.

**Exit:** release 2.0 with divergence + simulator survives the objection process with all resolutions published.

## Phase 4 — First Live Election: NRW (Weeks 31–44, Mar–May 2027)

- WP-4.1 **[AGENT]** A2 schema migration (country/legislature); `evidence_config/deu-nrw.yaml` — Landtag NRW sources: Landtag open documentation system, abgeordnetenwatch Land coverage, Land party programmes. Expect thinner T1; the config file, not the code, absorbs this.
- WP-4.2 **[HUMAN]** NRW statement set (~30, Land competencies only — education, policing, Verkehr; no federal-competence statements) + coding sprint with the same freelance pair.
- WP-4.3 **[MIXED]** All-ballot-parties coverage drill (Volt rule): every party admitted by the Landeswahlausschuss gets cells — mostly "keine belegbare Position" plus their T2 fast path; contact each small party with the self-declaration invitation ≥8 weeks pre-election.
- WP-4.4 Load posture check (trivial by design — CDN cache headers audit), press kit, methodology-page German legal imprint (Impressum/TMG duties).

**Exit:** live through election day with zero position changes after the pre-election freeze date (freeze: 10 days out, published in advance).

## Phase 5+ — Maturity (from Jun 2027)

Assist-ML in the portal (A4 scope, throughput-measured); policy-explorer surface over A3 entities; researcher JSON endpoint; second Land; Phase 6 Koalitionsvertrag-Tracker scoped against A5 and academic pledge-fulfillment methodology; Bundestagswahl ~2029 as the graduation event.

---

## Budget (through Phase 4, ~10 months)

| Item | Estimate |
|---|---|
| Infrastructure (per §11) | €30/mo → ~€300 |
| Legal (entity + licensing + AI-Act memo, one-off) | €4–8k |
| Freelance coders (2 × ~10 h/wk × ~30 active weeks × €25/h) | ~€15k |
| Board honoraria (modest, disclosed) | €3–5k |
| Design (if contracted beyond Claude Design output) | €0–5k |
| **Total cash** | **≈ €25–35k** |

Founder/agent engineering time is the unpriced majority. Cash profile fits a micro-raise — and note the friends-and-family "micro-raising" storyline you've had on the back burner maps cleanly onto Phase 0–2 milestones if you want external money for the coder + legal line.

## Top risks, ordered

1. **Statement selection contested** (likelihood: certain). Mitigation is procedural, already designed: rejected-list publication, board sign-off, topic-balance report. Accept that this never fully goes away — §13.1.
2. **Board recruitment stalls.** Mitigation: start W1; WZB/Berlin proximity; fallback is a named academic *advisory* review of methodology v1 with the full board seated before release 1.0 — but not later.
3. **Licensing blocks verbatim extracts** (bpb / Manifesto Project). Mitigation: Phase 0 legal question; fallback design is quotation-length extracts + deep links, which the evidence explorer supports without redesign.
4. **Coding throughput** — 32 statements × ~8 parties × multi-document T2 is the grind. Mitigation: A4 retrieval-assist earliest useful deployment is *inside the portal* in Phase 3 (human-gated); until then, scope discipline (32 statements, not 60).
5. **Divergence-view legal threats from parties.** Mitigation: every flag mechanically derived, rule contains no party name, evidence one tap away; legal memo in Phase 0 covers Meinungsfreiheit/Tatsachenbehauptung boundaries — displayed cells are sourced facts, framed as such.
6. **NRW date or Land-source assumptions wrong.** Mitigation: W1 verification task; Phase 4 has 6 weeks of float before a May election if Phase 3 holds schedule.

## Definition of done, per release (standing checklist)

Signature verifies · reproduce.py byte-identical · §9 suite green · changelog human-written · right-of-reply executed and resolutions published · freeze respected · no NULL position entered any score · no user data path exists (checked by grep + review, every release).
