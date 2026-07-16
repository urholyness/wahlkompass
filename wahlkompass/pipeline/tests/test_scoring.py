import unittest
from src.scoring import match_score, rank_parties, MIN_ANSWERS_FOR_RANKING


def ans(**kv):
    """Helper: {stmt: {"u":u,"w":w}} from stmt=(u,w) kwargs like s1=(1.0,1)."""
    return {k: {"u": v[0], "w": v[1]} for k, v in kv.items()}


def pos(**kv):
    """Helper: {stmt: {"p":p,"confidence":c}} from stmt=(p,c) kwargs."""
    return {k: {"p": v[0], "confidence": v[1]} for k, v in kv.items()}


class TestMatchScore(unittest.TestCase):

    def test_perfect_match(self):
        u = ans(s1=(1.0, 1), s2=(-1.0, 1), s3=(0.5, 1))
        p = pos(s1=(1.0, 1.0), s2=(-1.0, 1.0), s3=(0.5, 1.0))
        r = match_score(u, p)
        self.assertAlmostEqual(r["S"], 1.0, places=6)
        self.assertAlmostEqual(r["h"], 0.0, places=6)      # full confidence -> zero interval
        self.assertEqual(r["n_answered"], 3)

    def test_maximal_disagreement(self):
        u = ans(s1=(1.0, 1), s2=(1.0, 1))
        p = pos(s1=(-1.0, 1.0), s2=(-1.0, 1.0))
        r = match_score(u, p)
        self.assertAlmostEqual(r["S"], 0.0, places=6)

    def test_null_position_excluded_not_imputed(self):
        # Statement s2 has no belegbare Position -> dropped from num AND denom.
        # Result must equal scoring only s1 (not treating s2 as 0/agreement).
        u = ans(s1=(1.0, 1), s2=(1.0, 1))
        p_with_null = pos(s1=(1.0, 1.0))
        p_with_null["s2"] = {"p": None, "confidence": 0.0}
        r_null = match_score(u, p_with_null)
        r_only_s1 = match_score(ans(s1=(1.0, 1)), pos(s1=(1.0, 1.0)))
        self.assertEqual(r_null["n_answered"], 1)
        self.assertAlmostEqual(r_null["S"], r_only_s1["S"], places=9)

    def test_double_weight_matters(self):
        # Disagree on the double-weighted statement, agree on the single one.
        u = ans(s1=(1.0, 2), s2=(1.0, 1))
        p = pos(s1=(-1.0, 1.0), s2=(1.0, 1.0))
        r = match_score(u, p)
        # num = 2*2 + 1*0 = 4 ; denom = 3 ; S = 1 - 4/6 = 0.3333
        self.assertAlmostEqual(r["S"], 1 - 4 / 6, places=6)

    def test_lower_confidence_widens_interval(self):
        u = ans(s1=(1.0, 1), s2=(1.0, 1))
        hi = match_score(u, pos(s1=(1.0, 0.9), s2=(1.0, 0.9)))
        lo = match_score(u, pos(s1=(1.0, 0.2), s2=(1.0, 0.2)))
        self.assertLess(hi["h"], lo["h"])
        self.assertLess(hi["h_max"], lo["h_max"])
        self.assertLessEqual(hi["h"], hi["h_max"] + 1e-12)  # RSS bound <= conservative bound

    def test_empty_overlap_returns_none(self):
        r = match_score(ans(s1=(1.0, 1)), pos(s9=(1.0, 1.0)))
        self.assertIsNone(r["S"])
        self.assertEqual(r["n_answered"], 0)


class TestRankParties(unittest.TestCase):

    def test_ties_render_as_ties(self):
        # Two parties with an almost-identical score but wide intervals (low
        # confidence) must share a rank; a clearly-worse third gets its own.
        u = ans(s1=(1.0, 1), s2=(1.0, 1), s3=(1.0, 1))
        parties = {
            "A": pos(s1=(1.0, 0.2), s2=(1.0, 0.2), s3=(0.9, 0.2)),
            "B": pos(s1=(1.0, 0.2), s2=(1.0, 0.2), s3=(1.0, 0.2)),
            "C": pos(s1=(-1.0, 1.0), s2=(-1.0, 1.0), s3=(-1.0, 1.0)),
        }
        ranked, low = rank_parties(u, parties)
        by_id = {r["party_id"]: r for r in ranked}
        self.assertEqual(by_id["A"]["rank"], by_id["B"]["rank"])   # tied
        self.assertNotEqual(by_id["C"]["rank"], by_id["A"]["rank"])
        self.assertTrue(low)  # only 3 answers < 10

    def test_low_coverage_flag(self):
        u = {f"s{i}": {"u": 1.0, "w": 1} for i in range(MIN_ANSWERS_FOR_RANKING)}
        parties = {"A": {f"s{i}": {"p": 1.0, "confidence": 1.0} for i in range(MIN_ANSWERS_FOR_RANKING)}}
        _, low = rank_parties(u, parties)
        self.assertFalse(low)


if __name__ == "__main__":
    unittest.main()
