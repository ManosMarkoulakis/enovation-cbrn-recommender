from dataclasses import dataclass
from typing import Callable

@dataclass(frozen=True)
class MetaPath:
    mid: str
    name: str
    intent: str
    count_query: Callable[[str, str, str], str]
    evidence_query: Callable[[str, str, str], str]

def _values(center: str, tech: str, scen: str) -> str:
    return f"""\
VALUES ?center {{ <{center}> }}
VALUES ?tech   {{ <{tech}> }}
VALUES ?scen   {{ <{scen}> }}
"""

# MP1: Centre uses selected technology or equipment (with subclasses).
def mp1_count(center, tech, scen):
    return f"""\
SELECT (COUNT(DISTINCT ?techMatch) AS ?cnt)
WHERE {{
  {_values(center, tech, scen)}
  {{
    ?center en:usesTechnology ?tech .
    BIND(?tech AS ?techMatch)
  }}
  UNION
  {{
    ?center en:usesTechnology ?techMatch .
    ?techMatch a ?techClass .
    ?techClass rdfs:subClassOf* ?tech .
  }}
  UNION
  {{
    ?center en:hasEquipment ?tech .
    BIND(?tech AS ?techMatch)
  }}
  UNION
  {{
    ?center en:hasEquipment ?techMatch .
    ?techMatch a ?techClass2 .
    ?techClass2 rdfs:subClassOf* ?tech .
  }}
}}
"""

def mp1_ev(center, tech, scen):
    return f"""\
SELECT ?techMatch
WHERE {{
  {_values(center, tech, scen)}
  {{
    ?center en:usesTechnology ?tech .
    BIND(?tech AS ?techMatch)
  }}
  UNION
  {{
    ?center en:usesTechnology ?techMatch .
    ?techMatch a ?techClass .
    ?techClass rdfs:subClassOf* ?tech .
  }}
  UNION
  {{
    ?center en:hasEquipment ?tech .
    BIND(?tech AS ?techMatch)
  }}
  UNION
  {{
    ?center en:hasEquipment ?techMatch .
    ?techMatch a ?techClass2 .
    ?techClass2 rdfs:subClassOf* ?tech .
  }}
}}
LIMIT 3
"""

# MP2: Threat capability for selected technology.
def mp2_count(center, tech, scen):
    return f"""\
SELECT (COUNT(DISTINCT ?th) AS ?cnt)
WHERE {{
  {_values(center, tech, scen)}
  ?scen  en:isBasedOnIncident ?incS .
  ?incS  en:involvesThreat  ?th .
  {{
    ?center en:usesTechnology ?tech .
    BIND(?tech AS ?res)
  }}
  UNION
  {{
    ?center en:usesTechnology ?res .
    ?res a ?resClass .
    ?resClass rdfs:subClassOf* ?tech .
  }}
  {{
    ?res en:addressesThreat ?th .
  }}
  UNION
  {{
    ?res en:adressesThreat ?th .
  }}
}}
"""

def mp2_ev(center, tech, scen):
    return f"""\
SELECT ?th ?incS
WHERE {{
  {_values(center, tech, scen)}
  ?scen  en:isBasedOnIncident ?incS .
  ?incS  en:involvesThreat  ?th .
  {{
    ?center en:usesTechnology ?tech .
    BIND(?tech AS ?res)
  }}
  UNION
  {{
    ?center en:usesTechnology ?res .
    ?res a ?resClass .
    ?resClass rdfs:subClassOf* ?tech .
  }}
  {{
    ?res en:addressesThreat ?th .
  }}
  UNION
  {{
    ?res en:adressesThreat ?th .
  }}
}}
LIMIT 3
"""

# MP3: Incident coverage (scenario incidents tackled by the centre).
def mp3_count(center, tech, scen):
    return f"""\
SELECT (COUNT(DISTINCT ?inc) AS ?cnt)
WHERE {{
  {_values(center, tech, scen)}
  ?scen  en:isBasedOnIncident ?inc .
  {{
    ?center en:tacklesIncident ?inc .
  }}
  UNION
  {{
    ?inc en:isIncidentTackledBy ?center .
  }}
}}
"""

def mp3_ev(center, tech, scen):
    return f"""\
SELECT ?inc
WHERE {{
  {_values(center, tech, scen)}
  ?scen  en:isBasedOnIncident ?inc .
  {{
    ?center en:tacklesIncident ?inc .
  }}
  UNION
  {{
    ?inc en:isIncidentTackledBy ?center .
  }}
}}
LIMIT 3
"""

