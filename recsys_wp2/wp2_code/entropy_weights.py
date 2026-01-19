from __future__ import annotations

from typing import Dict, List
import math


def compute_entropy_weights(
    features_by_center: Dict[str, Dict[str, float]],
    criteria: List[str],
    eps: float = 1e-12,
) -> Dict[str, float]:
    """Compute entropy weights (EWM) for normalized criteria.

    features_by_center:
        { centre_iri: { criterion_id: value_in_[0,1] } }

    criteria:
        List of criterion IDs (e.g., ["MP1", "MP2", ...]).

    Returns:
        { criterion_id: weight } normalized to sum to 1.
    """
    if not features_by_center or not criteria:
        return {}

    centres = list(features_by_center.keys())
    n = len(centres)
    if n == 0:
        return {}

    # 1) Probability matrix p_ij = x_ij / sum_i x_ij
    p: Dict[str, List[float]] = {}
    for crit in criteria:
        col = [features_by_center[c].get(crit, 0.0) for c in centres]
        col_sum = sum(col)
        if col_sum <= eps:
            p[crit] = [1.0 / n] * n
        else:
            p[crit] = [x / col_sum for x in col]

    # 2) Entropy per criterion
    k = 1.0 / math.log(n)
    entropy: Dict[str, float] = {}
    for crit in criteria:
        vals = p[crit]
        e = 0.0
        for pij in vals:
            if pij > eps:
                e -= pij * math.log(pij)
        e *= k
        entropy[crit] = max(0.0, min(1.0, e))

    # 3) Diversification degree d_j = 1 - e_j
    d: Dict[str, float] = {crit: 1.0 - entropy[crit] for crit in criteria}
    d_sum = sum(d.values())

    # 4) Normalize weights
    if d_sum <= eps:
        m = len(criteria)
        return {crit: 1.0 / m for crit in criteria}

    return {crit: d[crit] / d_sum for crit in criteria}
