from __future__ import annotations

from typing import Dict, List, Tuple, Optional

from recsys_wp1.wp1_code.features_wp1 import compute_wp1_features
from recsys_wp1.wp1_code.metapaths import METAPATHS
from recsys_wp1.wp1_code.sparql_client import DEFAULT_ENDPOINT
from .topsis import topsis_scores
from .entropy_weights import compute_entropy_weights


# Subjective weights (sum to 1.0). Names reflect current meta-path intent.
DEFAULT_WP2_SUBJECTIVE_WEIGHTS: Dict[str, float] = {
    "MP1": 0.30,  # Technology use / equipment match
    "MP2": 0.18,  # Threat capability
    "MP3": 0.18,  # Incident coverage
    "MP4": 0.14,  # Facilities / infrastructure
    "MP5": 0.08,  # Networks
    "MP6": 0.04,  # Technology training (courses)
    "MP7": 0.04,  # Training course volume
    "MP8": 0.04,  # Discipline coverage
}


def _meta_ids() -> List[str]:
    return [mp.mid for mp in METAPATHS]


def _build_normalized_features(
    tech_iri: str,
    scen_iri: str,
    centres: List[str],
    include_evidence: bool = False,
    endpoint: str = DEFAULT_ENDPOINT,
) -> Tuple[Dict[str, Dict[str, float]], Dict[str, dict]]:
    """Compute per-centre meta-path features (raw counts)."""
    features_raw: Dict[str, Dict[str, float]] = {}
    evidence_by_center: Dict[str, dict] = {}

    for c in centres:
        feats, ev = compute_wp1_features(
            center_iri=c,
            tech_iri=tech_iri,
            scen_iri=scen_iri,
            include_evidence=include_evidence,
            endpoint=endpoint,
        )
        features_raw[c] = feats
        evidence_by_center[c] = ev

    return features_raw, evidence_by_center


def _hybrid_weights(
    features_norm: Dict[str, Dict[str, float]],
    subjective: Dict[str, float],
    alpha: float = 0.5,
) -> Dict[str, float]:
    """Blend subjective weights with entropy weights.

    w_final = alpha * w_subjective_norm + (1 - alpha) * w_entropy
    """
    meta_ids = _meta_ids()
    if not meta_ids:
        return {}

    subj_sum = sum(subjective.get(fid, 0.0) for fid in meta_ids)
    if subj_sum > 0:
        subj_norm = {fid: subjective.get(fid, 0.0) / subj_sum for fid in meta_ids}
    else:
        m = len(meta_ids)
        subj_norm = {fid: 1.0 / m for fid in meta_ids}

    entropy_w = compute_entropy_weights(features_norm, meta_ids)

    combined: Dict[str, float] = {}
    for fid in meta_ids:
        w_s = subj_norm.get(fid, 0.0)
        w_e = entropy_w.get(fid, 0.0)
        combined[fid] = alpha * w_s + (1.0 - alpha) * w_e

    total = sum(combined.values())
    if total <= 1e-12:
        m = len(meta_ids)
        return {fid: 1.0 / m for fid in meta_ids}

    return {fid: w / total for fid, w in combined.items()}


def rank_centers_wp2(
    tech_iri: str,
    scen_iri: str,
    centres: List[str],
    include_evidence: bool = False,
    endpoint: str = DEFAULT_ENDPOINT,
) -> Tuple[List[Tuple[str, float]], Optional[Dict[str, dict]]]:
    """WP2 structural ranker: TOPSIS over meta-path features.

    Note: alpha is set to 1.0, so only subjective weights are used.
    """
    if not centres:
        return [], {} if include_evidence else None

    features_norm, evidence_by_center = _build_normalized_features(
        tech_iri=tech_iri,
        scen_iri=scen_iri,
        centres=centres,
        include_evidence=include_evidence,
        endpoint=endpoint,
    )

    meta_ids = _meta_ids()

    used_criteria: List[str] = []
    for fid in meta_ids:
        if any(features_norm.get(c, {}).get(fid, 0.0) > 0.0 for c in centres):
            used_criteria.append(fid)

    if not used_criteria:
        ranking = [(c, 0.0) for c in centres]
        return ranking, {} if include_evidence else None

    hybrid_w = _hybrid_weights(features_norm, DEFAULT_WP2_SUBJECTIVE_WEIGHTS, alpha=1.0)

    scores_by_center = topsis_scores(
        feature_dict=features_norm,
        weights=hybrid_w,
        criteria=used_criteria,
    )

    ranking = sorted(scores_by_center.items(), key=lambda x: x[1], reverse=True)

    if not include_evidence:
        return ranking, None

    detailed_evidence: Dict[str, dict] = {}
    for c in centres:
        detailed_evidence[c] = {
            "features": features_norm.get(c, {}),
            "evidence": evidence_by_center.get(c, {}),
            "weights": {fid: hybrid_w[fid] for fid in used_criteria},
            "criteria": used_criteria,
        }

    return ranking, detailed_evidence
