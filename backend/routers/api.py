"""REST API for the PredictED dashboard."""
from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..core import csv_loader
from .. import payload as payload_mod
from ..config import settings
from ..core.predictor import FEATURE_META, MODEL_FEATURES
from ..core.whatif import evaluate
from ..database import db
from ..ingestion.mqtt_listener import apply_sensor_message
from ..state import store

router = APIRouter(prefix="/api")


# ------------------------------------------------------------------ models
class TelemetryIn(BaseModel):
    hospital_type: str
    sensor_type: str
    value: float


class WhatIfIn(BaseModel):
    hospital_type: str
    features: dict[str, float] = Field(default_factory=dict)


class OverrideIn(BaseModel):
    hospital_type: str
    features: dict[str, float] = Field(default_factory=dict)


# ------------------------------------------------------------------ helpers
def _require_archetype(hospital_type: str):
    st = store.archetype_for(hospital_type)
    if st is None:
        raise HTTPException(status_code=404,
                            detail=f"Unknown hospital_type '{hospital_type}'")
    return st


# ------------------------------------------------------------------ health
@router.get("/health")
def health():
    snap = store.snapshot()
    return {"status": "ok", "time": time.time(), "store": snap}


# ------------------------------------------------------------------ state
@router.get("/contexts")
def contexts():
    out = []
    for context in ("urban", "rural"):
        ctx = csv_loader.get(context)
        out.append({
            "context": context,
            "hospital_types": csv_loader.archetypes_for(context),
            "rows": len(ctx.df) if ctx else 0,
        })
    return {"contexts": out}


@router.get("/state")
def state(context: str | None = Query(default=None)):
    if context is None:
        return payload_mod.full_payload()
    if context not in ("urban", "rural"):
        raise HTTPException(status_code=400, detail="context must be urban|rural")
    return {"generated_at": time.time(),
            "context": payload_mod.context_payload(context),
            "sources": payload_mod.sources_payload()}


@router.get("/web")
def web():
    return payload_mod.web_note_payload()


# ------------------------------------------------------------------ CSV context
@router.get("/context/{context}/summary")
def csv_summary(context: str, hospital_type: str, month: int | None = Query(default=None)):
    if context not in ("urban", "rural"):
        raise HTTPException(status_code=400, detail="context must be urban|rural")
    ctx = csv_loader.get(context)
    if ctx is None:
        raise HTTPException(status_code=503, detail="CSV context not loaded")
    month = month or time.localtime().tm_mon
    return ctx.summary(hospital_type, month=month)


@router.get("/context/{context}/history")
def csv_history(context: str, hospital_type: str,
                months: int = Query(default=36, ge=3, le=240)):
    if context not in ("urban", "rural"):
        raise HTTPException(status_code=400, detail="context must be urban|rural")
    ctx = csv_loader.get(context)
    if ctx is None:
        raise HTTPException(status_code=503, detail="CSV context not loaded")
    return {"hospital_type": hospital_type,
            "points": ctx.history(hospital_type, months=months)}


# ------------------------------------------------------------------ what-if
@router.post("/whatif")
def whatif(body: WhatIfIn):
    st = _require_archetype(body.hospital_type)
    feats = st.effective()
    for f, v in body.features.items():
        if f in MODEL_FEATURES:
            try:
                feats[f] = float(v)
            except (TypeError, ValueError):
                raise HTTPException(status_code=422, detail=f"bad value for {f}")
    base_score = None
    base_archetype = store.archetype_for(body.hospital_type)
    if base_archetype is not None:
        from ..core import nedocs as n
        base_score = n.score_from_features(base_archetype.effective())
    ctx = csv_loader.get(st.context)
    csv_summary = ctx.summary(st.hospital_type, month=time.localtime().tm_mon) if ctx else {}
    result = evaluate(feats, base_score=base_score, web=store.web, csv_summary=csv_summary)
    result["hospital_type"] = body.hospital_type
    return result


# ------------------------------------------------------------------ overrides
@router.post("/state/override")
def set_override(body: OverrideIn):
    st = _require_archetype(body.hospital_type)
    valid = {f: v for f, v in body.features.items()
             if f in MODEL_FEATURES and v is not None}
    if not valid:
        raise HTTPException(status_code=422, detail="no valid features supplied")
    store.set_override(body.hospital_type, valid)
    db.insert_emr(body.hospital_type, valid, source="override")
    store.record_trend(body.hospital_type)
    return {"ok": True, "overridden": sorted(valid.keys()),
            "features": st.effective()}


@router.delete("/state/override")
def clear_override(hospital_type: str):
    _require_archetype(hospital_type)
    store.clear_override(hospital_type)
    store.record_trend(hospital_type)
    return {"ok": True, "overridden": []}


# ------------------------------------------------------------------ telemetry (HTTP fallback for devices without MQTT)
@router.post("/telemetry")
def telemetry(body: TelemetryIn):
    data = {"hospital_type": body.hospital_type,
            "sensor_type": body.sensor_type, "value": body.value}
    ok = apply_sensor_message(store, data, db)
    if not ok:
        raise HTTPException(status_code=422,
                            detail="unrecognised sensor_type or hospital_type")
    return {"ok": True}


# ------------------------------------------------------------------ meta
@router.get("/feature-meta")
def feature_meta():
    return {k: v for k, v in FEATURE_META.items()}
