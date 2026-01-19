from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

from recsys_wp0.wp0_code.eval_metrics import compute_all_metrics
from recsys_wp3.wp3_code.embed_ranker import load_entity_embeddings
from recsys_wp3.wp3_code.ranker_wp3 import rank_centers_wp3_embedding


def _load_jsonl(path: str) -> List[dict]:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description="WP3 eval: Embedding-only similarity vs WP0 labels.")
    root_dir = Path(__file__).resolve().parents[2]
    default_dataset = root_dir / "recsys_wp0" / "eval_data" / "reference_labels.jsonl"
    default_splits = root_dir / "recsys_wp0" / "eval_data" / "reference_splits.json"

    ap.add_argument("--dataset", default=str(default_dataset), help="Reference dataset jsonl")
    ap.add_argument("--splits", default=str(default_splits), help="Splits json")
    ap.add_argument("--split", default="all", choices=["train", "val", "test", "all"])
    ap.add_argument(
        "--emb",
        default="recsys_wp3/recsys_wp3_artifacts/entity_embeddings.tsv",
        help="Entity embeddings TSV (from train_kge.py)",
    )
    ap.add_argument("--endpoint", default=None, help="Unused (kept for CLI compatibility)")
    ap.add_argument("--limit", type=int, default=None, help="Limit number of queries")
    args = ap.parse_args()

    rows = _load_jsonl(args.dataset)
    splits = json.load(open(args.splits, "r", encoding="utf-8"))
    keep = None if args.split == "all" else set(splits[args.split])
    if keep is not None:
        rows = [r for r in rows if r.get("qid") in keep]
    if args.limit is not None:
        rows = rows[: args.limit]

    emb = load_entity_embeddings(args.emb)

    y_true_all: List[Dict[str, int]] = []
    y_score_all: List[Dict[str, float]] = []

    for r in rows:
        tech = r["query"]["technology"]
        scen = r["query"]["scenario"]
        centres = r["candidates"]

        ranking, evidence = rank_centers_wp3_embedding(
            tech_iri=tech,
            scen_iri=scen,
            centres=centres,
            emb_index=emb,
        )

        scores = {c: s for c, s in ranking}

        rel = r.get("labels_bin") or {}
        y_true_all.append(rel)
        y_score_all.append(scores)

    metrics = compute_all_metrics(y_true_all, y_score_all)
    out = {"split": args.split, "n_queries": len(rows), "metrics": metrics}
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
