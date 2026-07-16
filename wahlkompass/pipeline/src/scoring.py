"""
Wahlkompass reference scoring engine (Python) — v1.2 §2.2-2.3.

This is the pure reference implementation of the client-side match computation.
The SHIPPED scorer is a small TypeScript module (engine/); this module is the
byte-for-byte reference it is cross-checked against in CI (§14.3). Keeping a
Python reference lets the bias/integrity suite (§9) run in the same test harness
as the pipeline.

Guarantees this module is designed to make verifiable by reading it:
  * symmetric in parties  — no party-specific term anywhere
  * scale-fixed           — no learned parameters
  * total                 — S(P) is the ONLY computation between input and rank
  * no imputation         — a skipped statement or a null position is removed
                            from BOTH numerator and denominator; never defaulted
                            to 0 or "supportive".
"""
import math
from typing import Dict, List, Optional, Any, Tuple

# v1.2 §2.1 — below this many answered statements, results render as unranked
# cards with a low-coverage warning (never a ranked list).
MIN_ANSWERS_FOR_RANKING = 10


def match_score(
    user_answers: Dict[Any, Dict[str, float]],
    party_positions: Dict[Any, Dict[str, Optional[float]]],
) -> Dict[str, Optional[float]]:
    """
    Normalized weighted-L1 match of one user against one party (v1.2 §2.2-2.3).

      user_answers[stmt]    = {"u": stance in [-1,1], "w": weight > 0}   (skips omitted)
      party_positions[stmt] = {"p": pos in [-1,1] or None, "confidence": c in [0,1]}

    Overlap = answered statements where the party has a non-null position. A
    null position ("keine belegbare Position") is excluded exactly like a skip.

    Returns {"S", "h", "h_max", "n_answered"} where
      S      = 1 - (Σ w|u-p|) / (2 Σ w)                      in [0,1]
      h      = sqrt(Σ (w r)^2) / (2 Σ w)     display half-width (RSS, z=1)
      h_max  = (Σ w r) / (2 Σ w)             conservative tie-grouping bound
      r      = 1 - confidence                position-uncertainty radius
    S/h/h_max are None when the overlap is empty.
    """
    num = 0.0
    denom = 0.0
    rss = 0.0     # Σ (w r)^2  — independent-error display interval
    lin = 0.0     # Σ w r      — fully-correlated conservative bound
    n = 0

    for stmt, ans in user_answers.items():
        pos = party_positions.get(stmt)
        if pos is None:
            continue
        p = pos.get("p")
        if p is None:                 # keine belegbare Position — never imputed
            continue
        u = ans["u"]
        w = ans["w"]
        c = pos.get("confidence")
        c = 0.0 if c is None else c
        r = 1.0 - c

        num += w * abs(u - p)
        denom += w
        rss += (w * r) ** 2
        lin += w * r
        n += 1

    if denom == 0:
        return {"S": None, "h": None, "h_max": None, "n_answered": 0}

    S = 1.0 - num / (2.0 * denom)
    h = math.sqrt(rss) / (2.0 * denom)
    h_max = lin / (2.0 * denom)
    return {"S": S, "h": h, "h_max": h_max, "n_answered": n}


def rank_parties(
    user_answers: Dict[Any, Dict[str, float]],
    positions_by_party: Dict[Any, Dict[Any, Dict[str, Optional[float]]]],
) -> Tuple[List[Dict[str, Any]], bool]:
    """
    Score every party and assign ranks. Ties render as ties: two adjacent
    parties share a rank when their scores differ by less than the larger of
    their conservative bounds (max(h_max) — v1.2 §2.3). Arbitrary tie-breaking
    between parties is a bias vector, so it is not done.

    Returns (ranked, low_coverage):
      ranked        list sorted by S desc; each entry has party_id, S, h, h_max,
                    n_answered, rank (1-indexed, competition ranking with ties).
                    Pre-result ordering elsewhere is alphabetical; here parties
                    with no overlap (S is None) are returned separately-last with
                    rank None.
      low_coverage  True when the user answered < MIN_ANSWERS_FOR_RANKING
                    statements (the UI then suppresses the ranked list).
    """
    scored = []
    for pid, positions in positions_by_party.items():
        r = match_score(user_answers, positions)
        scored.append({"party_id": pid, **r})

    rankable = [s for s in scored if s["S"] is not None]
    no_overlap = [s for s in scored if s["S"] is None]

    # Deterministic order: by score desc, then by party_id to make equal-score
    # ordering stable across runs/platforms (rank ties are still marked below;
    # this only fixes list position, never the displayed rank number).
    rankable.sort(key=lambda s: (-s["S"], str(s["party_id"])))

    rank = 0
    for i, s in enumerate(rankable):
        if i == 0:
            rank = 1
        else:
            prev = rankable[i - 1]
            bound = max(s["h_max"] or 0.0, prev["h_max"] or 0.0)
            if abs(prev["S"] - s["S"]) >= bound:
                rank = i + 1          # distinct rank (competition ranking)
            # else: tie -> keep prev rank
        s["rank"] = rank

    for s in no_overlap:
        s["rank"] = None

    low_coverage = len(user_answers) < MIN_ANSWERS_FOR_RANKING
    return rankable + no_overlap, low_coverage
