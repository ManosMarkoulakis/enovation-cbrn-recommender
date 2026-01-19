"""Quick cosine similarity heatmap (centres vs technologies)."""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
EMB_PATH = ROOT_DIR / "recsys_wp3" / "recsys_wp3_artifacts" / "entity_embeddings.tsv"

emb = pd.read_csv(EMB_PATH, sep="\t", header=None)
E = {row[0]: np.array(row[1:], dtype=float) for row in emb.values}

centres = [u for u in E.keys() if "#TC" in u and "_SCE" not in u]
techs   = [u for u in E.keys() if "#Res_Tech" in u]

centres = centres[:10]
techs   = techs[:15]

def cos(a,b):
    na=np.linalg.norm(a); nb=np.linalg.norm(b)
    return 0.0 if na==0 or nb==0 else float(np.dot(a,b)/(na*nb))

M = np.zeros((len(centres), len(techs)))
for i,c in enumerate(centres):
    for j,t in enumerate(techs):
        M[i,j]=cos(E[c],E[t])

plt.figure()
plt.imshow(M, aspect="auto")
plt.colorbar()
plt.yticks(range(len(centres)), [c.split("#")[-1] for c in centres])
plt.xticks(range(len(techs)), [t.split("#")[-1] for t in techs], rotation=90)
plt.title("Cosine similarity: Centres vs Technologies")
plt.tight_layout()
plt.show()
