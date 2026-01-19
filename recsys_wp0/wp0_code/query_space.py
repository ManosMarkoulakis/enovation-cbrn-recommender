"""Query-space utilities for synthetic dataset generation.

WP0 needs a deterministic way to enumerate (Technology, Scenario) pairs.
We keep it intentionally simple and reproducible.
"""

from __future__ import annotations

from typing import Dict, List
import itertools
import random

from rdflib import Graph

from .kg_loader import get_entities


def enumerate_centers(g: Graph) -> List[str]:
    """Return all candidate TrainingCentre IRIs."""
    return get_entities(g).centers


def enumerate_q1_queries(g: Graph, max_queries: int = 120, seed: int = 42) -> List[Dict[str, str]]:
    """Enumerate Q1 queries: {technology, scenario}.

    If the full Cartesian product is large, we sample a fixed-size subset.
    """
    ents = get_entities(g)
    pairs = list(itertools.product(ents.technologies, ents.scenarios))
    if len(pairs) <= max_queries:
        chosen = pairs
    else:
        rnd = random.Random(seed)
        chosen = rnd.sample(pairs, k=max_queries)

    # Stable order (important for repeatable qids)
    chosen = sorted(chosen)
    return [{"technology": t, "scenario": s} for (t, s) in chosen]
