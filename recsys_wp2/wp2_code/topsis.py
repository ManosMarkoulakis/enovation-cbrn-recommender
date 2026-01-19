from __future__ import annotations
from typing import Dict, List, Tuple
import math


def _build_matrix(
    feature_dict: Dict[str, Dict[str, float]],
    criteria: List[str],
) -> Tuple[List[str], List[str], List[List[float]]]:
    """Convert nested dict centre->criterion->value into a dense matrix.

    Returns:
        centres: list of centre ids (rows)
        crits:   list of criteria actually used (columns)
        X:       matrix X[i][j] with raw values
    """
    centres = sorted(feature_dict.keys())
    # Keep criteria that appear at least once (non-all-zero) to avoid
    # degenerate columns.
    used_criteria: List[str] = []
    for c in criteria:
        col_non_zero = any(
            feature_dict[centre].get(c, 0.0) != 0.0 for centre in centres
        )
        if col_non_zero:
            used_criteria.append(c)

    X: List[List[float]] = []
    for centre in centres:
        row = [float(feature_dict[centre].get(c, 0.0)) for c in used_criteria]
        X.append(row)

    return centres, used_criteria, X


def _vector_normalise_column(col: List[float]) -> List[float]:
    """L2 normalisation for a single column.

    If the column is all zeros, returns zeros.
    """
    norm_sq = sum(v * v for v in col)
    if norm_sq <= 0.0:
        return [0.0 for _ in col]
    norm = math.sqrt(norm_sq)
    return [v / norm for v in col]


def topsis_scores(
    feature_dict: Dict[str, Dict[str, float]],
    weights: Dict[str, float],
    criteria: List[str],
) -> Dict[str, float]:
    """Compute TOPSIS closeness scores for a set of alternatives.

    All criteria are treated as benefit criteria (higher is better).

    Args:
        feature_dict: mapping centre_iri -> {criterion_name: value}.
        weights:      mapping criterion_name -> subjective weight
                       (non-negative). Only criteria in this mapping
                       and in `criteria` are considered.
        criteria:     ordered list of criterion names to consider.

    Returns:
        Dict centre_iri -> TOPSIS score in [0, 1].
    """
    # 1. Build matrix and filter criteria that have any non-zero signal.
    centres, crits_used, X = _build_matrix(feature_dict, criteria)

    if not centres or not crits_used:
        return {c: 0.0 for c in centres}

    n_rows = len(centres)
    n_cols = len(crits_used)

    # 2. Normalise columns (vector normalisation).
    # Transpose, normalise, transpose back.
    cols: List[List[float]] = [[X[i][j] for i in range(n_rows)] for j in range(n_cols)]
    cols_norm = [_vector_normalise_column(col) for col in cols]
    R: List[List[float]] = [[cols_norm[j][i] for j in range(n_cols)] for i in range(n_rows)]

    # 3. Build weight vector aligned to crits_used and normalise weights.
    w_raw = [max(0.0, float(weights.get(c, 0.0))) for c in crits_used]
    w_sum = sum(w_raw)
    if w_sum <= 0.0:
        # Fallback: equal weights
        w = [1.0 / n_cols for _ in crits_used]
    else:
        w = [v / w_sum for v in w_raw]

    # 4. Weighted normalised matrix V.
    V: List[List[float]] = []
    for i in range(n_rows):
        row = [R[i][j] * w[j] for j in range(n_cols)]
        V.append(row)

    # 5. Ideal best and worst.
    ideal_best: List[float] = [max(V[i][j] for i in range(n_rows)) for j in range(n_cols)]
    ideal_worst: List[float] = [min(V[i][j] for i in range(n_rows)) for j in range(n_cols)]

    # 6. Distances to ideals.
    scores: Dict[str, float] = {}
    for i, centre in enumerate(centres):
        d_pos = math.sqrt(
            sum((V[i][j] - ideal_best[j]) ** 2 for j in range(n_cols))
        )
        d_neg = math.sqrt(
            sum((V[i][j] - ideal_worst[j]) ** 2 for j in range(n_cols))
        )
        if d_pos + d_neg == 0.0:
            s = 0.0
        else:
            s = d_neg / (d_pos + d_neg)
        scores[centre] = s

    return scores

