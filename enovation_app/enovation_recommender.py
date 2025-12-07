import requests
from typing import List, Dict, Any, Optional
import os

FUSEKI_ENDPOINT = os.getenv("FUSEKI_ENDPOINT", "http://147.102.6.178:3030/enovation/sparql")

DISCIPLINE_MAP = {
    "B": "Biological (B)",
    "C": "Chemical (C)",
    "RN": "Radiological / Nuclear (RN)",
}

def run_sparql(query: str) -> Dict[str, Any]:
    headers = {"Accept": "application/sparql-results+json"}
    params = {"query": query}
    try:
        resp = requests.get(FUSEKI_ENDPOINT, params=params, headers=headers, timeout=60)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        print(f"[run_sparql] ERROR: {e}")
        return {}

def sparql_escape_literal(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')

def _get_val(binding: Dict[str, Any], name: str, default=None):
    v = binding.get(name)
    return v.get("value", default) if v else default

def _get_int(binding: Dict[str, Any], name: str) -> int:
    v = binding.get(name)
    if not v:
        return 0
    try:
        return int(v.get("value", "0"))
    except ValueError:
        return 0

_URI_CACHE: Dict[str, Optional[str]] = {}

def get_uri_for_label(label: str) -> Optional[str]:
    if not label:
        return None
    if label in _URI_CACHE:
        return _URI_CACHE[label]

    esc_full = sparql_escape_literal(label)

    # 1) exact
    q_exact = f"""
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT DISTINCT ?s WHERE {{
      ?s rdfs:label ?l .
      FILTER(LCASE(STR(?l)) = LCASE("{esc_full}"))
    }} LIMIT 1
    """
    data = run_sparql(q_exact)
    bindings = data.get("results", {}).get("bindings", [])
    if bindings:
        uri = bindings[0]["s"]["value"]
        _URI_CACHE[label] = uri
        return uri

    # 2) prefix before "("
    prefix = label.split("(", 1)[0].strip()
    if len(prefix) >= 5:
        esc_prefix = sparql_escape_literal(prefix)
        q_prefix = f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT DISTINCT ?s WHERE {{
          ?s rdfs:label ?l .
          FILTER(CONTAINS(LCASE(STR(?l)), LCASE("{esc_prefix}")))
        }} LIMIT 1
        """
        data2 = run_sparql(q_prefix)
        bindings2 = data2.get("results", {}).get("bindings", [])
        if bindings2:
            uri = bindings2[0]["s"]["value"]
            _URI_CACHE[label] = uri
            return uri

    # 3) generic contains
    q_contains = f"""
    PREFIX rdfs: <http://www.w3.org/2000/01/rdfs-schema#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT DISTINCT ?s WHERE {{
      ?s rdfs:label ?l .
      FILTER(CONTAINS(LCASE(STR(?l)), LCASE("{esc_full}")))
    }} LIMIT 1
    """
    data3 = run_sparql(q_contains)
    bindings3 = data3.get("results", {}).get("bindings", [])
    if bindings3:
        uri = bindings3[0]["s"]["value"]
        _URI_CACHE[label] = uri
        return uri

    print(f"[get_uri_for_label] WARNING: no URI found for label: {label!r}")
    _URI_CACHE[label] = None
    return None

ENGINE_QUERY_TEMPLATE = """
PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl:  <http://www.w3.org/2002/07/owl#>
PREFIX xsd:  <http://www.w3.org/2001/XMLSchema#>
PREFIX en:   <http://www.semanticweb.org/eNOVATION-ontology#>

SELECT DISTINCT
  ?center
  ?centerLabel
  (COUNT(DISTINCT ?techUseMatch)     AS ?techUseCount)
  (COUNT(DISTINCT ?courseForTech)    AS ?techTrainCount)  # CHANGED: Count Courses, not Techs
  (COUNT(DISTINCT ?incMatch)         AS ?incidentCount)
  (COUNT(DISTINCT ?threatCapMatch)   AS ?threatCapCount)
  (COUNT(DISTINCT ?facMatch)         AS ?facilityCount)
  (COUNT(DISTINCT ?discMatch)        AS ?disciplineCount)
  (COUNT(DISTINCT ?courseMatch)      AS ?courseCount)
  (COUNT(DISTINCT ?netMatch)         AS ?networkCount)
