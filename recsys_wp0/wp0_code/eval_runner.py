from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from recsys_wp0.wp0_code.eval_metrics import precision_at_k, recall_at_k, hitrate_at_k, ndcg_at_k, mrr
from recsys_wp0.wp0_code.baseline_model import baseline_rank_from_signals
from recsys_wp0.wp0_code.kg_loader import load_graph, get_entities
from recsys_wp0.wp0_code.q1_features import compute_q1_signals


def load_dataset(jsonl_path: str) -> List[dict]:
    records: List[dict] = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def load_splits(splits_path: str) -> Dict[str, List[str]]:
    with open(splits_path, "r", encoding="utf-8") as f:
        return json.load(f)


def evaluate_baseline_q1(
    ontology_ttl: str,
    dataset_jsonl: str,
    splits_json: str,
    split: str = "test",
    ks=(1, 2, 3, 5),
) -> dict:
    g = load_graph(ontology_ttl)
    ents = get_entities(g)

    dataset = load_dataset(dataset_jsonl)
    splits = load_splits(splits_json)
    allowed = None if split == "all" else set(splits[split])

    agg = {f"P@{k}": 0.0 for k in ks}
    agg.update({f"R@{k}": 0.0 for k in ks})
    agg.update({f"HR@{k}": 0.0 for k in ks})
    agg.update({f"nDCG@{k}": 0.0 for k in ks})
    agg["MRR"] = 0.0
    n = 0

    for rec in dataset:
        if allowed is not None and rec["qid"] not in allowed:
            continue
        tech = rec["query"]["technology"]
        scen = rec["query"]["scenario"]

        center_to_signals = {c: compute_q1_signals(g, tech, scen, c) for c in ents.centers}
        ranked = [c for c, _ in baseline_rank_from_signals(center_to_signals)]

        rel_bin = rec["labels_bin"]
        gains = rec["labels_1_5"]

        for k in ks:
            agg[f"P@{k}"] += precision_at_k(ranked, rel_bin, k)
            agg[f"R@{k}"] += recall_at_k(ranked, rel_bin, k)
            agg[f"HR@{k}"] += hitrate_at_k(ranked, rel_bin, k)
            agg[f"nDCG@{k}"] += ndcg_at_k(ranked, gains, k)
        agg["MRR"] += mrr(ranked, rel_bin)
        n += 1

    if n == 0:
        return {"error": "no records evaluated", "split": split}

    return {"split": split, "n_queries": n, "metrics": {k: v / n for k, v in agg.items()}}


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    root_dir = Path(__file__).resolve().parents[2]
    default_ttl = root_dir / "ontology.ttl"
    default_dataset = root_dir / "recsys_wp0" / "eval_data" / "reference_labels.jsonl"
    default_splits = root_dir / "recsys_wp0" / "eval_data" / "reference_splits.json"

    p.add_argument("--ttl", default=str(default_ttl))
    p.add_argument("--dataset", default=str(default_dataset))
    p.add_argument("--splits", default=str(default_splits))
    p.add_argument("--split", default="all", choices=["train", "val", "test", "all"])
    args = p.parse_args()
    out = evaluate_baseline_q1(args.ttl, args.dataset, args.splits, split=args.split)
    print(json.dumps(out, ensure_ascii=False, indent=2))
