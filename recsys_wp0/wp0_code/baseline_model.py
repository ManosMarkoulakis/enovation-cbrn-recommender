from __future__ import annotations

from typing import Dict, List, Tuple

# Reuse the same scoring logic as the UI recommender.
try:
    from App.enovation_recommender import _compute_cluster_scores
except ImportError:  # pragma: no cover
    import os
    import sys

    _THIS_DIR = os.path.dirname(os.path.abspath(__file__))
    _PROJECT_ROOT = os.path.abspath(os.path.join(_THIS_DIR, "..", ".."))
    if _PROJECT_ROOT not in sys.path:
        sys.path.insert(0, _PROJECT_ROOT)
    from App.enovation_recommender import _compute_cluster_scores

def baseline_rank_from_signals(center_to_signals: Dict[str, Dict[str, int]]) -> List[Tuple[str, float]]:
    """Score centres using min-max normalized signals and the shared scorer."""
    keys = list(next(iter(center_to_signals.values())).keys())
    mins = {k: min(v[k] for v in center_to_signals.values()) for k in keys}
    maxs = {k: max(v[k] for v in center_to_signals.values()) for k in keys}

    scored = []
    for center, sig in center_to_signals.items():
        scores = {}
        for k in keys:
            mn, mx = mins[k], maxs[k]
            norm = 0.0 if mx==mn else (sig[k]-mn)/(mx-mn)
            scores[k + "_norm"] = norm
        _compute_cluster_scores(scores)
        scored.append((center, float(scores.get("final_score_0_1", 0.0))))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored
