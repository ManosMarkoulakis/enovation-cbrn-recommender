from __future__ import annotations

import argparse
import os
from pathlib import Path


def main() -> None:
    """Train a TransE model with PyKEEN and save artifacts.

    Requirements (install in your venv):
      pip install pykeen torch

    This script is intentionally small and reproducible. It writes:
      - model directory (PyKEEN pipeline result)
      - entity_embeddings.tsv
      - relation_embeddings.tsv
    """
    root_dir = Path(__file__).resolve().parents[2]
    default_triples = root_dir / "recsys_wp3" / "data_wp3_triples.tsv"
    default_outdir = root_dir / "recsys_wp3" / "recsys_wp3_artifacts"

    ap = argparse.ArgumentParser(description="Train TransE KGE (PyKEEN) on exported triples")
    ap.add_argument("--triples", default=str(default_triples), help="TSV triples file (s\tp\to)")
    ap.add_argument("--outdir", default=str(default_outdir), help="Output directory")
    ap.add_argument("--model", default="TransE", choices=["TransE", "DistMult"], help="KGE model")
    ap.add_argument("--epochs", type=int, default=200)
    ap.add_argument("--dim", type=int, default=100)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    triples_path = Path(args.triples)
    if not triples_path.exists():
        raise SystemExit(f"Triples file not found: {triples_path}")

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # Import here so the app can run without ML dependencies.
    from pykeen.pipeline import pipeline
    from pykeen.triples import TriplesFactory

    # Load triples
    tf = TriplesFactory.from_path(str(triples_path))

    result = pipeline(
        training=tf,
        testing=tf,
        model=args.model,
        model_kwargs={"embedding_dim": args.dim},
        training_kwargs={"num_epochs": args.epochs},
        random_seed=args.seed,
        device="cuda" if os.environ.get("USE_CUDA") == "1" else "cpu",
    )

    # Save the full result (includes model + config)
    result.save_to_directory(outdir)

    # Export entity & relation embeddings as TSV (URI \t dim0 \t dim1 ...)
    entity_repr = result.model.entity_representations[0]
    rel_repr = result.model.relation_representations[0]

    # Mapping objects
    entity_to_id = result.training.entity_to_id
    rel_to_id = result.training.relation_to_id

    entity_matrix = entity_repr().detach().cpu().numpy()
    rel_matrix = rel_repr().detach().cpu().numpy()

    ent_out = outdir / "entity_embeddings.tsv"
    rel_out = outdir / "relation_embeddings.tsv"

    with open(ent_out, "w", encoding="utf-8") as f:
        for ent, idx in entity_to_id.items():
            vec = entity_matrix[idx]
            f.write(ent)
            for v in vec:
                f.write(f"\t{float(v)}")
            f.write("\n")

    with open(rel_out, "w", encoding="utf-8") as f:
        for rel, idx in rel_to_id.items():
            vec = rel_matrix[idx]
            f.write(rel)
            for v in vec:
                f.write(f"\t{float(v)}")
            f.write("\n")

    print(f"OK. saved model -> {outdir}")
    print(f"OK. saved entity embeddings -> {ent_out}")
    print(f"OK. saved relation embeddings -> {rel_out}")


if __name__ == "__main__":
    main()
