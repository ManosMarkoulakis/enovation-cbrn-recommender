from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Dict, List

from recsys_wp1.wp1_code.features_wp1 import compute_wp1_features
from recsys_wp1.wp1_code.structural_ranker_wp1 import rank_centers_wp1
from recsys_wp1.wp1_code.sparql_client import DEFAULT_ENDPOINT, sparql_get, with_prefixes


ROOT_DIR = Path(__file__).resolve().parents[2]
DATASET_PATH = ROOT_DIR / "recsys_wp0" / "eval_data" / "reference_labels.jsonl"
SPLITS_PATH = ROOT_DIR / "recsys_wp0" / "eval_data" / "reference_splits.json"

_LABEL_CACHE: Dict[str, str] = {}

_MP_TO_SIGNAL = {
    "MP1": "tech_use_count",
    "MP6": "tech_train_count",
    "MP3": "incident_count",
    "MP2": "threat_cap_count",
    "MP4": "facility_count",
    "MP8": "discipline_count",
    "MP7": "course_count",
    "MP5": "network_count",
}


def label_for(uri: str, endpoint: str) -> str:
    cached = _LABEL_CACHE.get(uri)
    if cached is not None:
        return cached

    q = with_prefixes(
        f"""
        SELECT ?label WHERE {{
          <{uri}> rdfs:label ?label .
        }} LIMIT 1
        """
    )
    try:
        data = sparql_get(q, endpoint=endpoint)
        bindings = data.get("results", {}).get("bindings", [])
        if bindings:
            lab = bindings[0]["label"]["value"]
            _LABEL_CACHE[uri] = lab
            return lab
    except Exception:
        pass

    lab = uri.split("#")[-1]
    _LABEL_CACHE[uri] = lab
    return lab


def load_split_rows(split: str) -> List[dict]:
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        rows = [json.loads(line) for line in f]

    with open(SPLITS_PATH, "r", encoding="utf-8") as f:
        splits = json.load(f)

    ids = set(splits.get(split, []))
    split_rows = [r for r in rows if r.get("qid") in ids]
    if not split_rows:
        raise RuntimeError("No rows found for the requested split.")

    return split_rows


def _format_counts(feats: Dict[str, float]) -> str:
    items = []
    for mp_id, signal_key in _MP_TO_SIGNAL.items():
        v = feats.get(mp_id, 0)
        items.append(f"{signal_key}={int(v)}")
    return ", ".join(items)


def main() -> None:
    ap = argparse.ArgumentParser(description="WP1 sanity check (meta-path ranking).")
    ap.add_argument("--split", default="test", choices=["train", "val", "test"], help="Split to sample")
    ap.add_argument("--n", type=int, default=3, help="Number of queries to sample")
    ap.add_argument("--seed", type=int, default=42, help="Random seed")
    ap.add_argument("--endpoint", default=DEFAULT_ENDPOINT, help="Fuseki endpoint override")
    args = ap.parse_args()

    rows = load_split_rows(args.split)
    rnd = random.Random(args.seed)
    n = min(max(args.n, 1), len(rows))
    samples = rnd.sample(rows, k=n)

    for idx, q in enumerate(samples, start=1):
        qid = q["qid"]
        tech = q["query"]["technology"]
        scen = q["query"]["scenario"]
        candidates = q["candidates"]

        labels_1_5: Dict[str, int] = q["labels_1_5"]
        labels_bin: Dict[str, int] = q["labels_bin"]

        tech_label = label_for(tech, args.endpoint)
        scen_label = label_for(scen, args.endpoint)

        print(f"\n=== Sample {idx}/{n} ===")
        print(f"QID: {qid}")
        print(f"TECH: {tech_label}")
        print(f"SCEN: {scen_label}\n")

        print("Reference labels_1_5 / labels_bin:")
        for cid, rating in labels_1_5.items():
            b = labels_bin.get(cid, 0)
            cname = label_for(cid, args.endpoint)
            print(f"  {cname} -> {rating} (bin: {b})")

        features_by_center: Dict[str, Dict[str, float]] = {}
        for cid in candidates:
            feats, _ = compute_wp1_features(
                center_iri=cid,
                tech_iri=tech,
                scen_iri=scen,
                endpoint=args.endpoint,
                include_evidence=False,
            )
            features_by_center[cid] = feats

        ranking = rank_centers_wp1(features_by_center)

        print("\nWP1 structural ranking (meta-path features):")
        for rank, (cid, score) in enumerate(ranking, start=1):
            r1_5 = labels_1_5.get(cid)
            b = labels_bin.get(cid)
            cname = label_for(cid, args.endpoint)
            counts = _format_counts(features_by_center.get(cid, {}))
            print(f"{rank:2d}. {cname} | wp1_score={score:.4f} | ref_1_5={r1_5} | ref_bin={b}")
            print(f"    counts: {counts}")

    print("\nDone.")


if __name__ == "__main__":
    main()
