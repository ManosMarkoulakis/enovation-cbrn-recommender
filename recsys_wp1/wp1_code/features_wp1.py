from typing import Dict, Any, Tuple

from .sparql_client import sparql_get, with_prefixes, DEFAULT_ENDPOINT
from .metapaths import METAPATHS

def _count_from_json(res: dict) -> int:
    """Extract integer count from a SPARQL JSON result."""
    bindings = res.get("results", {}).get("bindings", [])
    if not bindings:
        return 0
    row = bindings[0]
    if "cnt" not in row:
        return 0
    v = row["cnt"]["value"]
    try:
        return int(float(v))
    except Exception:
        return 0

def compute_wp1_features(
    center_iri: str,
    tech_iri: str,
    scen_iri: str,
    endpoint: str = DEFAULT_ENDPOINT,
    include_evidence: bool = True,
) -> Tuple[Dict[str, int], Dict[str, Any]]:
    """Compute meta-path counts (and optional evidence) for one centre."""
    feats: Dict[str, int] = {}
    evidence: Dict[str, Any] = {}

    for mp in METAPATHS:
        # Per meta-path: count and optional evidence.
        q_count = with_prefixes(mp.count_query(center_iri, tech_iri, scen_iri))
        cnt = _count_from_json(sparql_get(q_count, endpoint=endpoint))
        feats[mp.mid] = cnt

        if include_evidence:
            q_ev = with_prefixes(mp.evidence_query(center_iri, tech_iri, scen_iri))
            ev = sparql_get(q_ev, endpoint=endpoint)
            evidence[mp.mid] = ev.get("results", {}).get("bindings", [])

    return feats, evidence
