"""Загрузка обучающего датасета (data/raw/data.csv) в таблицу training_data."""
from __future__ import annotations

import configparser
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.db import get_conn, init_schema, training_table  # noqa: E402


def main() -> int:
    cfg = configparser.ConfigParser()
    cfg.read(ROOT / "config.ini", encoding="utf-8")
    raw = ROOT / cfg["PATHS"]["raw_csv"]
    if not raw.is_file():
        print(f"Нет файла: {raw}", file=sys.stderr)
        return 1

    df = pd.read_csv(raw)
    df = df.drop(columns=[c for c in df.columns if str(c).startswith("Unnamed")], errors="ignore")
    if "id" in df.columns:
        df = df.drop(columns=["id"])
    if "diagnosis" not in df.columns:
        print("В CSV нет колонки diagnosis", file=sys.stderr)
        return 1

    init_schema()
    table = training_table()

    rows = []
    for _, r in df.iterrows():
        diag = str(r["diagnosis"])
        feats = {c: float(r[c]) for c in df.columns if c != "diagnosis"}
        rows.append((diag, json.dumps(feats)))

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(f"TRUNCATE {table} RESTART IDENTITY;")
        cur.executemany(f"INSERT INTO {table} (diagnosis, features) VALUES (%s, %s);", rows)
        conn.commit()

    print(f"Загружено строк в {table}: {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