WHERE {{

  BIND(<{TECH_URI}> AS ?selTech)
  BIND(<{SCEN_URI}> AS ?scenario)

  ?trainingClass rdfs:label "Training centre"@en .
  ?center a ?trainingClass ;
          rdfs:label ?centerLabel .

  # 1. Tech Use (Handles Subclasses)
  OPTIONAL {{
    {{
      ?center en:usesTechnology ?selTech .
      BIND(?selTech AS ?techUseMatch)
    }}
    UNION
    {{
      ?center       en:usesTechnology ?techUseMatch .
      ?techUseMatch a ?techClass .
      ?techClass    rdfs:subClassOf* ?selTech .
    }}
  }}

  # 2. Tech Training (FIXED: Handles Subclasses & binds ?courseForTech)
  OPTIONAL {{
    ?center en:providesTrainingCourse ?courseForTech .
    {{
      ?courseForTech en:trainsOnTechnology ?selTech .
    }}
    UNION
    {{
      ?courseForTech en:trainsOnTechnology ?trainedTechMatch .
      ?trainedTechMatch a ?techClassTrain .
      ?techClassTrain rdfs:subClassOf* ?selTech .
    }}
  }}

  # 3. Incident Match 
  OPTIONAL {{
    ?scenario en:isBasedOnIncident ?incMatch .
    {
      ?center en:tacklesIncident ?incMatch .
    } UNION {
      ?incMatch en:isIncidentTackledBy ?center .
    }
  }}
  
  # 4. Threat Capability
  OPTIONAL {{
    ?scenario     en:isBasedOnIncident ?incForThreat .
    ?incForThreat en:involvesThreat    ?threatAgent .
    ?center (en:hasEquipment | en:usesTechnology) ?res .
    ?res   en:adressesThreat ?threatAgent .
    BIND(?res AS ?threatCapMatch)
  }}

  # 5. Facility
  OPTIONAL {{
    ?center   en:hasFacility ?facMatch .
    ?facMatch a ?facType .
    ?facType  rdfs:subClassOf* en:Facility .
  }}

  # 6. Discipline
  OPTIONAL {{ ?center en:hasTCDiscipline ?discMatch . }}

  # 7. General Courses
  OPTIONAL {{
    ?center      en:providesTrainingCourse ?courseMatch .
    ?courseMatch a en:TrainingCourse .
  }}

  # 8. Network
  OPTIONAL {{ ?center en:connectsWithNetwork ?netMatch . }}

}}
GROUP BY
  ?center
  ?centerLabel
ORDER BY
  DESC(?techTrainCount)
  DESC(?techUseCount)
  DESC(?threatCapCount)
  DESC(?incidentCount)
  DESC(?facilityCount)
  DESC(?disciplineCount)
  DESC(?courseCount)
  DESC(?networkCount)
"""

def get_recommendations(tech_label: str, scen_label: str):
    tech_uri = get_uri_for_label(tech_label)
    scen_uri = get_uri_for_label(scen_label)
    if not tech_uri or not scen_uri:
        print("[get_recommendations] ABORT – missing tech or scenario URI")
        return []

    query = (
        ENGINE_QUERY_TEMPLATE
        .replace("{TECH_URI}", tech_uri)
        .replace("{SCEN_URI}", scen_uri)
    )

    data = run_sparql(query)
    results = []

    for b in data.get("results", {}).get("bindings", []):
        center_uri   = _get_val(b, "center")
        center_label = _get_val(b, "centerLabel")

        tech_use   = _get_int(b, "techUseCount")
        tech_train = _get_int(b, "techTrainCount")
        incident   = _get_int(b, "incidentCount")
        threat_cap = _get_int(b, "threatCapCount")
        facility   = _get_int(b, "facilityCount")
        discipline = _get_int(b, "disciplineCount")
        course     = _get_int(b, "courseCount")
        network    = _get_int(b, "networkCount")

        results.append(
            {
                "center_uri": center_uri,
                "center_label": center_label,
                "region": "",
                "scores": {
                    "tech_use_count": tech_use,
                    "tech_train_count": tech_train,
                    "incident_count": incident,
                    "threat_cap_count": threat_cap,
                    "facility_count": facility,
                    "discipline_count": discipline,
                    "course_count": course,
                    "network_count": network,
                },
            }
        )
    return results

EXPLAIN_QUERY_TEMPLATE = """
PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX en:   <http://www.semanticweb.org/eNOVATION-ontology#>

SELECT DISTINCT
  ?criterion
  ?relatedEntity
  ?entityLabel
  ?explanation
