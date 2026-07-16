import json
import sys
import os
import math
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

# Fallback methodology constants for deu-bundestag-21 (methodology v1.0).
# Used ONLY when the release bundle does not pin its own methodology; a warning
# is printed when the fallback is taken, because a real release MUST pin these
# (§7: methodology_version pins tau, lambda, W_0, formulas).
FALLBACK_LAMBDA = 0.17328679513
FALLBACK_W0 = 1.3028834457
FALLBACK_TIERS = {1: 1.0, 2: 0.8, 3: 0.6, 4: 0.3}
FALLBACK_TARGET_DATE = "2026-11-01"


class ReproduceVerifier:
    """
    Independent re-implementation of the aggregation formulas (v1.2).

    This is deliberately a SEPARATE implementation from
    pipeline/src/aggregation.py: a bug present in only one of the two is caught
    when their outputs disagree. It also doubles as the off-browser
    journalist/researcher tool (§7).
    """

    def __init__(self, lambda_decay: float, w0: float, tier_weights: Dict[int, float]):
        self.lambda_decay = lambda_decay
        self.w0 = w0
        self.tier_weights = tier_weights

    def compute_decay(self, evidence_date_str: str, target_date_str: str) -> float:
        ev_date = datetime.strptime(evidence_date_str, "%Y-%m-%d").date()
        target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
        delta_days = (target_date - ev_date).days
        age_years = max(0.0, delta_days / 365.25)
        return math.exp(-self.lambda_decay * age_years)

    def _effective_weight(self, item: Dict[str, Any], target_date_str: str) -> float:
        tau = self.tier_weights[item["tier"]]
        rho = self.compute_decay(item["date"], target_date_str)
        iw = item.get("item_weight", 1.0)
        return tau * rho * iw

    def calculate_cell(self, evidence_items: List[Dict[str, Any]], target_date_str: str) -> Dict[str, Any]:
        target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()

        active_items = []
        for item in evidence_items:
            ev_date = datetime.strptime(item["date"], "%Y-%m-%d").date()
            age_years = (target_date - ev_date).days / 365.25
            if item["tier"] == 1 and age_years > 8.0:
                continue
            active_items.append(item)

        empty = {"p": None, "confidence": None, "p_said": None, "p_did": None, "divergent": False}
        if not active_items:
            return empty

        def aggregate_subset(subset: List[Dict[str, Any]]) -> Tuple[Optional[float], float]:
            num = 0.0
            den = 0.0
            for item in subset:
                w = self._effective_weight(item, target_date_str)
                if w == 0.0:
                    continue
                num += w * item["direction"]
                den += w
            return (num / den, den) if den > 0 else (None, 0.0)

        weighted = [i for i in active_items if self._effective_weight(i, target_date_str) > 0.0]
        t1_t2_items = [i for i in weighted if i["tier"] in (1, 2)]
        t3_items = [i for i in weighted if i["tier"] == 3]

        is_admissible = False
        if len(t1_t2_items) >= 1:
            is_admissible = True
        elif len(t3_items) >= 3:
            directions = [i["direction"] for i in t3_items]
            if all(d > 0 for d in directions) or all(d < 0 for d in directions) or all(d == 0 for d in directions):
                is_admissible = True

        if not is_admissible:
            return empty

        p, total_weight = aggregate_subset(active_items)
        if p is None:
            return empty

        volume = 1.0 - math.exp(-total_weight / self.w0)

        weighted_var_sum = 0.0
        for item in active_items:
            w = self._effective_weight(item, target_date_str)
            if w == 0.0:
                continue
            weighted_var_sum += w * ((item["direction"] - p) ** 2)

        weighted_std = math.sqrt(weighted_var_sum / total_weight) if total_weight > 0 else 0.0
        agreement = 1.0 - min(1.0, weighted_std)
        confidence = volume * agreement

        t2_sub = [i for i in active_items if i["tier"] == 2]
        t1_sub = [i for i in active_items if i["tier"] == 1]
        p_said, _ = aggregate_subset(t2_sub)
        p_did, _ = aggregate_subset(t1_sub)

        divergent = (p_said is not None and p_did is not None and abs(p_said - p_did) > 0.5)

        return {
            "p": round(p, 4),
            "confidence": round(confidence, 4),
            "p_said": round(p_said, 4) if p_said is not None else None,
            "p_did": round(p_did, 4) if p_did is not None else None,
            "divergent": divergent,
        }


