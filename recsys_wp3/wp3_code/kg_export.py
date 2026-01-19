from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import List, Tuple

from recsys_wp1.wp1_code.sparql_client import DEFAULT_ENDPOINT, sparql_get, with_prefixes


def _fetch_triples(endpoint: str, limit: int, offset: int) -> List[Tuple[str, str, str]]:
    """Fetch a page of triples (s,p,o) from Fuseki.

    We keep only IRI-to-IRI triples (drop literal objects), which is the most
    robust default for KGE training.
    """
    q = with_prefixes(
        f"""
        SELECT ?s ?p ?o WHERE {{
          ?s ?p ?o .
          FILTER(isIRI(?s) && isIRI(?o))
        }}
        LIMIT {limit}
        OFFSET {offset}
        """
    )
    res = sparql_get(q, endpoint=endpoint)
    out: List[Tuple[str, str, str]] = []
    for b in res.get("results", {}).get("bindings", []):
        out.append((b["s"]["value"], b["p"]["value"], b["o"]["value"]))
    return out


def export_triples(out_path: str, endpoint: str, page_size: int = 5000, max_pages: int | None = None) -> int:
    """Export triples to a TSV file, returning the number of exported triples."""
    n = 0
    offset = 0
    pages = 0
    with open(out_path, "w", encoding="utf-8") as f:
        while True:
            if max_pages is not None and pages >= max_pages:
                break
            rows = _fetch_triples(endpoint=endpoint, limit=page_size, offset=offset)
            if not rows:
                break
            for s, p, o in rows:
                f.write(f"{s}\t{p}\t{o}\n")
                n += 1
            offset += page_size
            pages += 1
    return n


def main() -> None:
    root_dir = Path(__file__).resolve().parents[2]
    default_out = root_dir / "recsys_wp3" / "data_wp3_triples.tsv"
    ap = argparse.ArgumentParser(description="Export Fuseki triples to TSV for KGE training.")
    ap.add_argument("--out", default=str(default_out), help="Output TSV path.")
    ap.add_argument(
        "--endpoint",
        default=os.environ.get("FUSEKI_ENDPOINT", DEFAULT_ENDPOINT),
        help="Fuseki SPARQL endpoint.",
    )
    ap.add_argument("--page_size", type=int, default=5000)
    ap.add_argument("--max_pages", type=int, default=None)
    args = ap.parse_args()

    n = export_triples(out_path=args.out, endpoint=args.endpoint, page_size=args.page_size, max_pages=args.max_pages)
    print(f"OK. wrote {n} triples -> {args.out}")


if __name__ == "__main__":
    main()