WHERE {{

  BIND(<{CENTER_URI}>   AS ?center)
  BIND(<{TECH_URI}>     AS ?selTech)
  BIND(<{SCENARIO_URI}> AS ?scenario)

  # 1. Tech Use
  {{
    ?center en:usesTechnology ?selTech .
    ?selTech rdfs:label ?entityLabel .
    BIND("Technology Use" AS ?criterion)
    BIND(?selTech AS ?relatedEntity)
    BIND(
      CONCAT(
        "This centre uses the technology '",
        STR(?entityLabel),
        "', which matches your selected technology."
      )
      AS ?explanation
    )
  }}

  UNION

  # 2. Tech Training (Fixed Text)
  {{
    ?center en:providesTrainingCourse ?course .
    ?course en:trainsOnTechnology ?selTech .
    ?course rdfs:label ?entityLabel .
    BIND("Technology Training" AS ?criterion)
    BIND(?course AS ?relatedEntity)
    BIND(
      CONCAT(
        "This centre offers the training course '",
        STR(?entityLabel),
        "', which focuses on your selected technology."
      )
      AS ?explanation
    )
  }}

  UNION

  # 3. Incident
  {{
    ?scenario en:isBasedOnIncident ?inc .
    ?center   en:tacklesIncident   ?inc .
    ?inc rdfs:label ?entityLabel .
    BIND("Incident Coverage" AS ?criterion)
    BIND(?inc AS ?relatedEntity)
    BIND(
      CONCAT(
        "This centre has experience with incidents of type '",
        STR(?entityLabel),
        "', which are part of your scenario."
      )
      AS ?explanation
    )
  }}

  UNION

  # 4. Threat
  {{
    ?scenario en:isBasedOnIncident ?inc2 .
    ?inc2    en:involvesThreat    ?threat .
    ?center ?resProp ?res .
    FILTER(?resProp IN (en:hasEquipment, en:hasCapacity, en:usesTechnology)) .
    ?res    en:adressesThreat ?threat .
    ?threat rdfs:label ?entityLabel .
    BIND("Threat Capability" AS ?criterion)
    BIND(?threat AS ?relatedEntity)
    BIND(
      CONCAT(
        "This centre has resources that address the threat '",
        STR(?entityLabel),
        "' present in your scenario."
      )
      AS ?explanation
    )
  }}

  UNION

  # 5. Facility
  {{
    ?center en:hasFacility ?fac .
    ?fac a ?facClass .
    ?facClass rdfs:subClassOf* en:Facility .
    ?fac rdfs:label ?entityLabel .
    BIND("Facility Match" AS ?criterion)
    BIND(?fac AS ?relatedEntity)
    BIND(
      CONCAT(
        "This centre provides relevant facilities such as '",
        STR(?entityLabel),
        "' to support training and operations."
      )
      AS ?explanation
    )
  }}

  UNION

  # 6. Discipline
  {{
    ?center en:hasTCDiscipline ?disc .
    ?disc rdfs:label ?entityLabel .
    BIND("Discipline Match" AS ?criterion)
    BIND(?disc AS ?relatedEntity)
    BIND(
      CONCAT(
        "This centre includes expertise in '",
        STR(?entityLabel),
        "', which is relevant for this type of scenario."
      )
      AS ?explanation
    )
  }}

  UNION

  # 7. General Courses
  {{
    ?center en:providesTrainingCourse ?courseGen .
    ?courseGen rdfs:label ?entityLabel .
    BIND("Training Capability" AS ?criterion)
    BIND(?courseGen AS ?relatedEntity)
    BIND(
      CONCAT(
        "This centre offers the course '",
        STR(?entityLabel),
        "', contributing to overall CBRN training capacity."
      )
      AS ?explanation
    )
  }}

  UNION

  # 8. Network
  {{
    ?center en:connectsWithNetwork ?net .
    ?net rdfs:label ?entityLabel .
    BIND("Network Links" AS ?criterion)
    BIND(?net AS ?relatedEntity)
    BIND(
      CONCAT(
        "This centre is connected with the network '",
        STR(?entityLabel),
        "', supporting cooperation and knowledge sharing."
      )
      AS ?explanation
    )
  }}
}}
ORDER BY ?criterion ?entityLabel
"""

def get_explanations(tech_label: str, scen_label: str, center_label: str):
    tech_uri   = get_uri_for_label(tech_label)
    scen_uri   = get_uri_for_label(scen_label)
    center_uri = get_uri_for_label(center_label)

    if not tech_uri or not scen_uri or not center_uri:
        print("[get_explanations] missing URI")
        return []

    q = (
        EXPLAIN_QUERY_TEMPLATE
        .replace("{TECH_URI}", tech_uri)
        .replace("{SCENARIO_URI}", scen_uri)
        .replace("{CENTER_URI}", center_uri)
    )
    data = run_sparql(q)
    out = []
    for b in data.get("results", {}).get("bindings", []):
        criterion = _get_val(b, "criterion", "")
        entity = _get_val(b, "entityLabel", "")
        # Map discipline short codes (B/C/RN) to human-readable labels for explanations
        if criterion == "Discipline Match" and entity in DISCIPLINE_MAP:
            entity = DISCIPLINE_MAP[entity]
        out.append(
            {
                "criterion": criterion,
                "entity": entity,
                "text": _get_val(b, "explanation", ""),
            }
        )
    return out


JUST_QUERY_TEMPLATE = """
PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX en:   <http://www.semanticweb.org/eNOVATION-ontology#>