def _load_methodology(release_dir: str, meta: Dict[str, Any]) -> Tuple[float, float, Dict[int, float], str, bool]:
    """
    Resolve methodology constants + target date, preferring what the release
    pins over the built-in fallback. Precedence:
      1. methodology.json in the release dir  (lambda, W_0, tiers, target_date)
      2. a "methodology" object embedded in meta.json
      3. built-in deu-bundestag-21 fallback   (warns)
    Returns (lambda, W0, tier_weights, target_date_str, pinned).
    """
    src: Dict[str, Any] = {}
    methodology_path = os.path.join(release_dir, "methodology.json")
    if os.path.exists(methodology_path):
        with open(methodology_path, "r", encoding="utf-8") as f:
            src = json.load(f)
    elif isinstance(meta.get("methodology"), dict):
        src = meta["methodology"]

    pinned = bool(src)

    lam = float(src.get("lambda", FALLBACK_LAMBDA))
    w0 = float(src.get("W_0", src.get("w0", FALLBACK_W0)))

    tiers_raw = src.get("tier_weights") or src.get("tiers")
    if isinstance(tiers_raw, dict) and tiers_raw:
        tiers = {int(k.lstrip("T")) if isinstance(k, str) else int(k): float(v) for k, v in tiers_raw.items()}
    else:
        tiers = dict(FALLBACK_TIERS)

    target_date = (
        src.get("target_date")
        or meta.get("as_of")
        or meta.get("target_date")
        or FALLBACK_TARGET_DATE
    )
    return lam, w0, tiers, target_date, pinned


def verify_release(release_dir: str) -> bool:
    print(f"Starting verification of release in directory: {release_dir}")

    required = ["meta.json", "statements.json", "parties.json", "positions.json", "evidence.json"]
    paths = {name: os.path.join(release_dir, name) for name in required}
    for name, path in paths.items():
        if not os.path.exists(path):
            print(f"Verification FAILED: Missing required file {path}")
            return False

    with open(paths["meta.json"], "r", encoding="utf-8") as f:
        meta = json.load(f)
    with open(paths["positions.json"], "r", encoding="utf-8") as f:
        positions_expected = json.load(f)
    with open(paths["evidence.json"], "r", encoding="utf-8") as f:
        evidence_db = json.load(f)

    lambda_decay, w0, tier_weights, target_date_str, pinned = _load_methodology(release_dir, meta)
    if not pinned:
        print(
            "  WARNING: release does not pin its methodology (no methodology.json / meta.methodology). "
            f"Falling back to built-in deu-bundestag-21 constants and target_date={target_date_str}. "
            "A production release MUST pin tau/lambda/W_0/target_date."
        )
    print(f"  methodology: lambda={lambda_decay}, W_0={w0}, tiers={tier_weights}, target_date={target_date_str}")

    verifier = ReproduceVerifier(lambda_decay, w0, tier_weights)

    all_cells_match = True
    mismatches: List[str] = []

    def same(a: Optional[float], b: Optional[float]) -> bool:
        # Byte-identical determinism: both sides are stored/recomputed rounded to
        # 4 dp, so exact equality is the correct check (no tolerance dial).
        if a is None or b is None:
            return a is None and b is None
        return round(a, 4) == round(b, 4)

    for cell_key, cell_meta in positions_expected.items():
        ev_ids = cell_meta.get("evidence_ids", [])
        cell_evidence = []
        for ev_id in ev_ids:
            item = evidence_db.get(ev_id)
            if item is not None:
                cell_evidence.append({
                    "tier": item["tier"],
                    "direction": item["direction"],
                    "date": item["date"],
                    "item_weight": item.get("item_weight", 1.0),
                })

        computed = verifier.calculate_cell(cell_evidence, target_date_str)

        checks = {
            "p": (cell_meta.get("p"), computed["p"]),
            "confidence": (cell_meta.get("confidence"), computed["confidence"]),
            "p_said": (cell_meta.get("p_said"), computed["p_said"]),
            "p_did": (cell_meta.get("p_did"), computed["p_did"]),
        }
        for field, (exp, got) in checks.items():
            if not same(exp, got):
                all_cells_match = False
                mismatches.append(f"Cell {cell_key}: {field} expected {exp}, computed {got}")

        if bool(cell_meta.get("divergent", False)) != bool(computed["divergent"]):
            all_cells_match = False
            mismatches.append(
                f"Cell {cell_key}: divergent expected {cell_meta.get('divergent', False)}, "
                f"computed {computed['divergent']}"
            )

    if all_cells_match:
        print("Verification SUCCESS: Computed positions.json matches the release exactly.")
        return True

    print("Verification FAILED! Mismatches found:")
    for msg in mismatches[:10]:
        print(f" - {msg}")
    if len(mismatches) > 10:
        print(f" ... and {len(mismatches) - 10} more.")
    return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python reproduce.py <release_directory_path>")
        sys.exit(1)
    success = verify_release(sys.argv[1])
    sys.exit(0 if success else 1)
