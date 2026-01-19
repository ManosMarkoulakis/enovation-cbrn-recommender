from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Tuple

from recsys_wp1.wp1_code.features_wp1 import compute_wp1_features
from recsys_wp1.wp1_code.structural_ranker_wp1 import rank_centers_wp1
from recsys_wp1.wp1_code.sparql_client import DEFAULT_ENDPOINT


def _load_jsonl(path: str) -> List[dict]:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _overlap_at_k(a: List[str], b: List[str], k: int) -> float:
    if k <= 0:
        return 0.0
    return len(set(a[:k]).intersection(b[:k])) / float(k)


def main() -> None:
    root_dir = Path(__file__).resolve().parents[2]
    default_dataset = root_dir / "recsys_wp0" / "eval_data" / "reference_labels.jsonl"
    default_splits = root_dir / "recsys_wp0" / "eval_data" / "reference_splits.json"

    ap = argparse.ArgumentParser(description="WP1 eval: compare meta-path scores to WP0 reference scores.")
    ap.add_argument("--dataset", default=str(default_dataset))
    ap.add_argument("--splits", default=str(default_splits))
    ap.add_argument("--split", default="all", choices=["train", "val", "test", "all"])
    ap.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    ap.add_argument("--limit", type=int, default=0, help="Limit number of queries (0 = no limit)")
    args = ap.parse_args()

    rows = _load_jsonl(args.dataset)
    splits = json.load(open(args.splits, "r", encoding="utf-8"))
    qids = None if args.split == "all" else set(splits.get(args.split, []))

    abs_diffs: List[float] = []
    sq_diffs: List[float] = []
    top1_match = 0
    top3_overlap = 0.0
    top5_overlap = 0.0
    n = 0

    for r in rows:
        if qids is not None and r.get("qid") not in qids:
            continue
        if args.limit and n >= args.limit:
            break

        tech = r["query"]["technology"]
        scen = r["query"]["scenario"]
        cands = r["candidates"]

        features_by_center: Dict[str, Dict[str, float]] = {}
        for cid in cands:
            feats, _ = compute_wp1_features(
                center_iri=cid,
                tech_iri=tech,
                scen_iri=scen,
                endpoint=args.endpoint,
                include_evidence=False,
            )
            features_by_center[cid] = feats

        wp1_ranking = rank_centers_wp1(features_by_center)
        wp1_scores = {cid: float(score) for cid, score in wp1_ranking}

        ref_scores = (r.get("reference_meta") or {}).get("scores") or {}

        # Score diffs (only for shared candidates).
        for cid in cands:
            if cid not in ref_scores:
                continue
            d = abs(float(wp1_scores.get(cid, 0.0)) - float(ref_scores.get(cid, 0.0)))
            abs_diffs.append(d)
            sq_diffs.append(d * d)

        # Ranking overlap.
        ref_ranked = [cid for cid, _ in sorted(ref_scores.items(), key=lambda kv: (-float(kv[1]), kv[0]))]
        wp1_ranked = [cid for cid, _ in wp1_ranking]
        if ref_ranked and wp1_ranked and ref_ranked[0] == wp1_ranked[0]:
            top1_match += 1
        top3_overlap += _overlap_at_k(wp1_ranked, ref_ranked, 3)
        top5_overlap += _overlap_at_k(wp1_ranked, ref_ranked, 5)

        n += 1

    if n == 0:
        print(json.dumps({"error": "no records evaluated", "split": args.split}, indent=2))
        return

    mean_abs = sum(abs_diffs) / len(abs_diffs) if abs_diffs else 0.0
    mean_sq = sum(sq_diffs) / len(sq_diffs) if sq_diffs else 0.0

    out = {
        "split": args.split,
        "n_queries": n,
        "score_diff": {
            "mean_abs": mean_abs,
            "rmse": mean_sq ** 0.5,
            "max_abs": max(abs_diffs) if abs_diffs else 0.0,
        },
        "ranking_overlap": {
            "top1_match_rate": top1_match / float(n),
            "top3_overlap": top3_overlap / float(n),
            "top5_overlap": top5_overlap / float(n),
        },
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
