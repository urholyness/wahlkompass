import math
import yaml
from datetime import date
from typing import Dict, Any, List, Optional, Tuple


class AggregationEngine:
    """
    Reference Aggregation Engine for Wahlkompass (v1.2).

    Computes party stance positions (p), confidence, said/did values, and the
    divergence flag from evidence items using tier weights, recency decay, and
    the per-item participation weight.

    v1.2 change vs v1.1: the item's participation weight is now folded into the
    effective evidence weight w_e = tau * rho * item_weight (numerator,
    denominator, and the confidence variance). Previously item_weight was only
    used to exclude an item when exactly 0, so a partial weight (e.g. a 0.5
    participation share on a split vote) silently counted as a full 1.0.
    """

    def __init__(self, config_path: str):
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

        self.lambda_decay = float(self.config["constants"]["lambda"])
        self.w0 = float(self.config["constants"]["W_0"])

        self.tier_weights = {
            1: float(self.config["tiers"]["T1"]["weight"]),
            2: float(self.config["tiers"]["T2"]["weight"]),
            3: float(self.config["tiers"]["T3"]["weight"]),
            4: float(self.config["tiers"]["T4"]["weight"]),
        }

    def compute_recency_decay(self, evidence_date: date, target_date: date) -> float:
        """Exponential recency decay: rho = e^(-lambda * age_years)."""
        delta_days = (target_date - evidence_date).days
        age_years = max(0.0, delta_days / 365.25)
        return math.exp(-self.lambda_decay * age_years)

    def _effective_weight(self, item: Dict[str, Any], target_date: date) -> float:
        """w_e = tau * rho * item_weight (v1.2)."""
        tau = self.tier_weights[item["tier"]]
        rho = self.compute_recency_decay(item["evidence_date"], target_date)
        iw = item.get("item_weight", 1.0)
        return tau * rho * iw

    def calculate_cell_position(
        self,
        evidence_items: List[Dict[str, Any]],
        target_date: date,
    ) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float], bool]:
        """
        Compute (p, confidence, p_said, p_did, divergent) for a single
        party-statement cell.

        Each evidence item must contain:
          - 'tier'          : int (1..4)
          - 'direction'     : float (-1.0..1.0)
          - 'item_weight'   : float (participation share; 0.0 excludes the item)
          - 'evidence_date' : datetime.date
        """
        # Legislature-boundary rule: drop T1 evidence older than 8 years (two
        # legislative periods). A reaffirmation would exist as a fresh T2 item.
        active_items = []
        for item in evidence_items:
            age_years = (target_date - item["evidence_date"]).days / 365.25
            if item["tier"] == 1 and age_years > 8.0:
                continue
            active_items.append(item)

        if not active_items:
            return None, None, None, None, False

        def aggregate_subset(subset: List[Dict[str, Any]]) -> Tuple[Optional[float], float]:
            numerator = 0.0
            denominator = 0.0
            for item in subset:
                w = self._effective_weight(item, target_date)
                if w == 0.0:            # zero participation / excluded item
                    continue
                numerator += w * item["direction"]
                denominator += w
            if denominator == 0:
                return None, 0.0
            return numerator / denominator, denominator

        # Admission rule: >=1 item of tier T1 or T2, or >=3 concordant T3 items.
        # Items whose effective weight is 0 (e.g. unified abstentions) do not
        # count toward admission — an excluded item is not evidence of a position.
        weighted = [i for i in active_items if self._effective_weight(i, target_date) > 0.0]
        t1_t2_items = [i for i in weighted if i["tier"] in (1, 2)]
        t3_items = [i for i in weighted if i["tier"] == 3]

        is_admissible = False
        if len(t1_t2_items) >= 1:
            is_admissible = True
        elif len(t3_items) >= 3:
            directions = [i["direction"] for i in t3_items]
            all_positive = all(d > 0 for d in directions)
            all_negative = all(d < 0 for d in directions)
            all_neutral = all(d == 0 for d in directions)
            if all_positive or all_negative or all_neutral:
                is_admissible = True

        if not is_admissible:
            return None, None, None, None, False

        # Stance position p.
        p, total_weight = aggregate_subset(active_items)
        if p is None:
            return None, None, None, None, False

        # Confidence c = v * a.
        volume = 1.0 - math.exp(-total_weight / self.w0)

        weighted_variance_sum = 0.0
        for item in active_items:
            w = self._effective_weight(item, target_date)
            if w == 0.0:
                continue
            weighted_variance_sum += w * ((item["direction"] - p) ** 2)

        weighted_std = math.sqrt(weighted_variance_sum / total_weight) if total_weight > 0 else 0.0
        agreement = 1.0 - min(1.0, weighted_std)   # sigma_max = 1 on [-1, 1]
        confidence = volume * agreement

        # Said (T2-only) vs Did (T1-only) divergence.
        t2_subset = [i for i in active_items if i["tier"] == 2]
        t1_subset = [i for i in active_items if i["tier"] == 1]
        p_said, _ = aggregate_subset(t2_subset)
        p_did, _ = aggregate_subset(t1_subset)

        divergent = (
            p_said is not None
            and p_did is not None
            and abs(p_said - p_did) > 0.5
        )

        return (
            round(p, 4),
            round(confidence, 4),
            round(p_said, 4) if p_said is not None else None,
            round(p_did, 4) if p_did is not None else None,
            divergent,
        )
