"""What-if engine — answers "how does changing X move the score?".

For the *current* NEDOCS the effect is exact (linear formula coefficients).
For the *T+2h RF forecast* the effect is a local two-sided numerical
sensitivity at the operating point (the model is nonlinear).

Also flags level-band crossings ("+10 patients ⇒ crosses into Overcrowded").
"""
from __future__ import annotations

from . import nedocs as n
from .explainer import explain
from .predictor import FEATURE_META, MODEL_FEATURES, predict_2h

COUNT_FEATURES = {"ed_pts", "ed_beds", "admits", "hosp_beds", "vents"}


def _clamp(features: dict) -> dict:
    out = dict(features)
    for f in MODEL_FEATURES:
        try:
            out[f] = max(0.0, float(out.get(f, 0.0)))
        except (TypeError, ValueError):
            out[f] = 0.0
    return out


def current_per_unit(feature: str, features: dict) -> float | None:
    """Exact marginal effect of +1 natural unit on the current NEDOCS."""
    ed_beds = features.get("ed_beds", 1.0) or 1.0
    hosp_beds = features.get("hosp_beds", 1.0) or 1.0
    if feature == "ed_pts":
        return 85.8 / ed_beds
    if feature == "admits":
        return 600.0 / hosp_beds
    if feature == "vents":
        return 13.4
    if feature == "longest_wait":
        return 0.93
    if feature == "last_wait":
        return 5.64
    if feature == "ed_beds":
        return -85.8 * features.get("ed_pts", 0.0) / (ed_beds ** 2)
    if feature == "hosp_beds":
        return -600.0 * features.get("admits", 0.0) / (hosp_beds ** 2)
    return None  # hardware features only affect the T+2h forecast


def evaluate(features: dict, base_score: float | None = None,
             web: dict | None = None, csv_summary: dict | None = None) -> dict:
    """Full what-if response for an arbitrary census snapshot."""
    features = _clamp(features)
    score = n.score_from_features(features)
    forecast = predict_2h(features)
    level = n.level_of(score)
    base_level = n.level_of(base_score) if base_score is not None else None

    sensitivity = []
    for f in MODEL_FEATURES:
        meta = FEATURE_META[f]
        step = meta["step"]
        up = dict(features)
        up[f] = features[f] + step
        up = _clamp(up)

        per_unit_now = current_per_unit(f, features)
        delta_now = per_unit_now * step if per_unit_now is not None else None
        delta_2h = (predict_2h(up) - forecast) / step if per_unit_now is None else None
        # forecast is also nudged by census features, but we already show the
        # current-score effect there; only report 2h effect for hardware.
        sensitivity.append({
            "feature": f,
            "label": meta["label"],
            "unit": meta["unit"],
            "step": step,
            "tag": meta["tag"],
            "delta_now": round(delta_now, 2) if delta_now is not None else None,
            "delta_2h": round(delta_2h, 2) if delta_2h is not None else None,
        })

    # level crossing vs. whatever the dashboard was showing
    crossing = None
    if base_level is not None and base_level["key"] != level["key"]:
        dirn = "up" if score > base_score else "down"
        crossing = {
            "direction": dirn,
            "from": base_level["label"],
            "to": level["label"],
        }

    expl = explain(features, forecast, web, csv_summary)
    expl["level_crossing"] = crossing
    return {
        "score": score,
        "level": level["key"],
        "level_label": level["label"],
        "explanation": expl,
        "sensitivity": sensitivity,
        "crossing": crossing,
    }
