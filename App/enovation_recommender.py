"""eNOVATION CBRN recommender (Fuseki/SPARQL)."""

import logging
import os
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

FUSEKI_ENDPOINT = os.getenv("FUSEKI_ENDPOINT", "http://147.102.6.178:3030/enovation/sparql")

DISCIPLINE_MAP = {
    "B": "Biological (B)",
    "C": "Chemical (C)",
    "RN": "Radiological / Nuclear (RN)",
}

# SPARQL query execution.
def run_sparql(query: str) -> Dict[str, Any]:
    headers = {"Accept": "application/sparql-results+json"}
    params = {"query": query}
    try:
        resp = requests.get(FUSEKI_ENDPOINT, params=params, headers=headers, timeout=60)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        # Keep the app running even if Fuseki is temporarily unavailable.
        logger.warning("run_sparql failed: %s", e)
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

# Label/IRI helpers.
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

# Core recommendation query.
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
  (COUNT(DISTINCT ?courseForTech)    AS ?techTrainCount)
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
  
  # 4. Threat Capability (ONLY for selected technology)
  OPTIONAL {{
    ?scenario     en:isBasedOnIncident ?incForThreat .
    ?incForThreat en:involvesThreat    ?threatAgent .

    {
      ?center en:usesTechnology ?selTech .
      BIND(?selTech AS ?res)
    }
    UNION
    {
      ?center en:usesTechnology ?res .
      ?res a ?resClass .
      ?resClass rdfs:subClassOf* ?selTech .
    }

    ?res en:addressesThreat ?threatAgent .

    # Count as 1 (boolean) if ANY matching selected technology exists
    BIND(?selTech AS ?threatCapMatch)
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

# Recommendation results from label inputs.
def get_recommendations(tech_label: str, scen_label: str):
    tech_uri = get_uri_for_label(tech_label)
    scen_uri = get_uri_for_label(scen_label)
    if not tech_uri or not scen_uri:
        print("[get_recommendations] ABORT – missing tech or scenario URI")
        return []

    query = (
# Core recommendation query.
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

# Recommendation results from URI inputs.
def get_recommendations_by_uri(tech_uri: str, scen_uri: str):
    if not tech_uri or not scen_uri:
        print("[get_recommendations_by_uri] ABORT: missing tech or scenario URI")
        return []

    query = (
# Core recommendation query.
        ENGINE_QUERY_TEMPLATE
        .replace("{TECH_URI}", tech_uri)
        .replace("{SCEN_URI}", scen_uri)
    )

    data = run_sparql(query)
    results = []

    for b in data.get("results", {}).get("bindings", []):
        center_uri = _get_val(b, "center")
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

  # 2. Tech Training 
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
    ?res    en:addressesThreat ?threat .
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

# Human-readable explanations for a centre.
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

  # 1) Tech Use (selected tech)
  {{
    {{
      ?center en:usesTechnology ?selTech .
      BIND(?selTech AS ?techUsed)
    }}
    UNION
    {{
      ?center en:usesTechnology ?techUsed .
      ?techUsed a ?techClass .
      ?techClass rdfs:subClassOf* ?selTech .
    }}

    BIND("TECH_USE" AS ?edgeType)
    BIND(?center AS ?source)
    BIND(en:usesTechnology AS ?property)
    BIND(?techUsed AS ?target)
  }}

  UNION

  # 2) Tech Training (two edges; Python will join into one meta-path)
  {{
    ?center en:providesTrainingCourse ?course .
    {{
      ?course en:trainsOnTechnology ?selTech .
    }}
    UNION
    {{
      ?course en:trainsOnTechnology ?trainedTech .
      ?trainedTech a ?techClass2 .
      ?techClass2 rdfs:subClassOf* ?selTech .
    }}

    BIND("TECH_TRAINING_COURSE" AS ?edgeType)
    BIND(?center AS ?source)
    BIND(en:providesTrainingCourse AS ?property)
    BIND(?course AS ?target)
  }}

  UNION
  {{
    ?center en:providesTrainingCourse ?course2 .
    {{
      ?course2 en:trainsOnTechnology ?selTech .
      BIND(?selTech AS ?trainedTech2)
    }}
    UNION
    {{
      ?course2 en:trainsOnTechnology ?trainedTech2 .
      ?trainedTech2 a ?techClass3 .
      ?techClass3 rdfs:subClassOf* ?selTech .
    }}

    BIND("COURSE_TECH" AS ?edgeType)
    BIND(?course2 AS ?source)
    BIND(en:trainsOnTechnology AS ?property)
    BIND(?trainedTech2 AS ?target)
  }}

  UNION

  # 3) Scenario -> Incident 
  {{
    ?scenario en:isBasedOnIncident ?incident .
    BIND("SCENARIO_INCIDENT" AS ?edgeType)
    BIND(?scenario AS ?source)
    BIND(en:isBasedOnIncident AS ?property)
    BIND(?incident AS ?target)
  }}

  UNION

  # 3) Centre -> Incident
  {{
    ?scenario en:isBasedOnIncident ?incident2 .
    ?center   en:tacklesIncident   ?incident2 .
    BIND("CENTER_INCIDENT" AS ?edgeType)
    BIND(?center AS ?source)
    BIND(en:tacklesIncident AS ?property)
    BIND(?incident2 AS ?target)
  }}

  UNION

  # 4) Incident -> Threat
  {{
    ?scenario en:isBasedOnIncident ?incident3 .
    ?incident3 en:involvesThreat ?threat .
    BIND("INCIDENT_THREAT" AS ?edgeType)
    BIND(?incident3 AS ?source)
    BIND(en:involvesThreat AS ?property)
    BIND(?threat AS ?target)
  }}

  UNION

  # 4) Selected technology -> Threat 
  {{
    ?scenario en:isBasedOnIncident ?incident4 .
    ?incident4 en:involvesThreat ?threat2 .

    {{
      ?center en:usesTechnology ?selTech .
      BIND(?selTech AS ?resource)
    }}
    UNION
    {{
      ?center en:usesTechnology ?resource .
      ?resource a ?resClass .
      ?resClass rdfs:subClassOf* ?selTech .
    }}

    ?resource en:addressesThreat ?threat2 .

    BIND("TECH_THREAT" AS ?edgeType)
    BIND(?resource AS ?source)
    BIND(en:addressesThreat AS ?property)
    BIND(?threat2 AS ?target)
  }}

  UNION

  # 5) Facilities
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

  # 6) Disciplines
  {{
    ?center en:hasTCDiscipline ?disc .
    BIND("CENTER_DISCIPLINE" AS ?edgeType)
    BIND(?center AS ?source)
    BIND(en:hasTCDiscipline AS ?property)
    BIND(?disc AS ?target)
  }}

  UNION

  # 7) Courses (all)
  {{
    ?center en:providesTrainingCourse ?courseGen .
    BIND("CENTER_COURSE" AS ?edgeType)
    BIND(?center AS ?source)
    BIND(en:providesTrainingCourse AS ?property)
    BIND(?courseGen AS ?target)
  }}

  UNION

  # 8) Networks
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


# Justification graph for the UI.
def get_justification_graph(tech_label: str, scen_label: str, center_label: str, scores: Optional[Dict[str, Any]] = None):

    tech_uri   = get_uri_for_label(tech_label)
    scen_uri   = get_uri_for_label(scen_label)
    center_uri = get_uri_for_label(center_label)

    if not tech_uri or not scen_uri or not center_uri:
        print("[get_justification_graph] missing URI")
        return {"edges": [], "graph_groups": [], "paths": []}

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

    # Dedup (edgeType, source, property, target)
    seen = set()
    dedup = []
    for e in edges:
        k = (e["edgeType"], e["source"], e["property"], e["target"])
        if k in seen:
            continue
        seen.add(k)
        dedup.append(e)
    edges = dedup

    def node(label: str) -> Dict[str, Any]:
        return {"kind": "node", "label": label}

    def pred(label: str, direction: str = "fwd") -> Dict[str, Any]:
        return {"kind": "pred", "label": label, "dir": direction}

    # Index edges by type
    by_type: Dict[str, List[Dict[str, Any]]] = {}
    for e in edges:
        by_type.setdefault(e["edgeType"], []).append(e)

    # Core entities for meta-paths
    tc = center_label
    sel_tech = tech_label
    scen = scen_label

    # --- 1) Tech Use ---
    tech_use_paths: List[List[Dict[str, Any]]] = []
    for e in by_type.get("TECH_USE", []):
        # TC -> usesTechnology -> usedTech (often equals selected tech label)
        tech_use_paths.append([
            node(tc),
            pred("Uses Technology", "fwd"),
            node(e["targetLabel"]),
        ])

    # --- 2) Tech Training (join center->course and course->tech) ---
    tech_training_paths: List[List[Dict[str, Any]]] = []
    # map course label -> tech label
    course_to_tech = {}
    for e in by_type.get("COURSE_TECH", []):
        course_to_tech.setdefault(e["source"], []).append(e["targetLabel"])
    for e in by_type.get("TECH_TRAINING_COURSE", []):
        course_uri = e["target"]
        course_label = e["targetLabel"]
        techs = course_to_tech.get(course_uri, [])
        # If multiple techs, create one meta-path per tech (usually 1)
        for tlabel in techs:
            tech_training_paths.append([
                node(tc),
                pred("Provides Training Course", "fwd"),
                node(course_label),
                pred("Trains On Technology", "fwd"),
                node(tlabel),
            ])

    # --- 3) Incident Coverage (join center->incident and scenario->incident, reverse direction on scenario leg) ---
    incident_paths: List[List[Dict[str, Any]]] = []
    # scenario->incident mapping
    scen_inc_by_inc = {e["target"]: e for e in by_type.get("SCENARIO_INCIDENT", [])}
    for e in by_type.get("CENTER_INCIDENT", []):
        inc_uri = e["target"]
        inc_label = e["targetLabel"]
        if inc_uri in scen_inc_by_inc:
            # TC -> Tackles -> Incident  AND  Scenario -> isBasedOnIncident -> Incident (reverse in displayed meta-path)
            incident_paths.append([
                node(tc),
                pred("Tackles Incident", "fwd"),
                node(inc_label),
                pred("Is Based On Incident", "rev"),
                node(scen),
            ])

    # --- 4) Threat Capability ---
    threat_paths: List[List[Dict[str, Any]]] = []
    # Build: TC -> usesTech -> tech -> addressesThreat -> threat <- involvesThreat <- incident <- isBasedOnIncident <- scenario
    # Use TECH_USE to get tech labels used, TECH_THREAT for tech->threat, INCIDENT_THREAT for incident->threat, SCENARIO_INCIDENT for scenario->incident
    # Index incident->threat and scenario->incident
    incident_to_threat = {e["source"]: e for e in by_type.get("INCIDENT_THREAT", [])}  # incident uri -> edge
    scenario_to_inc = {e["target"]: e for e in by_type.get("SCENARIO_INCIDENT", [])}   # incident uri -> edge
    tech_to_threat_edges = by_type.get("TECH_THREAT", [])

    # Need a tech used edge to connect TC->tech for the same tech label as TECH_THREAT source
    tech_used_by_uri = {e["target"]: e for e in by_type.get("TECH_USE", [])}  # tech uri -> edge

    for e in tech_to_threat_edges:
        tech_uri_used = e["source"]   # tech/resource uri
        threat_uri = e["target"]
        threat_label = e["targetLabel"]

        # Find incident that involves this threat
        inc_edge = None
        for inc, it_edge in incident_to_threat.items():
            if it_edge["target"] == threat_uri:
                inc_edge = it_edge
                break
        if not inc_edge:
            continue
        inc_label = inc_edge["sourceLabel"]
        inc_uri = inc_edge["source"]

        # Ensure scenario is based on that incident
        scen_inc_edge = scenario_to_inc.get(inc_uri)
        if not scen_inc_edge:
            continue

        # Ensure the centre uses this technology/resource (selected tech or subclass instance)
        used_edge = tech_used_by_uri.get(tech_uri_used)
        if not used_edge:
            continue

        tech_label_used = used_edge["targetLabel"]

        threat_paths.append([
            node(tc),
            pred("Uses Technology", "fwd"),
            node(tech_label_used),
            pred("addresses Threat", "fwd"),
            node(threat_label),
            pred("Involves Threat", "rev"),
            node(inc_label),
            pred("Is Based On Incident", "rev"),
            node(scen),
        ])

    # --- 5) Facilities ---
    facility_paths = [
        [node(tc), pred("Has Facility", "fwd"), node(e["targetLabel"])]
        for e in by_type.get("CENTER_FACILITY", [])
    ]

    # --- 6) Disciplines ---
    disc_paths = []
    for e in by_type.get("CENTER_DISCIPLINE", []):
        lab = e["targetLabel"]
        if lab in DISCIPLINE_MAP:
            lab = DISCIPLINE_MAP[lab]
        disc_paths.append([node(tc), pred("Has Discipline", "fwd"), node(lab)])

    # --- 7) Courses ---
    course_paths = [
        [node(tc), pred("Provides Training Course", "fwd"), node(e["targetLabel"])]
        for e in by_type.get("CENTER_COURSE", [])
    ]

    # --- 8) Networks ---
    network_paths = [
        [node(tc), pred("Connects With Network", "fwd"), node(e["targetLabel"])]
        for e in by_type.get("CENTER_NETWORK", [])
    ]

    # Decide which sections to include (only non-zero criteria)
    # Prefer provided scores if available (most accurate)
    def nonzero(key: str) -> bool:
        if scores and isinstance(scores, dict):
            return int(scores.get(key, 0) or 0) > 0
        return True  # fallback, will prune by empty paths

    groups = []
    def add_group(title: str, key: str, paths: List[List[Dict[str, Any]]]):
        if not paths:
            return
        if scores and not nonzero(key):
            return
        groups.append({"title": title, "paths": paths})

    add_group("Technology Use", "tech_use_count", tech_use_paths)
    add_group("Technology Training", "tech_train_count", tech_training_paths)
    add_group("Incident Coverage", "incident_count", incident_paths)
    add_group("Threat Capability", "threat_cap_count", threat_paths)
    add_group("Facilities", "facility_count", facility_paths)
    add_group("Disciplines", "discipline_count", disc_paths)
    add_group("Courses", "course_count", course_paths)
    add_group("Networks", "network_count", network_paths)

    # Backwards-compatible flat paths (plain strings) - used only if UI can't render structured groups
    flat_paths = []
    for g in groups:
        for p in g["paths"]:
            # Render to simple string with markers; UI will ignore if it uses graph_groups.
            parts = []
            for step in p:
                if step["kind"] == "node":
                    parts.append(step["label"])
                else:
                    parts.append(f"[{step['label']}]")
            flat_paths.append(" ➜ ".join(parts))

    return {"edges": edges, "graph_groups": groups, "paths": flat_paths}


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

# Score normalization and aggregation.
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
    """Compute baseline (WP0/WP1) score from normalized criterion signals.

    Inputs are expected in [0,1] (see _normalize_scores). We keep this baseline
    stable so later WPs (TOPSIS, KGE, hybrid) can compare against the same core.
    """

    tu = s.get("tech_use_count_norm", 0.0)
    tt = s.get("tech_train_count_norm", 0.0)
    ic = s.get("incident_count_norm", 0.0)
    th = s.get("threat_cap_count_norm", 0.0)
    fa = s.get("facility_count_norm", 0.0)
    di = s.get("discipline_count_norm", 0.0)
    co = s.get("course_count_norm", 0.0)
    ne = s.get("network_count_norm", 0.0)


    # 1) Operational fit: technology + scenario relevance (weighted sum baseline).
    operational_fit = 0.35 * tu + 0.20 * tt + 0.25 * ic + 0.20 * th

    # 2) Capacity/infrastructure: supporting signals (training + facilities/networks).
    training_capacity = 0.60 * co + 0.40 * di
    infrastructure_coop = 0.60 * fa + 0.40 * ne

    # 3) Baseline score (0..1). The 0..10 is only a UI-friendly scaling.
    base_score = 0.65 * operational_fit + 0.15 * training_capacity + 0.20 * infrastructure_coop

    final_score_0_1 = base_score
    final_score_0_10 = 10.0 * base_score

    # Store for UI / evaluation.
    s["operational_fit"] = operational_fit
    s["training_capacity"] = training_capacity
    s["infrastructure_coop"] = infrastructure_coop
    s["base_score_0_1"] = base_score
    s["final_score_0_1"] = final_score_0_1
    s["final_score_0_10"] = final_score_0_10
    s["total_score"] = final_score_0_10
    
# UI payload builder.
def build_ui_payload(tech_label: str, scen_label: str):
    recs = get_recommendations(tech_label, scen_label)
    ui_items = []
    for r in recs:
        center_label = r["center_label"]
        explanations = get_explanations(tech_label, scen_label, center_label)
        # Build scores before the justification graph to hide zero-criteria paths.
        scores = dict(r["scores"])
        graph = get_justification_graph(tech_label, scen_label, center_label, scores=scores)
        ui_items.append(
            {
                "center_uri": r["center_uri"],
                "center_label": center_label,
                "region": r.get("region", ""),
                "scores": scores,
                "explanations_simple": explanations,
                "graph_paths": graph.get("paths", []),
                "graph_groups": graph.get("graph_groups", []),
            }
        )
    _normalize_scores(ui_items)
    for item in ui_items:
        _compute_cluster_scores(item["scores"])
    ui_items.sort(key=lambda x: x["scores"].get("final_score_0_1", 0.0), reverse=True)
    return ui_items

# Ranking helper for evaluation.
def rank_centers_by_uri(tech_uri: str, scen_uri: str, candidates: List[str]):
    """Rank centres using the same scoring logic as the UI recommender."""
    recs = get_recommendations_by_uri(tech_uri, scen_uri)
    by_uri = {r["center_uri"]: r for r in recs}

    items = []
    for cid in candidates:
        row = by_uri.get(cid)
        if row is None:
            items.append({"center_uri": cid, "scores": {k: 0 for k in SCORE_KEYS}})
        else:
            items.append({"center_uri": cid, "scores": dict(row["scores"])})

    _normalize_scores(items)
    for item in items:
        _compute_cluster_scores(item["scores"])

    items.sort(key=lambda x: x["scores"].get("final_score_0_1", 0.0), reverse=True)
    return [(i["center_uri"], i["scores"].get("final_score_0_1", 0.0)) for i in items]
