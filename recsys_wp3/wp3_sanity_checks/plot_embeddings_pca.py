"""Quick PCA visualization of entity embeddings."""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
EMB_PATH = ROOT_DIR / "recsys_wp3" / "recsys_wp3_artifacts" / "entity_embeddings.tsv"

emb = pd.read_csv(EMB_PATH, sep="\t", header=None)
uris = emb.iloc[:,0].astype(str).tolist()
X = emb.iloc[:,1:].to_numpy(dtype=float)

# PCA via SVD (no sklearn dependency).
Xc = X - X.mean(axis=0, keepdims=True)
U,S,Vt = np.linalg.svd(Xc, full_matrices=False)
X2 = Xc @ Vt[:2].T

def kind(u: str) -> str:
    if "#TC" in u: return "Centre"
    if "#Res_Tech" in u: return "Tech"
    if "#SCE" in u or "#TC" in u and "_SCE" in u: return "Scenario"
    return "Other"

kinds = [kind(u) for u in uris]
uniq = sorted(set(kinds))

plt.figure()
for k in uniq:
    idx = [i for i,t in enumerate(kinds) if t==k]
    plt.scatter(X2[idx,0], X2[idx,1], label=k, s=10)

plt.title("Entity embeddings (PCA 2D)")
plt.legend()
plt.show()
