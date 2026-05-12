from __future__ import annotations

import json
import sys
from pathlib import Path

from sklearn.datasets import load_breast_cancer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.db import get_conn, init_schema, training_table


def _to_kaggle(n: str) -> str:
    if n.startswith("mean "):
        return n[5:] + "_mean"
    if n.startswith("worst "):
        return n[6:] + "_worst"
    if n.endswith(" error"):
        return n[:-6] + "_se"
    return n


def main() -> int:
    bc = load_breast_cancer(as_frame=True)
    X = bc.data
    X.columns = [_to_kaggle(c) for c in X.columns]
    y = 1 - bc.target

    init_schema()
    table = training_table()

    rows = []
    for i, (_, r) in enumerate(X.iterrows()):
        diag = "M" if int(y.iloc[i]) == 1 else "B"
        feats = {c: float(r[c]) for c in X.columns}
        rows.append((diag, json.dumps(feats)))

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(f"TRUNCATE {table} RESTART IDENTITY;")
        cur.executemany(f"INSERT INTO {table} (diagnosis, features) VALUES (%s, %s);", rows)
        conn.commit()

    print(f"Загружено строк в {table}: {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
