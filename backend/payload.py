"""Dashboard payload builders — shared by the REST and WebSocket routers."""
from __future__ import annotations

import time

from .core import csv_loader
from .config import settings
from .core import nedocs as n
from .core.explainer import explain
from .core.predictor import FEATURE_META, HARDWARE_FEATURES, MODEL_FEATURES, predict_2h


def _fmt(v: float | None, nd: int = 2):
    return round(float(v), nd) if v is not None else None


def archetype_payload(st, csv_summary: dict | None, web: dict | None = None) -> dict:
    feats = st.effective()
    score = n.score_from_features(feats)
    forecast = predict_2h(feats)
    expl = explain(feats, forecast, web, csv_summary)
    now = time.time()
    tail = list(st.trend)[-settings.ws_tail_points:] if st.trend else []

    if st.override:
        mode = "override"
    elif st.census_source in ("emr", "simulator"):
        mode = "live"
    else:
        mode = "manual"

    features = {}
    for f in MODEL_FEATURES:
        v = feats.get(f)
        features[f] = {"value": _fmt(v, 2 if f in HARDWARE_FEATURES else 1),
                       "unit": FEATURE_META[f]["unit"]}
    hardware = {
        "ambient_noise_db": {
            "value": _fmt(feats.get("ambient_noise_db", 0.0), 1),
            "unit": "dB",
        },
        "arrival_velocity": features["arrival_velocity"],
        "equipment_chaos_index": features["equipment_chaos_index"],
    }

    return {
        "id": st.key,
        "context": st.context,
        "hospital_type": st.hospital_type,
        "mode": mode,
        "overridden": bool(st.override),
        "override_fields": sorted(st.override.keys()) if st.override else [],
        "features": features,
        "hardware": hardware,
        "staleness_s": {k: (round(v, 1) if v is not None else None)
                        for k, v in st.staleness_s().items()},
        "last_census_age_s": round(max(0.0, now - st.last_census_ts), 1),
        "last_sensor_age_s": round(max(0.0, now - st.last_sensor_ts), 1),
        "score": expl["score"],
        "level": expl["level"],
        "level_label": expl["level_label"],
        "summary": expl["summary"],
        "factors": expl["factors"],
        "actions": expl["actions"],
        "terms": expl["terms"],
        "forecast": expl["forecast"],
        "drivers": expl["drivers"],
        "context_note": expl["context_note"],
        "environment_note": expl["environment_note"],
        "csv": {
            "hospital_type": st.hospital_type,
            "rows": (csv_summary or {}).get("rows"),
            "typical_census": (csv_summary or {}).get("typical_census"),
            "month_median": ((csv_summary or {}).get("monthly") or {}).get("median"),
            "month_count": ((csv_summary or {}).get("monthly") or {}).get("count"),
            "global_mean": ((csv_summary or {}).get("global") or {}).get("mean"),
            "global_p90": ((csv_summary or {}).get("global") or {}).get("p90"),
        },
        "trend_tail": [
            {"t": round(p["t"], 1), "now": p["now"], "f2h": p["f2h"]} for p in tail
        ],
    }


def context_payload(context: str) -> dict:
    ctx = csv_loader.get(context)
    month = time.localtime().tm_mon
    archetypes = []
    web = store.web
    for st in store.archetypes(context):
        csv_summary = ctx.summary(st.hospital_type, month=month) if ctx else {}
        archetypes.append(archetype_payload(st, csv_summary, web))
    return {"context": context, "archetypes": archetypes,
            "month": month, "csv_loaded": ctx is not None,
            "web": web_note_payload()}


def sources_payload() -> dict:
    from .database import db  # local import to avoid cycles

    rows = db.count_rows()
    return {
        "mqtt": {
            "enabled": store.mqtt.get("enabled"),
            "connected": store.mqtt.get("connected", False),
            "error": store.mqtt.get("error"),
            "last_message_age_s": (
                round(time.time() - store.mqtt["last_message_ts"], 1)
                if store.mqtt.get("last_message_ts") else None
            ),
        },
        "demo": {"active": store.demo.get("active", False),
                 "mode": store.demo.get("mode")},
        "web": {
            "ok": store.web.get("ok", False),
            "fetched_at": store.web.get("fetched_at"),
            "error": store.web.get("error"),
        },
        "db": rows,
        "csv": {
            "urban_rows": len(csv_loader.get("urban").df) if csv_loader.get("urban") else 0,
            "rural_rows": len(csv_loader.get("rural").df) if csv_loader.get("rural") else 0,
        },
        "uptime_s": round(time.time() - store.started_at, 1),
    }


def full_payload() -> dict:
    return {
        "generated_at": time.time(),
        "contexts": {
            "urban": context_payload("urban"),
            "rural": context_payload("rural"),
        },
        "sources": sources_payload(),
    }


def web_note_payload() -> dict:
    """Public web-context fields consumed by the UI + explainer."""
    w = store.web
    out = {"ok": bool(w.get("ok")), "error": w.get("error"),
           "fetched_at": w.get("fetched_at")}
    if w.get("ok"):
        out.update({
            "temperature_c": _fmt(w.get("temperature_c")),
            "apparent_temperature_c": _fmt(w.get("apparent_temperature_c")),
            "humidity_pct": _fmt(w.get("humidity_pct")),
            "wind_kmh": _fmt(w.get("wind_kmh")),
            "weather_code": w.get("weather_code"),
            "weather_text": w.get("weather_text"),
            "aqi": _fmt(w.get("aqi")),
            "aqi_category": w.get("aqi_category"),
            "pm2_5": _fmt(w.get("pm2_5")),
            "pm10": _fmt(w.get("pm10")),
        })
    return out


# import at the bottom to avoid circular import (state.store uses core only)
from .state import store  # noqa: E402
