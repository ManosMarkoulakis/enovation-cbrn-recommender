from __future__ import annotations

from typing import Dict, List, Tuple, Optional

from recsys_wp3.wp3_code.embed_ranker import EmbeddingIndex, rank_centres_by_embedding


def rank_centers_wp3_embedding(
    tech_iri: str,
    scen_iri: str,
    centres: List[str],
    emb_index: EmbeddingIndex,
    include_evidence: bool = False,
) -> Tuple[List[Tuple[str, float]], Optional[Dict[str, dict]]]:
    """Embedding-only ranker using cosine similarity."""
    emb_ranking = rank_centres_by_embedding(
        emb=emb_index,
        centres=centres,
        tech_iri=tech_iri,
        scen_iri=scen_iri,
    )
    ranking = emb_ranking

    if not include_evidence:
        return ranking, None

    evidence: Dict[str, dict] = {}
    for c, s in ranking:
        evidence[c] = {"emb": s}

    return ranking, evidence
