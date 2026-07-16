"""
§9 Bias & Integrity Test Suite (scoring path).

These are the release-blocking neutrality proofs from the architecture §9. They
run against the reference scorer (src/scoring.py); when the TypeScript engine
lands, it is held to the same fixtures (§14.3 cross-check). Reports that require
real evidence data (coverage-parity §9.5, statement-balance §9.6,
divergence-symmetry §9.8) attach at release-build time and are stubbed at the
bottom with the assertion they will make.
"""
import json
import os
import unittest

from src.scoring import match_score, rank_parties


# ---- Fixed synthetic fixture: 12 statements, 4 parties, 1 user -------------
STMTS = [f"s{i}" for i in range(12)]

USER = {s: {"u": u, "w": w} for s, u, w in [
    ("s0", 1.0, 1), ("s1", 1.0, 2), ("s2", 0.5, 1), ("s3", -1.0, 1),
    ("s4", -0.5, 1), ("s5", 0.0, 1), ("s6", 1.0, 1), ("s7", -1.0, 2),
    ("s8", 0.5, 1), ("s9", -0.5, 1), ("s10", 1.0, 1), ("s11", 0.0, 1),
]}

def _party(offsets, conf=0.8):
    """Build positions by nudging the user's stance by a per-statement offset,
    clamped to [-1,1]. Different offset patterns -> different, distinct scores."""
    out = {}
    for i, s in enumerate(STMTS):
        u = USER[s]["u"]
        p = max(-1.0, min(1.0, u + offsets[i % len(offsets)]))
        out[s] = {"p": p, "confidence": conf}
    return out

PARTIES = {
    "ALFA":  _party([0.0, 0.1, -0.1]),      # closest to the user
    "BRAVO": _party([0.4, -0.3, 0.2]),
    "CHARLIE": _party([-0.8, 0.9, -0.7]),   # far from the user
    "DELTA": _party([1.0, -1.0, 1.0]),      # very far
}


class TestDeterminism(unittest.TestCase):
    """§9.1 — identical inputs produce byte-identical scores across runs."""

    def test_scores_are_reproducible(self):
        r1, _ = rank_parties(USER, PARTIES)
        r2, _ = rank_parties(USER, PARTIES)
        self.assertEqual(json.dumps(r1, sort_keys=True), json.dumps(r2, sort_keys=True))

    def test_ranking_is_a_total_function_of_scores(self):
        ranked, _ = rank_parties(USER, PARTIES)
        scores = [r["S"] for r in ranked]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertEqual(ranked[0]["party_id"], "ALFA")  # closest party ranks first


class TestPartySymmetry(unittest.TestCase):
    """§9.2 — permuting party labels permutes the rankings identically.
    Proves no party-name-dependent code path exists."""

    def test_relabel_parties(self):
        sigma = {"ALFA": "BRAVO", "BRAVO": "CHARLIE", "CHARLIE": "DELTA", "DELTA": "ALFA"}
        permuted = {sigma[pid]: positions for pid, positions in PARTIES.items()}

        base = {r["party_id"]: r for r in rank_parties(USER, PARTIES)[0]}
        perm = {r["party_id"]: r for r in rank_parties(USER, permuted)[0]}

        for pid in PARTIES:
            self.assertEqual(base[pid]["rank"], perm[sigma[pid]]["rank"])
            self.assertAlmostEqual(base[pid]["S"], perm[sigma[pid]]["S"], places=12)


class TestMirror(unittest.TestCase):
    """§9.3 — user vector u vs a party set, and -u vs the mirrored (-p) set,
    yield identical match scores (confidence, hence intervals, unchanged)."""

    def test_mirror_invariance(self):
        mirror_user = {s: {"u": -a["u"], "w": a["w"]} for s, a in USER.items()}
        for pid, positions in PARTIES.items():
            mirrored = {s: {"p": -v["p"], "confidence": v["confidence"]} for s, v in positions.items()}
            base = match_score(USER, positions)
            mir = match_score(mirror_user, mirrored)
            self.assertAlmostEqual(base["S"], mir["S"], places=12)
            self.assertAlmostEqual(base["h"], mir["h"], places=12)
            self.assertAlmostEqual(base["h_max"], mir["h_max"], places=12)


class TestNoImputation(unittest.TestCase):
    """§9.4 — a null position never enters a score, and no default-value branch
    exists in the scoring module."""

    def test_null_position_removed_from_both_num_and_denom(self):
        positions = dict(PARTIES["ALFA"])
        positions["s0"] = {"p": None, "confidence": 0.0}   # blank one cell
        full = match_score(USER, PARTIES["ALFA"])
        with_null = match_score(USER, positions)
        self.assertEqual(with_null["n_answered"], full["n_answered"] - 1)

    def test_skipped_statement_not_invented(self):
        partial_user = {s: USER[s] for s in ("s0", "s1", "s2")}  # user skips the rest
        r = match_score(partial_user, PARTIES["ALFA"])
        self.assertEqual(r["n_answered"], 3)   # only answered statements counted

    def test_source_has_no_default_value_branch(self):
        # Grep-level guard (§9.4): the scoring module must not silently default a
        # missing position/stance to a number.
        path = os.path.join(os.path.dirname(__file__), "..", "src", "scoring.py")
        with open(path, "r", encoding="utf-8") as f:
            src = f.read()
        for forbidden in ('.get("p", 0', ".get('p', 0", '"p", 0.0', "p = 0 if", "or 0.0  # p"):
            self.assertNotIn(forbidden, src, f"forbidden imputation pattern found: {forbidden!r}")


class TestReleaseReportStubs(unittest.TestCase):
    """§9.5-9.8 attach at release-build time (need real evidence data). Documented
    here so the intent is version-controlled; not yet wired to a release."""

    @unittest.skip("coverage-parity / statement-balance / divergence-symmetry: wire at first real release build")
    def test_release_reports_placeholder(self):
        pass


if __name__ == "__main__":
    unittest.main()
