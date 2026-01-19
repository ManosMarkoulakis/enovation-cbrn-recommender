from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Dict, List

from recsys_wp0.wp0_code.eval_metrics import (
    precision_at_k,
    recall_at_k,
    hitrate_at_k,
    ndcg_at_k,
    mrr,
)

from .ranker_wp2 import rank_centers_wp2


def _load_dataset(path: str) -> List[Dict]:
    """Load JSONL reference rows."""
    rows: List[Dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    return rows


def _labels_bin_dict(labels_bin: Dict[str, int]) -> Dict[str, int]:
    return {k: int(v) for k, v in labels_bin.items()}


def _labels_grade_dict(labels_1_5: Dict[str, int]) -> Dict[str, int]:
    return {k: int(v) for k, v in labels_1_5.items()}


def compute_all_metrics(y_true_all: List[Dict[str, int]], y_score_all: List[Dict[str, float]]) -> Dict[str, float]:
    """Aggregate ranking metrics for a batch of queries."""
    ks = [1, 2, 3, 5]
    out: Dict[str, float] = {}

    for k in ks:
        out[f"P@{k}"] = precision_at_k(y_true_all, y_score_all, k)
        out[f"R@{k}"] = recall_at_k(y_true_all, y_score_all, k)
        out[f"HR@{k}"] = hitrate_at_k(y_true_all, y_score_all, k)
        out[f"nDCG@{k}"] = ndcg_at_k(y_true_all, y_score_all, k)

    out["MRR"] = mrr(y_true_all, y_score_all)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="WP2 MCDM/TOPSIS evaluation runner (Q1)")
    root_dir = Path(__file__).resolve().parents[2]
    default_dataset = root_dir / "recsys_wp0" / "eval_data" / "reference_labels.jsonl"
    default_splits = root_dir / "recsys_wp0" / "eval_data" / "reference_splits.json"

    parser.add_argument("--dataset", default=str(default_dataset), help="JSONL reference dataset")
    parser.add_argument("--splits", default=str(default_splits), help="JSON with train/val/test qids")
    parser.add_argument("--split", default="all", choices=["train", "val", "test", "all"], help="which split to evaluate")
    parser.add_argument("--limit", type=int, default=None, help="optional limit on number of queries")
    args = parser.parse_args()

    rows = _load_dataset(args.dataset)
    splits = json.load(open(args.splits, "r", encoding="utf-8"))
    wanted_ids = None if args.split == "all" else set(splits[args.split])

    eval_rows = rows if wanted_ids is None else [r for r in rows if r["qid"] in wanted_ids]
    if args.limit is not None:
        eval_rows = eval_rows[: args.limit]

    y_true_all: List[Dict[str, int]] = []
    y_score_all: List[Dict[str, float]] = []

    for r in eval_rows:
        tech = r["query"]["technology"]
        scen = r["query"]["scenario"]
        centres = r["candidates"]

        ranking, _features = rank_centers_wp2(tech_iri=tech, scen_iri=scen, centres=centres)

        # Ground truth
        rel = _labels_bin_dict(r["labels_bin"])

        # Scores as dict
        scores = {cid: float(score) for cid, score in ranking}

        y_true_all.append(rel)
        y_score_all.append(scores)

    metrics = compute_all_metrics(y_true_all, y_score_all)

    out = {
        "split": args.split,
        "n_queries": len(eval_rows),
        "metrics": metrics,
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
