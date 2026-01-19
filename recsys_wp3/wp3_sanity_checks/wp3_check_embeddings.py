"""Sanity check: report entities missing from the embedding file."""

import json
from pathlib import Path
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[2]
EMB_PATH = ROOT_DIR / "recsys_wp3" / "recsys_wp3_artifacts" / "entity_embeddings.tsv"
DATASET_PATH = ROOT_DIR / "recsys_wp0" / "eval_data" / "reference_labels.jsonl"

# Load embeddings.
emb = pd.read_csv(
    EMB_PATH,
    sep="\t",
    header=None
)
E = set(emb[0])

# Load reference dataset.
rows = [json.loads(l) for l in open(DATASET_PATH, "r", encoding="utf-8")]

needed = set()
for r in rows:
    needed.add(r["query"]["technology"])
    needed.add(r["query"]["scenario"])
    for c in r["candidates"]:
        needed.add(c)

missing = [x for x in needed if x not in E]

print("missing:", len(missing))
print(missing[:5])
