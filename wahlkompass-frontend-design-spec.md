# Wahlkompass — Frontend Design Specification (for Claude Design)

**Consumes:** Architecture v1.0 + v1.1 · **Feeds:** Build plan WP-2.2
**Product in one line:** A static, client-side tool where a citizen answers ~32 concrete policy statements and sees, for every party, how closely it matches — with every number one tap away from the documents that produced it.

**The design's single job:** make *verifiability feel tangible*. Every competing product asks for trust; this one hands over receipts. The interface should make "where does this number come from?" the most natural gesture on every screen.

---

## 1. Design direction (proposal — counter-proposals welcome within §2 hard rules)

**Aesthetic thesis: the precision instrument, not the news page.** The subject's world is measurement against documents: roll-call records, signed releases, calibration between what parties say and do. Draw from that — scale marks, detents, stamps, ledger rows — not from newsroom or campaign vernacular. Explicitly avoid: broadsheet hairline-grid pastiche, warm-cream editorial serif looks, and anything that echoes campaign material or state-authority insignia (no eagle-adjacent motifs).

**Token proposal:**

- `--paper #FAFAF7` — background; matte, not warm cream
- `--ink #1A1C1E` — primary text
- `--graphite #5A5F63` — secondary text, scale marks
- `--petrol #0F6B6E` — the product accent. Chosen because it is claimed by no German party (black/red/green/yellow/blue/orange/purple are all taken); used for interaction, focus, links, the verification seal
- `--signal #B4541E` — sparing: divergence flags and destructive/warn states only
- `--seal-green #2E7D4F` — signature-verified state only

**Type roles:** Display — **Archivo** (semi-expanded weights for screen titles; has an official-forms-modernized character). Body — **Public Sans** (designed for civic-government clarity; the provenance is on-message). Data/utility — a mono (**JetBrains Mono** or similar) for evidence extracts, release tags, hashes, vote records. Mono is doing real semantic work here: *monospace = quoted primary material*, everywhere, consistently.

**Signature element — the Beleg-Zug (evidence drawer).** Any position value, match score, or divergence flag is a pressable object; pressing slides open its receipts in place — tier-badged evidence cards with the mono extract, date, and source link. One interaction pattern, used identically across every screen, learned once. Spend the motion budget here (a single well-crafted open/close, 200ms, reduced-motion honored) and almost nowhere else.

**Secondary motif — the Prüfsiegel.** The in-browser signature verification renders as a small seal mark (petrol ring, seal-green check) beside the release tag in the footer and on every share image. It is a real state, not decoration: unverified bundle → seal absent, warning shown.

## 2. Neutrality hard rules (non-negotiable; treat as acceptance criteria)

1. **Party colors appear only inside identical-sized party chips** (name + chip). Never as backgrounds, section themes, chart fills larger than the chip, or gradients. No party's color may render at larger area than another's on any screen state.
2. **Pre-result ordering is alphabetical by short name.** Post-result ordering is by score only. No "featured," no default ordering that encodes size or incumbency.
3. **Ties render as ties**: shared rank number, visually grouped bracket. The design must have a real tie treatment, not a hidden tiebreak.
4. **"Keine belegbare Position" is a designed state**, visually neutral (graphite, em-dash glyph + label) — never rendered as 0%, never as negative space that reads as a defect of the party.
5. **Divergence flags use identical treatment for every party** (`--signal` dot + label). No intensity scaling.
6. **All ballot-admitted parties appear on the results screen** — the layout must survive 20+ parties gracefully (Volt rule), not be designed around 6 and degraded for the rest.
7. Confidence intervals are always rendered when a score is rendered. A bare percentage is a spec violation.

## 3. Data contracts (what the UI binds to)

The frontend loads one signed bundle per release. Shapes below are canonical; sample values are **illustrative — verify against release 1.0**.

