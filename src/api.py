"""FastAPI: здоровье сервиса и предсказание модели."""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, create_model

from src.inference import load_artifacts, predict_from_features, read_feature_names_for_openapi

logger = logging.getLogger("api")


def _predict_body_model() -> type[BaseModel]:
    names = read_feature_names_for_openapi()
    example = {n: 0.0 for n in names}
    return create_model(
        "PredictBody",
        __config__=ConfigDict(json_schema_extra={"example": example}, extra="forbid"),
        **{n: (float, Field(default=0.0, title=n.replace("_", " ")[:40])) for n in names},
    )


PredictBody = _predict_body_model()


def _db_enabled() -> bool:
    return os.environ.get("DB_ENABLED", "1") not in ("0", "false", "False", "")


@asynccontextmanager
async def _lifespan(app: FastAPI):
    try:
        app.state.model, app.state.feature_names = load_artifacts()
    except FileNotFoundError:
        app.state.model = None
        app.state.feature_names = []

    app.state.db_ready = False
    if _db_enabled():
        try:
            from src.db import init_schema

            init_schema()
            app.state.db_ready = True
        except Exception as e:
            logger.warning("DB init failed, продолжаем без БД: %s", e)
    yield


app = FastAPI(title="breast-cancer-logreg", version="0.2", lifespan=_lifespan)


@app.get("/health")
def health() -> dict:
    ok = getattr(app.state, "model", None) is not None
    return {
        "status": "ok" if ok else "no_model",
        "db": "ok" if getattr(app.state, "db_ready", False) else "off",
    }


@app.post("/predict")
def predict(body: PredictBody) -> dict:
    if app.state.model is None:
        raise HTTPException(
            status_code=503,
            detail="Модель не найдена.",
        )
    try:
        payload = body.model_dump()
        result = predict_from_features(payload, app.state.model, app.state.feature_names)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    if getattr(app.state, "db_ready", False):
        try:
            from src.db import save_prediction

            save_prediction(payload, result["label"], result.get("malignant_probability"))
        except Exception as e:
            logger.warning("Не удалось записать предсказание в БД: %s", e)
    return result


@app.get("/predictions")
def predictions(limit: int = Query(10, ge=1, le=200)) -> dict:
    if not getattr(app.state, "db_ready", False):
        raise HTTPException(status_code=503, detail="БД недоступна.")
    try:
        from src.db import fetch_last_predictions

        items = fetch_last_predictions(limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}") from e
    return {"items": items, "count": len(items)}
