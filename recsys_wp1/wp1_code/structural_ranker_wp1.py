from typing import Dict, List, Tuple

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

def _maxnorm(values: List[float]) -> List[float]:
    if not values:
        return values
    mx = max(values)
    if mx <= 0:
        return [0.0 for _ in values]
    return [v / mx for v in values]

def _compute_cluster_scores(s: Dict[str, float]) -> float:
    tu = s.get("tech_use_count_norm", 0.0)
    tt = s.get("tech_train_count_norm", 0.0)
    ic = s.get("incident_count_norm", 0.0)
    th = s.get("threat_cap_count_norm", 0.0)
    fa = s.get("facility_count_norm", 0.0)
    di = s.get("discipline_count_norm", 0.0)
    co = s.get("course_count_norm", 0.0)
    ne = s.get("network_count_norm", 0.0)

    operational_fit = 0.35 * tu + 0.20 * tt + 0.25 * ic + 0.20 * th
    training_capacity = 0.60 * co + 0.40 * di
    infrastructure_coop = 0.60 * fa + 0.40 * ne

    base_score = 0.65 * operational_fit + 0.15 * training_capacity + 0.20 * infrastructure_coop
    return base_score


def rank_centers_wp1(
    features_by_center: Dict[str, Dict[str, int]],
) -> List[Tuple[str, float]]:
    if not features_by_center:
        return []

    feat_ids = list(next(iter(features_by_center.values())).keys())
    norm_by_center = {c: {} for c in features_by_center}

    for fid in feat_ids:
        raw = [float(features_by_center[c].get(fid, 0)) for c in features_by_center]
        norm = _maxnorm(raw)
        for c, v in zip(features_by_center.keys(), norm):
            norm_by_center[c][fid] = v

    scored = []
    for c, feats in norm_by_center.items():
        score_inputs: Dict[str, float] = {}
        for mp_id, signal_key in _MP_TO_SIGNAL.items():
            score_inputs[signal_key + "_norm"] = feats.get(mp_id, 0.0)
        s = _compute_cluster_scores(score_inputs)
        scored.append((c, float(s)))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored
