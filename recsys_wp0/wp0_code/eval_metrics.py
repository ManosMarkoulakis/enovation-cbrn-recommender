"""Evaluation metrics for the WP0/WP1 offline experiments.

This module intentionally supports *two* calling styles:

1) Per-query style (used by WP0 runner):
   precision_at_k(ranked_list, relevance_dict, k)

2) Batch style (used by WP1 runner):
   precision_at_k(list_of_relevance_dicts, list_of_score_dicts, k)

That way the older WP0 scripts and the newer WP1 scripts can share the same
metric code without fragile refactors.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Sequence, Tuple, Union
import math


Relevance = Dict[str, float]
Scores = Dict[str, float]


def _rank_from_scores(scores: Scores) -> List[str]:
    """Return items sorted by score (desc). Deterministic tie-break by key."""
    return [k for k, _ in sorted(scores.items(), key=lambda kv: (-float(kv[1]), kv[0]))]


def _as_int_rel(rel: Relevance) -> Dict[str, int]:
    """Ensure relevance values are 0/1 ints for P/R/HR/MRR."""
    return {k: (1 if float(v) > 0 else 0) for k, v in rel.items()}


def precision_at_k(
    a: Union[List[str], Sequence[Relevance]],
    b: Union[Relevance, Sequence[Scores]],
    k: int,
) -> float:
    """Precision@k (per-query or mean over queries)."""
    if k <= 0:
        return 0.0

    # Per-query: ranked list + relevance dict
    if isinstance(b, dict):
        ranked: List[str] = list(a)  # type: ignore[arg-type]
        rel = _as_int_rel(b)
        top = ranked[:k]
        hits = sum(rel.get(x, 0) for x in top)
        return hits / float(k)

    # Batch: list[rel_dict] + list[score_dict]
    y_true_all: Sequence[Relevance] = a  # type: ignore[assignment]
    y_score_all: Sequence[Scores] = b
    if not y_true_all:
        return 0.0
    vals = [precision_at_k(_rank_from_scores(s), r, k) for r, s in zip(y_true_all, y_score_all)]
    return sum(vals) / len(vals)


def recall_at_k(
    a: Union[List[str], Sequence[Relevance]],
    b: Union[Relevance, Sequence[Scores]],
    k: int,
) -> float:
    """Recall@k (per-query or mean over queries)."""
    if k <= 0:
        return 0.0

    if isinstance(b, dict):
        ranked: List[str] = list(a)  # type: ignore[arg-type]
        rel = _as_int_rel(b)
        total_rel = sum(rel.values())
        if total_rel == 0:
            return 0.0
        top = ranked[:k]
        hits = sum(rel.get(x, 0) for x in top)
        return hits / float(total_rel)

    y_true_all: Sequence[Relevance] = a  # type: ignore[assignment]
    y_score_all: Sequence[Scores] = b
    if not y_true_all:
        return 0.0
    vals = [recall_at_k(_rank_from_scores(s), r, k) for r, s in zip(y_true_all, y_score_all)]
    return sum(vals) / len(vals)


def hitrate_at_k(
    a: Union[List[str], Sequence[Relevance]],
    b: Union[Relevance, Sequence[Scores]],
    k: int,
) -> float:
    """HitRate@k (per-query or mean over queries)."""
    if k <= 0:
        return 0.0

    if isinstance(b, dict):
        ranked: List[str] = list(a)  # type: ignore[arg-type]
        rel = _as_int_rel(b)
        top = ranked[:k]
        return 1.0 if any(rel.get(x, 0) for x in top) else 0.0

    y_true_all: Sequence[Relevance] = a  # type: ignore[assignment]
    y_score_all: Sequence[Scores] = b
    if not y_true_all:
        return 0.0
    vals = [hitrate_at_k(_rank_from_scores(s), r, k) for r, s in zip(y_true_all, y_score_all)]
    return sum(vals) / len(vals)


def _dcg_at_k(ranked: List[str], gains: Relevance, k: int) -> float:
    dcg = 0.0
    for i, item in enumerate(ranked[:k]):
        gain = float(gains.get(item, 0.0))
        denom = math.log2(i + 2)
        dcg += (2.0**gain - 1.0) / denom
    return dcg


def ndcg_at_k(
    a: Union[List[str], Sequence[Relevance]],
    b: Union[Relevance, Sequence[Scores]],
    k: int,
) -> float:
    """nDCG@k (per-query or mean over queries)."""
    if k <= 0:
        return 0.0

    if isinstance(b, dict):
        ranked: List[str] = list(a)  # type: ignore[arg-type]
        gains: Relevance = b
        dcg = _dcg_at_k(ranked, gains, k)
        ideal_ranked = [x for x, _ in sorted(gains.items(), key=lambda kv: (-float(kv[1]), kv[0]))]
        idcg = _dcg_at_k(ideal_ranked, gains, k)
        return 0.0 if idcg == 0.0 else dcg / idcg

    y_true_all: Sequence[Relevance] = a  # type: ignore[assignment]
    y_score_all: Sequence[Scores] = b
    if not y_true_all:
        return 0.0
    vals = [ndcg_at_k(_rank_from_scores(s), g, k) for g, s in zip(y_true_all, y_score_all)]
    return sum(vals) / len(vals)


def mrr(
    a: Union[List[str], Sequence[Relevance]],
    b: Union[Relevance, Sequence[Scores]],
) -> float:
    """MRR (per-query or mean over queries)."""
    if isinstance(b, dict):
        ranked: List[str] = list(a)  # type: ignore[arg-type]
        rel = _as_int_rel(b)
        for i, item in enumerate(ranked):
            if rel.get(item, 0):
                return 1.0 / float(i + 1)
        return 0.0

    y_true_all: Sequence[Relevance] = a  # type: ignore[assignment]
    y_score_all: Sequence[Scores] = b
    if not y_true_all:
        return 0.0
    vals = [mrr(_rank_from_scores(s), r) for r, s in zip(y_true_all, y_score_all)]
    return sum(vals) / len(vals)


def compute_all_metrics(
    y_true_all: Sequence[Relevance],
    y_score_all: Sequence[Scores],
    ks: Tuple[int, ...] = (1, 2, 3, 5),
    include_ndcg: bool = True,
) -> Dict[str, float]:
    """Convenience helper for WP1-style evaluation."""
    out: Dict[str, float] = {}
    for k in ks:
        out[f"P@{k}"] = precision_at_k(y_true_all, y_score_all, k)
        out[f"R@{k}"] = recall_at_k(y_true_all, y_score_all, k)
        out[f"HR@{k}"] = hitrate_at_k(y_true_all, y_score_all, k)
        if include_ndcg:
            out[f"nDCG@{k}"] = ndcg_at_k(y_true_all, y_score_all, k)
    out["MRR"] = mrr(y_true_all, y_score_all)
    return out