SELECT DISTINCT
  ?edgeType
  ?source
  ?sourceLabel
  ?property
  ?propertyLabel
  ?target
  ?targetLabel
WHERE {{

  BIND(<{CENTER_URI}>   AS ?center)
  BIND(<{TECH_URI}>     AS ?selTech)
  BIND(<{SCENARIO_URI}> AS ?scenario)

  {{
    {{ ?center en:usesTechnology ?selTech . BIND(?selTech AS ?techUsed) }}
    UNION
    {{ ?center en:usesTechnology ?techUsed . ?techUsed a ?techClass . ?techClass rdfs:subClassOf* ?selTech . }}

    BIND("TECH_USE" AS ?edgeType)
    BIND(?center AS ?source)
    BIND(en:usesTechnology AS ?property)
    BIND(?techUsed AS ?target)
  }}

  UNION
  {{
    ?center en:providesTrainingCourse ?course .
    ?course en:trainsOnTechnology ?techTrain .
    ?techTrain a ?techClass2 .
    ?techClass2 rdfs:subClassOf* ?selTech .

    BIND("TECH_TRAINING_COURSE" AS ?edgeType)
    BIND(?center AS ?source)
    BIND(en:providesTrainingCourse AS ?property)
    BIND(?course AS ?target)
  }}

  UNION
  {{
    ?center en:providesTrainingCourse ?course2 .
    ?course2 en:trainsOnTechnology ?techTrain2 .
    ?techTrain2 a ?techClass3 .
    ?techClass3 rdfs:subClassOf* ?selTech .

    BIND("COURSE_TECH" AS ?edgeType)
    BIND(?course2 AS ?source)
    BIND(en:trainsOnTechnology AS ?property)
    BIND(?techTrain2 AS ?target)
  }}

  UNION
  {{
    ?scenario en:isBasedOnIncident ?incident .
    BIND("SCENARIO_INCIDENT" AS ?edgeType)
    BIND(?scenario AS ?source)
    BIND(en:isBasedOnIncident AS ?property)
    BIND(?incident AS ?target)
  }}

  UNION
  {{
    ?scenario en:isBasedOnIncident ?incident2 .
    ?center   en:tacklesIncident   ?incident2 .
    BIND("CENTER_INCIDENT" AS ?edgeType)
    BIND(?center AS ?source)
    BIND(en:tacklesIncident AS ?property)
    BIND(?incident2 AS ?target)
  }}

  UNION
  {{
    ?scenario en:isBasedOnIncident ?incident3 .
    ?incident3 en:involvesThreat ?threat .
    BIND("INCIDENT_THREAT" AS ?edgeType)
    BIND(?incident3 AS ?source)
    BIND(en:involvesThreat AS ?property)
    BIND(?threat AS ?target)
  }}

  UNION
  {{
    ?scenario en:isBasedOnIncident ?incident4 .
    ?incident4 en:involvesThreat ?threat2 .
    ?center ?resProp ?resource .
    FILTER(?resProp IN (en:hasEquipment, en:hasCapacity, en:usesTechnology)) .
    ?resource en:adressesThreat ?threat2 .
    BIND("CENTER_RESOURCE_THREAT" AS ?edgeType)
    BIND(?center AS ?source)
    BIND(?resProp AS ?property)
    BIND(?resource AS ?target)
  }}

  UNION
  {{
    ?center en:hasFacility ?fac .
    ?fac a ?facClass .
    ?facClass rdfs:subClassOf* en:Facility .
    BIND("CENTER_FACILITY" AS ?edgeType)
    BIND(?center AS ?source)
    BIND(en:hasFacility AS ?property)
    BIND(?fac AS ?target)
  }}

  UNION
  {{
    ?center en:hasTCDiscipline ?disc .
    BIND("CENTER_DISCIPLINE" AS ?edgeType)
    BIND(?center AS ?source)
    BIND(en:hasTCDiscipline AS ?property)
    BIND(?disc AS ?target)
  }}

  UNION
  {{
    ?center en:providesTrainingCourse ?courseGen .
    BIND("CENTER_COURSE" AS ?edgeType)
    BIND(?center AS ?source)
    BIND(en:providesTrainingCourse AS ?property)
    BIND(?courseGen AS ?target)
  }}

  UNION
  {{
    ?center en:connectsWithNetwork ?net .
    BIND("CENTER_NETWORK" AS ?edgeType)
    BIND(?center AS ?source)
    BIND(en:connectsWithNetwork AS ?property)
    BIND(?net AS ?target)
  }}

  OPTIONAL {{ ?source  rdfs:label ?srcLab }}
  BIND(IF(BOUND(?srcLab), STR(?srcLab), STRAFTER(STR(?source), "#")) AS ?sourceLabel)

  OPTIONAL {{ ?target  rdfs:label ?tgtLab }}
  BIND(IF(BOUND(?tgtLab), STR(?tgtLab), STRAFTER(STR(?target), "#")) AS ?targetLabel)

  OPTIONAL {{ ?property rdfs:label ?propLab }}
  BIND(IF(BOUND(?propLab), STR(?propLab), STRAFTER(STR(?property), "#")) AS ?propertyLabel)
}}
ORDER BY ?edgeType ?sourceLabel ?targetLabel
"""

def get_justification_graph(tech_label: str, scen_label: str, center_label: str):
    tech_uri   = get_uri_for_label(tech_label)
    scen_uri   = get_uri_for_label(scen_label)
    center_uri = get_uri_for_label(center_label)

    if not tech_uri or not scen_uri or not center_uri:
        print("[get_justification_graph] missing URI")
        return {"edges": [], "paths": []}

    q = (
        JUST_QUERY_TEMPLATE
        .replace("{TECH_URI}", tech_uri)
        .replace("{SCENARIO_URI}", scen_uri)
        .replace("{CENTER_URI}", center_uri)
    )
    data = run_sparql(q)
    edges = []
    for b in data.get("results", {}).get("bindings", []):
        edges.append(
            {
                "edgeType": _get_val(b, "edgeType", ""),
                "source": _get_val(b, "source", ""),
                "sourceLabel": _get_val(b, "sourceLabel", ""),
                "property": _get_val(b, "property", ""),
                "propertyLabel": _get_val(b, "propertyLabel", ""),
                "target": _get_val(b, "target", ""),
                "targetLabel": _get_val(b, "targetLabel", ""),
            }
        )
    paths = [f"{e['sourceLabel']} → {e['propertyLabel']} → {e['targetLabel']}" for e in edges]
    return {"edges": edges, "paths": paths}

SCORE_KEYS = [
    "tech_use_count",
    "tech_train_count",
    "incident_count",
    "threat_cap_count",
    "facility_count",
    "discipline_count",
    "course_count",
    "network_count",
]

def _normalize_scores(items):
    if not items:
        return
    max_vals = {k: 0 for k in SCORE_KEYS}
    for item in items:
        s = item["scores"]
        for k in SCORE_KEYS:
            v = s.get(k, 0)
            if v > max_vals[k]:
                max_vals[k] = v
    for item in items:
        s = item["scores"]
        for k in SCORE_KEYS:
            max_v = max_vals[k]
            v = s.get(k, 0)
            s[k + "_norm"] = v / max_v if max_v > 0 else 0.0

def _compute_cluster_scores(s):
    # Ανάκτηση των κανονικοποιημένων τιμών (0.0 - 1.0)
    tu = s.get("tech_use_count_norm", 0.0)
    tt = s.get("tech_train_count_norm", 0.0)
    ic = s.get("incident_count_norm", 0.0)
    th = s.get("threat_cap_count_norm", 0.0)
    fa = s.get("facility_count_norm", 0.0)
    di = s.get("discipline_count_norm", 0.0)
    co = s.get("course_count_norm", 0.0)
    ne = s.get("network_count_norm", 0.0)

    # Υπολογισμός Core Scores (Μέσοι όροι για χρήση στο Penalty) *ΔΕΝ ΧΡΗΣΙΜΟΠΟΙΕΊΤΑΙ* 
    tech_core = (tu + tt) / 2
    scen_core = (ic + th) / 2
    core_score = (tech_core + scen_core) / 2

    # --- 1. Operational Fit Clustering (Weighted Sum Model) ---
    # Scientific Basis: AHP (Analytic Hierarchy Process) logic.
    # Δίνουμε προτεραιότητα στα 'Hard Constraints' (Tech Use), αλλά διατηρούμε
    # ισχυρή επιρροή του Σεναρίου (Context).
    # Αναλογία: Tech (35% + 25% = 60%) vs Scenario (25% + 15% = 40%)
    operational_fit = 0.35 * tu + 0.20 * tt + 0.25 * ic + 0.20 * th

    # --- 2. Capacity & Infrastructure Clusters ---
    training_capacity = 0.60 * co + 0.40 * di
    infrastructure_coop = 0.60 * fa + 0.40 * ne

    # --- 3. Base Score Calculation ---
    # Δίνουμε κυρίαρχο ρόλο στο Operational Fit (65%) για να διασφαλίσουμε τη σχετικότητα (Relevance).
    base_score = 0.65 * operational_fit + 0.15 * training_capacity + 0.20 * infrastructure_coop

    # --- 4. Penalty Factor (Soft/Concave Approach) --- ΔΕΝ ΧΡΗΣΙΜΟΠΟΙΕΊΤΑΙ 
    # Scientific Basis: Χρήση Concave Function (Root) για ομαλοποίηση.
    # Η γραμμική τιμωρία (Linear Penalty) ήταν πολύ αυστηρή για μεσαία σκορ.
    # Η ρίζα (sqrt) επιτρέπει στα σχετικά κέντρα να μην βυθίζονται, ενώ τα άσχετα παραμένουν χαμηλά.
    # Τύπος: 0.5 + 0.5 * sqrt(core_score)
    penalty_factor = 0.5 + 0.5 * (core_score ** 0.5)

    # --- 5. Final Score & Scaling (Linear Transformation) --- *ΔΕΝ ΧΡΗΣΙΜΟΠΟΙΕΊΤΑΙ* 
    # Υπολογισμός αρχικού τελικού σκορ
    raw_final = base_score * penalty_factor
    
    # Scaling Factor (x1.5): Μετασχηματισμός για βελτίωση UX. *ΔΕΝ ΧΡΗΣΙΜΟΠΟΙΕΊΤΑΙ* 
    # Φέρνει τα σκορ σε πιο "φυσιολογικά" επίπεδα (π.χ. το 6/10 γίνεται 9/10),
    # αξιοποιώντας όλο το εύρος της κλίμακας 0-10.
    # Cap (Ταβάνι) στο 1.0 για να μην υπερβούμε το 10/10.
    final_score_0_1 = min(1.0, raw_final * 1.5)
    
    # Το penalty factor δεν χρεισημοποιείται στην συγκεκριμένη έκδοση, το αποτέλεσμα είναι απλα το base score σε κλίμακα [0-10]
    final_score_0_10 = 10 * base_score

    # Αποθήκευση αποτελεσμάτων στο λεξικό
    s["tech_core"] = tech_core
    s["scenario_core"] = scen_core
    s["core_score"] = core_score
    s["operational_fit"] = operational_fit
    s["training_capacity"] = training_capacity
    s["infrastructure_coop"] = infrastructure_coop
    s["base_score_0_1"] = base_score
    s["penalty_factor"] = penalty_factor
    s["final_score_0_1"] = final_score_0_1
    s["final_score_0_10"] = final_score_0_10
    s["total_score"] = final_score_0_10
    
def build_ui_payload(tech_label: str, scen_label: str):
    recs = get_recommendations(tech_label, scen_label)
    ui_items = []
    for r in recs:
        center_label = r["center_label"]
        explanations = get_explanations(tech_label, scen_label, center_label)
        graph = get_justification_graph(tech_label, scen_label, center_label)
        scores = dict(r["scores"])
        ui_items.append(
            {
                "center_uri": r["center_uri"],
                "center_label": center_label,
                "region": r.get("region", ""),
                "scores": scores,
                "explanations_simple": explanations,
                "graph_paths": graph["paths"],
            }
        )
    _normalize_scores(ui_items)
    for item in ui_items:
        _compute_cluster_scores(item["scores"])
    ui_items.sort(key=lambda x: x["scores"].get("final_score_0_1", 0.0), reverse=True)
    return ui_items
