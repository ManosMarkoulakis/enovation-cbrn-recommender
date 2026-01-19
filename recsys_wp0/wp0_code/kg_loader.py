from __future__ import annotations

from dataclasses import dataclass
from typing import List, Set

from rdflib import Graph, Namespace
from rdflib.namespace import RDF, RDFS, OWL

EN = Namespace("http://www.semanticweb.org/eNOVATION-ontology#")


@dataclass(frozen=True)
class KGEntities:
    centers: List[str]
    technologies: List[str]
    scenarios: List[str]


def load_graph(ttl_path: str) -> Graph:
    g = Graph()
    g.parse(ttl_path, format="turtle")
    return g


def _subclass_closure(g: Graph, cls) -> Set:
    subs = {cls}
    changed = True
    while changed:
        changed = False
        for s, o in g.subject_objects(RDFS.subClassOf):
            if o in subs and s not in subs:
                subs.add(s)
                changed = True
    return subs


def instances_of(g: Graph, cls) -> Set:
    subs = _subclass_closure(g, cls)
    inst = set()
    for c in subs:
        for s in g.subjects(RDF.type, c):
            inst.add(s)
    return inst


def get_entities(g: Graph) -> KGEntities:
    """Return named individuals for the core entity types."""
    def filtered_instances(root_cls) -> List[str]:
        inst = instances_of(g, root_cls)
        out = []
        for s in inst:
            if (s, RDF.type, OWL.NamedIndividual) in g:
                out.append(str(s))
        out.sort()
        return out

    return KGEntities(
        centers=filtered_instances(EN.TrainingCentre),
        technologies=filtered_instances(EN.Technology),
        scenarios=filtered_instances(EN.Scenario),
    )
