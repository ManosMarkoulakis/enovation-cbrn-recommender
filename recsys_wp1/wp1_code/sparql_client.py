"""SPARQL client helpers for WP1."""

import os
import time
import requests

DEFAULT_ENDPOINT = os.getenv("FUSEKI_ENDPOINT", "http://147.102.6.178:3030/enovation/sparql")

PREFIXES = """\
PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl:  <http://www.w3.org/2002/07/owl#>
PREFIX xsd:  <http://www.w3.org/2001/XMLSchema#>
PREFIX en:   <http://www.semanticweb.org/eNOVATION-ontology#>
"""

def with_prefixes(body: str) -> str:
    """Prepend shared prefixes to a SPARQL body."""
    return PREFIXES + "\n" + body

def sparql_get(query: str, endpoint: str = DEFAULT_ENDPOINT, timeout: int = 60, retries: int = 4) -> dict:
    """Robust SPARQL GET with retry+backoff (WP1 eval can issue many small queries)."""
    headers = {"Accept": "application/sparql-results+json"}
    params = {"query": query}

    last_err = None
    for i in range(retries):
        try:
            r = requests.get(endpoint, params=params, headers=headers, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last_err = e
            time.sleep(0.8 * (2 ** i))  # 0.8s, 1.6s, 3.2s, 6.4s
    raise last_err
