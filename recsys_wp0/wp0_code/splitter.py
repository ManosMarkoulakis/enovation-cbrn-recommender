"""Deterministic train/val/test splitting for synthetic WP0 datasets."""

from __future__ import annotations

from typing import Dict, List
import random


def make_splits(
    qids: List[str],
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
    seed: int = 42,
) -> Dict[str, List[str]]:
    """Split qids into train/val/test.

    The split is deterministic (seeded shuffle) so experiments are repeatable.
    """
    if not qids:
        return {"train": [], "val": [], "test": []}

    rnd = random.Random(seed)
    qids_shuf = list(qids)
    rnd.shuffle(qids_shuf)

    n = len(qids_shuf)
    n_train = int(round(n * train_ratio))
    n_val = int(round(n * val_ratio))
    n_train = min(max(n_train, 0), n)
    n_val = min(max(n_val, 0), n - n_train)
    n_test = n - n_train - n_val

    train = qids_shuf[:n_train]
    val = qids_shuf[n_train : n_train + n_val]
    test = qids_shuf[n_train + n_val :]
    assert len(train) + len(val) + len(test) == n

    return {"train": train, "val": val, "test": test}
