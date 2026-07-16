# Wahlkompass Monorepo

Germany-first, country-agnostic policy similarity matching platform designed for adversarial transparency and zero user-data collection.

## Project Structure

* **`pipeline/`**: Python data ingestion, normalization, and reference aggregation engine.
* **`portal/`**: FastAPI admin and human coding portal for paired review and statement curation.
* **`engine/`**: TypeScript similarity matching scoring engine (compiled for client-side execution).
* **`frontend/`**: Astro & React static frontend hosted on edge CDN.
* **`data-releases/`**: Public repository for versioned, cryptographically signed data packages.

## Core Design Principles

1. **Concrete Statements**: Issue positions are derived from votes and policies, not arbitrary categories.
2. **Double Evidence**: Shows party self-declarations side-by-side with legislative votes (Sagen vs. Tun).
3. **Pure Client-Side**: No user data ever leaves the browser. Matches are computed locally.
4. **Deterministic Path**: Absolutely no ML/LLM models in the scoring or text-generation path.
5. **Release-Driven**: No live database modifications in production. Changes go through signed Git releases.
6. **Descriptive, Not Predictive**: No probability projections, coalition forecasting, or cabinet simulations.