```jsonc
// meta.json
{
  "release": "2026.11.1",
  "legislature": "deu-bundestag-21",
  "methodology_version": "1.0",
  "signature_verified": true,          // set by the client after minisign check
  "statement_count": 32,
  "frozen_at": null                     // ISO date when pre-election freeze active
}

// statements.json (array)
{
  "id": 14,
  "policy_slug": "schuldenbremse-de",
  "topic": "wirtschaft",
  "text_de": "Die Schuldenbremse im Grundgesetz soll reformiert werden, um höhere staatliche Investitionen zu ermöglichen.",
  "text_easy_de": "Der Staat soll mehr Schulden machen dürfen, um mehr zu investieren.",
  "context_de": "1–2 Sätze neutraler Hintergrund.",   // shown behind an info affordance
  "admission_ref": "ev-2201"
}

// parties.json (array)
{
  "id": 3, "short_name": "SPD", "name": "Sozialdemokratische Partei Deutschlands",
  "color_hex": "#E3000F", "ballot_status": "parliamentary",
  "seats": 120                                          // illustrative
}

// positions.json — keyed "partyId:statementId"
{
  "3:14": {
    "p": 0.78, "confidence": 0.91,
    "p_said": 0.90, "p_did": 0.70, "divergent": false,
    "evidence_ids": ["ev-1043","ev-1044","ev-2201"],
    "salience": "hoch"                                  // display-only, never scored
  },
  "9:14": { "p": null }                                  // keine belegbare Position
}

// evidence.json — keyed by id
{
  "ev-1043": {
    "tier": 1, "direction": 1.0, "date": "2026-03-12",
    "kind": "namentliche_abstimmung",
    "title_de": "Abstimmung über Drucksache 21/1234",
    "extract": "Fraktion stimmte mit Ja (118 Ja, 0 Nein, 2 Enthaltungen).",
    "source_url": "https://…", "sha256": "ab3f…"
  }
}

// exclusions.json (array)          — coalition simulator only
{ "pair": ["CDU","AfD"], "evidence_id": "ev-3001", "reaffirmed": "2025-01-…" }

// seats.json                       — simulator only, dawum-derived
{ "as_of": "2027-04-30", "projection": { "CDU/CSU": 208, "SPD": 120, "…": 0 },
  "total": 630, "majority": 316 }
```

**Client-computed (never in the bundle):** user answers `u[i] ∈ {-1,-0.5,0,0.5,1}` + weights `w[i] ∈ {1,2}` + skips — localStorage only; `S(P)`, `CI`, half-width `h(P)` per §2 of the architecture; coalition `S(C)`, `Ω(C)`.

## 4. Information architecture

```
Start ─► Fragebogen (32 steps) ─► Ergebnis ─┬─► Partei-Detail ─► Beleg-Zug (drawer, everywhere)
                                            ├─► Sagen-vs-Tun (matrix view)
                                            ├─► Koalitionen (simulator)
                                            └─► Themen (policy explorer, longitudinal)
Global footer: release tag + Prüfsiegel · Methodik · Impressum/Datenschutz
```

Deep-linkable: every statement, party, cell, and coalition has a URL (hash-routed; static hosting). Nothing requires completing the questionnaire except Ergebnis itself — the evidence layer is a public reference work on its own.

## 5. Screens

### 5.1 Start
Job: state the contract, start the flow. Content: one-line product promise; the privacy claim as a first-class element — "Ihre Antworten verlassen dieses Gerät nicht. Es gibt kein Konto, keinen Server, kein Tracking." with a "prüfen" link to the Methodik section explaining how to verify that in the source; release tag + Prüfsiegel; primary action "Los geht's"; secondary "Nur Daten ansehen" → Themen. States: bundle loading (skeleton), signature-failed (blocking warning, seal absent, link to repo), freeze banner when `frozen_at` set.

### 5.2 Fragebogen
One statement per step. Elements: progress ("14 / 32", thin bar), topic eyebrow, statement text (largest type on screen), Leichte-Sprache toggle (persists), context info affordance, **Stimmungs-Skala** — the 5-point selector rendered as a horizontal scale with detents and labels (lehne stark ab … stimme stark zu), a visually distinct **Überspringen** action (equal ease, zero guilt — skipping must not feel like failure; it feeds honest coverage), and **doppelt gewichten** toggle per answered statement. Back navigation always available; answers editable from a review list at step 32. Autosave to localStorage with a subtle "auf diesem Gerät gespeichert" note. State: `< 10` answered at finish → proceed allowed, but Ergebnis enters low-coverage mode.

### 5.3 Ergebnis
Job: ranked match with honest uncertainty. Each party row: rank (ties bracket-grouped) · party chip · `S(P)` as a bar with **CI whiskers** and "71 % ± 6" label · coverage note ("28 von 30 Ihrer Fragen belegbar") · expand → per-statement breakdown where every cell is a Beleg-Zug trigger. All ballot-admitted parties listed; sparse parties show honest coverage, not padding. Low-coverage mode (<10 answers): unranked cards, prominent explanation, CTA back to Fragebogen. Actions: "Vergleich teilen" → share image (see §7), "Koalitionen ansehen", "Sagen vs. Tun".

