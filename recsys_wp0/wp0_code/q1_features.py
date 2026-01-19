from __future__ import annotations

from typing import Dict, List, Set

from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDFS

EN = Namespace("http://www.semanticweb.org/eNOVATION-ontology#")


def _predicate_exists(g: Graph, p: URIRef) -> bool:
    """Return True if predicate p appears at least once in the graph."""
    return next(g.triples((None, p, None)), None) is not None


def subclass_closure(g: Graph, cls: URIRef) -> Set[URIRef]:
    """Return {cls} and all subclasses (transitive closure)."""
    key = (id(g), str(cls))
    cached = _SUBCLASS_CACHE.get(key)
    if cached is not None:
        return cached

    closure: Set[URIRef] = {cls}
    frontier = [cls]
    while frontier:
        x = frontier.pop()
        for sub in g.subjects(RDFS.subClassOf, x):
            if isinstance(sub, URIRef) and sub not in closure:
                closure.add(sub)
                frontier.append(sub)

    _SUBCLASS_CACHE[key] = closure
    return closure


_SUBCLASS_CACHE: Dict[tuple, Set[URIRef]] = {}


def _count_distinct(iterable) -> int:
    return len(set(iterable))


def compute_q1_signals(g: Graph, tech_iri: str, scen_iri: str, center_iri: str) -> Dict[str, int]:
    """Extract simple path-based signals for Q1."""
    C = URIRef(center_iri)
    T = URIRef(tech_iri)
    S = URIRef(scen_iri)

    # Align with SPARQL rdfs:subClassOf* for the selected technology.
    T_closure = subclass_closure(g, T)

    # 1) Tech Use.
    tech_use_matches = set()
    for p in (EN.usesTechnology, EN.hasEquipment):
        for o in g.objects(C, p):
            if o == T or o in T_closure:
                tech_use_matches.add(o)
    tech_use_count = len(tech_use_matches)

    # 2) Tech Training.
    course_for_tech = set()
    for course in g.objects(C, EN.providesTrainingCourse):
        for t in g.objects(course, EN.trainsOnTechnology):
            if t == T or t in T_closure:
                course_for_tech.add(course)
    tech_train_count = len(course_for_tech)

    # 3) Incident match.
    scen_incidents = set(g.objects(S, EN.isBasedOnIncident))
    center_incidents = set(g.objects(C, EN.tacklesIncident))
    for inc in g.subjects(EN.isIncidentTackledBy, C):
        center_incidents.add(inc)
    incident_count = len(scen_incidents.intersection(center_incidents))

    # 4) Threat capability.
    threats = set()
    for inc in scen_incidents:
        for th in g.objects(inc, EN.involvesThreat):
            threats.add(th)

    center_resources = set(g.objects(C, EN.hasEquipment)).union(set(g.objects(C, EN.usesTechnology)))
    threat_cap_matches = set()
    p_addr = EN.addressesThreat if _predicate_exists(g, EN.addressesThreat) else EN.adressesThreat

    for res in center_resources:
        for th in g.objects(res, p_addr):
            if th in threats:
                threat_cap_matches.add(res)
    threat_cap_count = len(threat_cap_matches)

    # 5) Facility.
    facility_count = _count_distinct(g.objects(C, EN.hasFacility))

    # 6) Discipline.
    discipline_count = _count_distinct(g.objects(C, EN.hasTCDiscipline))

    # 7) Courses (general).
    course_count = _count_distinct([c for c in g.objects(C, EN.providesTrainingCourse)])

    # 8) Network.
    network_count = _count_distinct(g.objects(C, EN.connectsWithNetwork))

    return {
        "tech_use_count": tech_use_count,
        "tech_train_count": tech_train_count,
        "incident_count": incident_count,
        "threat_cap_count": threat_cap_count,
        "facility_count": facility_count,
        "discipline_count": discipline_count,
        "course_count": course_count,
        "network_count": network_count,
    }
