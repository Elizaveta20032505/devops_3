"""Подключение к PostgreSQL. Креды только из переменных окружения."""
from __future__ import annotations

import configparser
import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import psycopg2
from psycopg2.extensions import connection as PGConnection


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _cfg() -> configparser.ConfigParser:
    cfg = configparser.ConfigParser()
    cfg.read(_root() / "config.ini", encoding="utf-8")
    return cfg


def predictions_table() -> str:
    return _cfg()["DB"].get("predictions_table", "predictions")


def training_table() -> str:
    return _cfg()["DB"].get("training_table", "training_data")


def _conn_params() -> dict:
    required = ("POSTGRES_HOST", "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD")
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        raise RuntimeError(f"Не заданы переменные окружения для БД: {missing}")
    return {
        "host": os.environ["POSTGRES_HOST"],
        "port": int(os.environ.get("POSTGRES_PORT", "5432")),
        "dbname": os.environ["POSTGRES_DB"],
        "user": os.environ["POSTGRES_USER"],
        "password": os.environ["POSTGRES_PASSWORD"],
    }


@contextmanager
def get_conn() -> Iterator[PGConnection]:
    conn = psycopg2.connect(**_conn_params())
    try:
        yield conn
    finally:
        conn.close()


def init_schema() -> None:
    ddl_predictions = f"""
        CREATE TABLE IF NOT EXISTS {predictions_table()} (
            id        BIGSERIAL PRIMARY KEY,
            ts        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            features  JSONB       NOT NULL,
            label     TEXT        NOT NULL,
            proba     DOUBLE PRECISION
        );
    """
    ddl_training = f"""
        CREATE TABLE IF NOT EXISTS {training_table()} (
            id        BIGSERIAL PRIMARY KEY,
            diagnosis TEXT NOT NULL,
            features  JSONB NOT NULL
        );
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(ddl_predictions)
        cur.execute(ddl_training)
        conn.commit()


def save_prediction(features: dict, label: str, proba: float | None) -> None:
    sql = f"INSERT INTO {predictions_table()} (features, label, proba) VALUES (%s, %s, %s);"
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, (json.dumps(features), label, proba))
        conn.commit()


def fetch_last_predictions(limit: int = 10) -> list[dict]:
    sql = f"SELECT id, ts, features, label, proba FROM {predictions_table()} ORDER BY id DESC LIMIT %s;"
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, (limit,))
        rows = cur.fetchall()
    return [
        {"id": r[0], "ts": r[1].isoformat(), "features": r[2], "label": r[3], "proba": r[4]}
        for r in rows
    ]