# MP4: Infrastructure (facilities)
def mp4_count(center, tech, scen):
    return f"""\
SELECT (COUNT(DISTINCT ?fac) AS ?cnt)
WHERE {{
  {_values(center, tech, scen)}
  ?center en:hasFacility ?fac .
}}
"""

def mp4_ev(center, tech, scen):
    return f"""\
SELECT ?fac
WHERE {{
  {_values(center, tech, scen)}
  ?center en:hasFacility ?fac .
}}
LIMIT 3
"""

# MP5: Connectivity (networks)
def mp5_count(center, tech, scen):
    return f"""\
SELECT (COUNT(DISTINCT ?net) AS ?cnt)
WHERE {{
  {_values(center, tech, scen)}
  ?center en:connectsWithNetwork ?net .
}}
"""

def mp5_ev(center, tech, scen):
    return f"""\
SELECT ?net
WHERE {{
  {_values(center, tech, scen)}
  ?center en:connectsWithNetwork ?net .
}}
LIMIT 3
"""

# MP6: Technology training (including subclasses).
def mp6_count(center, tech, scen):
    return f"""\
SELECT (COUNT(DISTINCT ?course) AS ?cnt)
WHERE {{
  {_values(center, tech, scen)}
  ?center en:providesTrainingCourse ?course .
  {{
    ?course en:trainsOnTechnology ?tech .
  }}
  UNION
  {{
    ?course en:trainsOnTechnology ?trainedTechMatch .
    ?trainedTechMatch a ?techClassTrain .
    ?techClassTrain rdfs:subClassOf* ?tech .
  }}
}}
"""

def mp6_ev(center, tech, scen):
    return f"""\
SELECT ?course
WHERE {{
  {_values(center, tech, scen)}
  ?center en:providesTrainingCourse ?course .
  {{
    ?course en:trainsOnTechnology ?tech .
  }}
  UNION
  {{
    ?course en:trainsOnTechnology ?trainedTechMatch .
    ?trainedTechMatch a ?techClassTrain .
    ?techClassTrain rdfs:subClassOf* ?tech .
  }}
}}
LIMIT 3
"""

# MP7: Training Courses Volume
def mp7_count(center, tech, scen):
    return f"""\
SELECT (COUNT(DISTINCT ?course) AS ?cnt)
WHERE {{
  {_values(center, tech, scen)}
  ?center en:providesTrainingCourse ?course .
}}
"""

def mp7_ev(center, tech, scen):
    return f"""\
SELECT ?course
WHERE {{
  {_values(center, tech, scen)}
  ?center en:providesTrainingCourse ?course .
}}
LIMIT 3
"""

# MP8: Discipline Coverage
def mp8_count(center, tech, scen):
    return f"""\
SELECT (COUNT(DISTINCT ?d) AS ?cnt)
WHERE {{
  {_values(center, tech, scen)}
  ?center en:hasTCDiscipline ?d .
}}
"""

def mp8_ev(center, tech, scen):
    return f"""\
SELECT ?d
WHERE {{
  {_values(center, tech, scen)}
  ?center en:hasTCDiscipline ?d .
}}
LIMIT 3
"""

METAPATHS = [
    MetaPath("MP1", "Direct Technology Capability",
             "Centre explicitly uses the selected technology.",
             mp1_count, mp1_ev),
    MetaPath("MP2", "Threat Overlap Evidence",
             "Centre's incident threats overlap with scenario incident threats.",
             mp2_count, mp2_ev),
    MetaPath("MP3", "Incident Overlap Evidence",
             "Centre tackles incidents used as the basis for the scenario.",
             mp3_count, mp3_ev),
    MetaPath("MP4", "Infrastructure: Facility Availability",
             "Centre infrastructure signal via facility availability.",
             mp4_count, mp4_ev),
    MetaPath("MP5", "Connectivity: Network Participation",
             "Centre connectivity signal via networks it connects with.",
             mp5_count, mp5_ev),
    MetaPath("MP6", "Technology Training",
             "Centre provides training courses that train on the selected technology.",
             mp6_count, mp6_ev),
    MetaPath("MP7", "Training Courses Volume",
             "Centre provides training courses (overall training capacity signal).",
             mp7_count, mp7_ev),
    MetaPath("MP8", "Discipline Coverage",
             "Centre covers multiple CBRN disciplines (B/C/RN).",
             mp8_count, mp8_ev),
]