### 5.4 Partei-Detail
All 32 statements × this party: user answer vs party position on the same scale glyph, confidence rendered (e.g., position marker opacity/ring maps to `confidence` — design a legible encoding, test it), divergence dot where flagged, salience tag ("für diese Partei: zentral/randständig" — visibly separate from the score), every row a Beleg-Zug.

### 5.5 Beleg-Zug (the signature component)
Slides open beneath its trigger. Contents: evidence cards sorted tier-then-date; each card = tier badge (T1 "Abstimmung", T2 "Programm", T3 "Kodierung", T4 "Äußerung" — shape+label, not color-only), date, mono extract, source link, hash tooltip. Footer of drawer: "Berechnung: p = 0.78 aus 3 Belegen · Formel ansehen" → Methodik anchor. If cell is divergent: drawer is pre-split into "Gesagt" / "Getan" columns.

### 5.6 Sagen-vs-Tun
Matrix or per-party list of divergent cells: paired-dot ("dumbbell") glyph per cell — `p_said` and `p_did` on one scale, connected. Identical glyph treatment for all parties (§2.5). Every dumbbell is a Beleg-Zug trigger. Header copy states the mechanical rule verbatim ("Flagge, wenn |gesagt − getan| > 0,5, für alle Parteien gleich").

### 5.7 Koalitionen
Feasible coalitions (from seats.json + exclusions.json) as cards: member chips, seat sum vs 316, user's `S(C)` with CI, cohesion `Ω(C)` as a labeled meter, and "Uneinig bei:" top-3 highest-variance statements (each a Beleg-Zug). Excluded combinations available behind "Warum nicht …?" — showing the exclusion evidence, which is itself a receipt. **D6 guardrail for design:** no probability language anywhere on this screen; feasibility is binary ("rechnerisch möglich / durch Beschluss ausgeschlossen"), copy reviewed against the word list *wahrscheinlich, dürfte, erwartet, Chance*.

### 5.8 Themen (policy explorer)
Per `policy` object: its statements across releases/elections, party position timelines (backward-looking step-lines, release-tagged points only — no extrapolation, the line ends at the newest release). Entry point for the "reference work" use case and for researchers.

### 5.9 Methodik
Rendered formulas (§2–3 of the architecture), constants table, release changelog, reproduce instructions, board members + disclosures, rejected-statements list link. Design this as a real destination, not a legal dump — it is the trust engine's showroom.

## 6. Component inventory (build order for Claude Design)

1. `StimmungsSkala` — 5-detent scale, keyboard operable (arrow keys), skip affordance
2. `MatchBar` — score bar + CI whiskers + label; tie-group wrapper
3. `BelegZug` — drawer + `EvidenceCard` (tier badge, mono extract) — *build early; everything composes it*
4. `PositionGlyph` — party position on scale w/ confidence encoding; divergence dot variant
5. `DumbbellGlyph` — said/did pair
6. `PartyChip` — equal-size, color-safe (contrast-checked label, never color-only)
7. `KoalitionsKarte` — chips, seat meter vs 316, Ω meter, disagreement list
8. `PrüfsiegelFooter` — release tag, seal state, methodology link
9. `KeineBelegbarePosition` — the designed absence (§2.4)
10. `ShareCard` renderer (§7)

## 7. Share images

Any cell/result renders to a share image with **baked-in provenance**: release tag, Prüfsiegel mark, cell URL, and the mechanical-rule one-liner for divergence cells. Assume screenshots will circulate hostile and cropped (§13.5 of the architecture); the watermark strip sits *inside* the informative area, not in a croppable margin.

## 8. Accessibility, language, quality floor

WCAG 2.1 AA minimum: full keyboard path through Fragebogen; visible focus (petrol); scale usable by screen reader as a radio group with value text; tier badges and divergence flags never color-only; contrast-checked party chips (auto light/dark label). Reduced-motion: Beleg-Zug becomes instant expand. Language: German, **Sie**-Form, sentence case, active voice; Leichte Sprache variant for every statement (human-reviewed per build plan); no LLM-generated visible copy without labeled human sign-off (A4 fence). Empty and error states direct action ("Bündel konnte nicht geprüft werden — Daten stammen möglicherweise nicht vom Original. Neu laden / Quelle prüfen."), never apologize vaguely. Mobile-first: the Fragebogen is a one-thumb flow; results table collapses to cards below 640px and must still honor §2.6 at 20+ parties.

## 9. Out of scope for design v1

Accounts, notifications, comparisons between two saved answer sets, embeds/widgets, English localization (structure for it — all copy through a strings file — but don't design it), and anything that violates D6.
