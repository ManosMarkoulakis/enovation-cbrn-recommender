from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Dict, List, Tuple

from App.enovation_recommender import rank_centers_by_uri


def _load_jsonl(path: str) -> List[dict]:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _labels_from_ranking(ranking: List[Tuple[str, float]]) -> Tuple[Dict[str, int], Dict[str, int], Dict[str, int]]:
    labels_1_5 = {cid: max(1, 5 - i) for i, (cid, _) in enumerate(ranking)}
    labels_thresh_0_5 = dict(labels_1_5)
    labels_bin = {cid: int(labels_1_5.get(cid, 0) >= 4) for cid, _ in ranking}
    return labels_1_5, labels_thresh_0_5, labels_bin


def main() -> None:
    root_dir = Path(__file__).resolve().parents[2]
    default_in = root_dir / "recsys_wp0" / "eval_data" / "reference_labels.jsonl"
    default_out = root_dir / "recsys_wp0" / "eval_data" / "reference_labels.jsonl"

    ap = argparse.ArgumentParser(description="Create reference labels using recommender scoring.")
    ap.add_argument("--in", dest="in_path", default=str(default_in), help="Input dataset jsonl")
    ap.add_argument("--out", dest="out_path", default=str(default_out), help="Output jsonl with reference labels")
    ap.add_argument("--endpoint", default=None, help="Fuseki endpoint override")
    ap.add_argument("--limit", type=int, default=0, help="Limit number of queries (0 = no limit)")
    args = ap.parse_args()

    if args.endpoint:
        os.environ["FUSEKI_ENDPOINT"] = args.endpoint

    rows = _load_jsonl(args.in_path)
    out_path = Path(args.out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    processed = 0
    with out_path.open("w", encoding="utf-8") as f:
        for r in rows:
            processed += 1
            if args.limit and processed > args.limit:
                break

            tech = r["query"]["technology"]
            scen = r["query"]["scenario"]
            cands = r["candidates"]

            ranking = rank_centers_by_uri(tech_uri=tech, scen_uri=scen, candidates=cands)
            labels_1_5, labels_thresh_0_5, labels_bin = _labels_from_ranking(ranking)
            score_map = {cid: float(score) for cid, score in ranking}

            out_row = dict(r)
            out_row["labels_1_5"] = labels_1_5
            out_row["labels_thresh_0_5"] = labels_thresh_0_5
            out_row["labels_bin"] = labels_bin
            out_row["reference_meta"] = {"scores": score_map}

            f.write(json.dumps(out_row) + "\n")

    print(f"OK. wrote {processed} rows -> {out_path}")


if __name__ == "__main__":
    main()
