import unittest
from datetime import date
from src.aggregation import AggregationEngine


class TestAggregationEngine(unittest.TestCase):

    def setUp(self):
        self.engine = AggregationEngine("evidence_config/deu-bundestag.yaml")
        self.target_date = date(2026, 7, 16)

    def test_recency_decay(self):
        four_years_ago = date(2022, 7, 16)
        decay = self.engine.compute_recency_decay(four_years_ago, self.target_date)
        self.assertAlmostEqual(decay, 0.5, places=4)  # half-life = one legislative period

    def test_admission_rule_no_items(self):
        p, conf, p_said, p_did, div = self.engine.calculate_cell_position([], self.target_date)
        self.assertIsNone(p)
        self.assertIsNone(conf)

    def test_admission_rule_t3_concordant(self):
        items = [
            {"tier": 3, "direction": 1.0, "evidence_date": date(2026, 1, 1), "item_weight": 1.0},
            {"tier": 3, "direction": 0.5, "evidence_date": date(2026, 1, 1), "item_weight": 1.0},
            {"tier": 3, "direction": 1.0, "evidence_date": date(2026, 1, 1), "item_weight": 1.0},
        ]
        p, conf, _, _, _ = self.engine.calculate_cell_position(items, self.target_date)
        self.assertIsNotNone(p)
        self.assertIsNotNone(conf)

        items_conflict = [
            {"tier": 3, "direction": 1.0, "evidence_date": date(2026, 1, 1), "item_weight": 1.0},
            {"tier": 3, "direction": -0.5, "evidence_date": date(2026, 1, 1), "item_weight": 1.0},
            {"tier": 3, "direction": 1.0, "evidence_date": date(2026, 1, 1), "item_weight": 1.0},
        ]
        p, conf, _, _, _ = self.engine.calculate_cell_position(items_conflict, self.target_date)
        self.assertIsNone(p)

    def test_legislature_boundary_rule(self):
        items = [
            {"tier": 1, "direction": 1.0, "evidence_date": date(2017, 7, 16), "item_weight": 1.0}  # 9y
        ]
        p, _, _, _, _ = self.engine.calculate_cell_position(items, self.target_date)
        self.assertIsNone(p)

    def test_abstention_exclusion_by_weight(self):
        # item_weight = 0.0 (unified abstention) excludes the item entirely.
        items = [
            {"tier": 1, "direction": 1.0, "evidence_date": date(2026, 7, 16), "item_weight": 1.0},
            {"tier": 1, "direction": -1.0, "evidence_date": date(2026, 7, 16), "item_weight": 0.0},
        ]
        p, _, _, _, _ = self.engine.calculate_cell_position(items, self.target_date)
        self.assertEqual(p, 1.0)

    def test_partial_item_weight_scales_contribution(self):
        # v1.2: a 0.5 participation share must count HALF as much, not as a full
        # 1.0. Two same-tier same-date T1 items, +1.0 (weight 1.0) and -1.0
        # (weight 0.5): p = (1*1 + (-1)*0.5) / (1 + 0.5) = 0.5/1.5 = 0.3333.
        items = [
            {"tier": 1, "direction": 1.0, "evidence_date": date(2026, 7, 16), "item_weight": 1.0},
            {"tier": 1, "direction": -1.0, "evidence_date": date(2026, 7, 16), "item_weight": 0.5},
        ]
        p, _, _, _, _ = self.engine.calculate_cell_position(items, self.target_date)
        self.assertAlmostEqual(p, 0.3333, places=4)

    def test_divergence_view_sagen_vs_tun(self):
        items = [
            {"tier": 1, "direction": -1.0, "evidence_date": date(2026, 7, 16), "item_weight": 1.0},
            {"tier": 2, "direction": 1.0, "evidence_date": date(2026, 7, 16), "item_weight": 1.0},
        ]
        p, conf, p_said, p_did, divergent = self.engine.calculate_cell_position(items, self.target_date)
        self.assertEqual(p_said, 1.0)
        self.assertEqual(p_did, -1.0)
        self.assertTrue(divergent)
        # T1 weight 1.0, T2 weight 0.8: p = (-1*1.0 + 1*0.8) / (1.0 + 0.8) = -0.1111
        self.assertAlmostEqual(p, -0.1111, places=4)


if __name__ == "__main__":
    unittest.main()
