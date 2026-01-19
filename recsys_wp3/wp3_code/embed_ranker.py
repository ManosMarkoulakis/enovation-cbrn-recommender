from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class EmbeddingIndex:
    """Simple in-memory embedding store loaded from TSV."""

    entity: Dict[str, List[float]]


def load_entity_embeddings(path: str | Path) -> EmbeddingIndex:
    p = Path(path)
    ent: Dict[str, List[float]] = {}
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            parts = line.split("\t")
            iri = parts[0]
            vec = [float(x) for x in parts[1:]]
            ent[iri] = vec
    return EmbeddingIndex(entity=ent)


def _cosine(a: List[float], b: List[float]) -> float:
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def rank_centres_by_embedding(
    emb: EmbeddingIndex,
    centres: List[str],
    tech_iri: str,
    scen_iri: str,
    alpha_query: float = 0.5,
) -> List[Tuple[str, float]]:
    """Rank centres by similarity to a query embedding.

    Query embedding: centroid-based representation
      e_Q = alpha * e(tech) + (1-alpha) * e(scenario)

    If an entity embedding is missing, the score is 0.0.
    """
    e_t = emb.entity.get(tech_iri)
    e_s = emb.entity.get(scen_iri)
    if e_t is None or e_s is None:
        # not enough info to build a query embedding
        return [(c, 0.0) for c in centres]

    e_q = [alpha_query * t + (1.0 - alpha_query) * s for t, s in zip(e_t, e_s)]

    scored: List[Tuple[str, float]] = []
    for c in centres:
        e_c = emb.entity.get(c)
        scored.append((c, 0.0 if e_c is None else _cosine(e_q, e_c)))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored
