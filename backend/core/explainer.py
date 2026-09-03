"""Rule-based explainer for PredictED.

Deterministic, hospital-safe: turns the current census + hardware + web
context into a plain-language explanation — level, contributing factors
with severity tags, recommended actions, forecast drivers, and context notes
from the CSV baselines and the live Delhi weather/AQI feed.

No LLM, no randomness: every sentence is derived from thresholds and the
additive NEDOCS terms, so it always agrees with the numbers on screen.
"""
from __future__ import annotations

from . import nedocs as n
from .predictor import FEATURE_META, NORMAL_CENTERS, feature_importances

# --------------------------------------------------------------------------
# threshold rules (hours, ratios, sensor ranges) — from PredictED domain notes
# (Data.py / update_dataset.py / Upgraded_App.py comments)
WAIT_TARGET_HRS = 4.0
LAST_WAIT_MILD = 1.5
LAST_WAIT_HIGH = 3.0
VENT_HIGH = 5
VELOCITY_BUSY = 0.5
VELOCITY_SURGE = 1.2
CHAOS_HIGH = 6.0
NOISE_HIGH = 85.0
NOISE_ELEVATED = 70.0
AQI_UNHEALTHY = 100

SEVERITY = {0: "info", 1: "low", 2: "medium", 3: "high"}


def _sev(n_: int) -> str:
    return SEVERITY.get(n_, "info")


def _drivers(features: dict, csv_typical: dict | None) -> list[dict]:
    """Top forecast drivers = RF importance weighted by deviation from normal.

    Deviation uses the archetype's typical census from the CSV when available,
    else a generic normal centre.
    """
    importances = feature_importances()
    scaled = []
    for feat, weight in importances.items():
        meta = FEATURE_META.get(feat, {})
        if weight <= 0:
            continue
        val = features.get(feat, 0.0)
        center = None
        if csv_typical and feat in csv_typical and csv_typical[feat] is not None:
            center = float(csv_typical[feat])
        else:
            center = NORMAL_CENTERS.get(feat, 0.0)
        # deviation measured in "typical magnitudes" so features stay comparable
        mag = abs(center) * 0.6 + 0.5 if center else 1.0
        dev = (val - center) / mag
        scaled.append({
            "feature": feat,
            "label": meta.get("label", feat),
            "tag": meta.get("tag", "CENSUS"),
            "weight": weight,
            "deviation": round(dev, 2),
            "strength": round(float(min(max(dev, -3.0), 3.0) * weight * 100.0), 1),
        })
    scaled.sort(key=lambda d: abs(d["strength"]), reverse=True)
    return scaled[:4]


def explain(features: dict, forecast_2h: float, web: dict | None,
            csv_summary: dict | None) -> dict:
    score = n.score_from_features(features)
    level = n.level_of(score)
    f_level = n.level_of(forecast_2h)
    terms = n.nedocs_terms(features)
    total_pre = sum(t["points"] for t in terms)

    ed_pts = features.get("ed_pts", 0)
    ed_beds = features.get("ed_beds", 1)
    admits = features.get("admits", 0)
    hosp_beds = features.get("hosp_beds", 1)
    vents = features.get("vents", 0)
    lw = features.get("longest_wait", 0.0)
    last_w = features.get("last_wait", 0.0)
    velocity = features.get("arrival_velocity", 0.0)
    chaos = features.get("equipment_chaos_index", 0.0)
    noise = features.get("ambient_noise_db", 0.0)

    util = (ed_pts / ed_beds) if ed_beds else 0.0
    factors: list[dict] = []

    # ---- census / flow rules --------------------------------------------
    if util > 1.0:
        factors.append({
            "text": (f"ED census ({ed_pts:.0f} patients) exceeds licensed "
                     f"capacity of {ed_beds:.0f} beds — patients are being "
                     f"boarded in corridors or auxiliary areas."),
            "tag": "CENSUS", "severity": "high", "score_contribution": "major",
        })
    elif util > 0.85:
        factors.append({
            "text": (f"ED occupancy at {util * 100:.0f}% ({ed_pts:.0f} / "
                     f"{ed_beds:.0f} beds) — near capacity with little "
                     f"buffer for new arrivals."),
            "tag": "CENSUS", "severity": "medium",
            "score_contribution": "moderate",
        })

    if admits and ed_beds:
        ratio = admits / ed_beds
        if ratio > 0.30:
            factors.append({
                "text": (f"{admits:.0f} admitted patients are waiting in the ED "
                         f"— roughly {ratio * 100:.0f}% of ED bed capacity is "
                         f"blocked awaiting inpatient beds."),
                "tag": "FLOW", "severity": "high",
                "score_contribution": "major",
            })
        elif ratio > 0.15:
            factors.append({
                "text": (f"{admits:.0f} admitted patients boarded in the ED are "
                         f"consuming {ratio * 100:.0f}% of available beds."),
                "tag": "FLOW", "severity": "medium",
                "score_contribution": "moderate",
            })

    if lw > WAIT_TARGET_HRS:
        factors.append({
            "text": (f"Longest admit wait is {lw:.1f} h — above the {WAIT_TARGET_HRS:.0f} h "
                     f"target; boarding time is the strongest predictor of "
                     f"ED overcrowding."),
            "tag": "FLOW", "severity": "high" if lw > 8 else "medium",
            "score_contribution": "major",
        })
    if last_w >= LAST_WAIT_HIGH:
        factors.append({
            "text": f"Recent patients waited {last_w:.1f} h to be seen — access block is real.",
            "tag": "FLOW", "severity": "high",
            "score_contribution": "moderate",
        })
    elif last_w >= LAST_WAIT_MILD:
        factors.append({
            "text": f"Latest patient wait is {last_w:.1f} h — above the 1 h comfort band.",
            "tag": "FLOW", "severity": "low",
            "score_contribution": "moderate",
        })

    if vents >= VENT_HIGH:
        factors.append({
            "text": (f"{vents:.0f} patients on ventilators — high-acuity demand "
                     f"consuming nursing ratio and equipment."),
            "tag": "CENSUS", "severity": "high",
            "score_contribution": "moderate",
        })

    # ---- hardware rules ---------------------------------------------------
    if velocity > VELOCITY_SURGE:
        factors.append({
            "text": (f"Arrival velocity {velocity:.2f} pts/min — sustained "
                     f"inflow surge (typical 0.1–0.5)."),
            "tag": "HARDWARE", "severity": "high",
            "score_contribution": "forecast",
        })
    elif velocity > VELOCITY_BUSY:
        factors.append({
            "text": f"Arrival velocity {velocity:.2f} pts/min — above the busy threshold of {VELOCITY_BUSY:.1f}.",
            "tag": "HARDWARE", "severity": "medium",
            "score_contribution": "forecast",
        })
    if chaos > CHAOS_HIGH:
        factors.append({
            "text": (f"Movement chaos {chaos:.1f}/10 from IMU sensors — frantic "
                     f"gurney/equipment activity, typically seen during "
                     f"resuscitation or surge."),
            "tag": "HARDWARE", "severity": "high",
            "score_contribution": "forecast",
        })
    elif chaos > 3.0:
        factors.append({
            "text": f"Movement chaos elevated at {chaos:.1f}/10.",
            "tag": "HARDWARE", "severity": "low",
            "score_contribution": "forecast",
        })
    if noise > NOISE_HIGH:
        factors.append({
            "text": f"Ambient noise {noise:.0f} dB — very loud ED environment.",
            "tag": "HARDWARE", "severity": "medium",
            "score_contribution": "forecast",
        })
    elif noise > NOISE_ELEVATED:
        factors.append({
            "text": f"Ambient noise elevated at {noise:.0f} dB.",
            "tag": "HARDWARE", "severity": "low",
            "score_contribution": "forecast",
        })

    # ---- top NEDOCS additive terms (exact point share) --------------------
    if total_pre > 0:
        ranked = sorted(terms, key=lambda t: t["points"], reverse=True)[:3]
        for term in ranked:
            share = term["points"] / total_pre
            if share < 0.15:
                continue
            if any(f.get("tag") == "CENSUS" and term["key"] == "ed_occupancy"
                   for f in factors):
                continue
            factors.append({
                "text": (f"{term['label']} contributes ≈{term['points']:.0f} of "
                         f"{score + 20:.0f} pre-adjustment points "
                         f"({share * 100:.0f}%) — {term['label'].lower()} is the "
                         f"dominant pressure term."),
                "tag": "CENSUS" if term["key"] != "last_wait" else "FLOW",
                "severity": "medium",
                "score_contribution": "major",
            })

    # ---- summary sentence -------------------------------------------------
    if level["key"] == "not_busy":
        summary = (f"Score {score:.0f} — the department is operating within "
                   f"normal capacity. Current flow is sustainable.")
    elif level["key"] == "busy":
        summary = (f"Score {score:.0f} — the department is busy. Demand is "
                   f"absorbable but boarding and waits need watching.")
    elif level["key"] == "overcrowded":
        summary = (f"Score {score:.0f} — the department is overcrowded. "
                   f"Capacity is exceeded relative to inflow; boarding and "
                   f"waits are compounding.")
    else:
        summary = (f"Score {score:.0f} — CRITICAL capacity. The ED is in "
                   f"dangerously overcrowded territory; flow is severely "
                   f"impaired and access block is acute.")

    # ---- recommended actions ----------------------------------------------
    actions: list[str] = []
    if level["key"] == "critical":
        actions.append("Escalate to hospital command: activate Full Capacity Protocol.")
        actions.append("Open auxiliary treatment areas / hallway surge capacity.")
        actions.append("Begin ambulance diversion review with EMS coordination.")
    elif level["key"] == "overcrowded":
        actions.append("Convene charge-nurse huddle; activate surge protocol (level 2).")
        actions.append("Expedite inpatient bed reconciliation to clear admitted boarders.")
        actions.append("Hold elective admissions; fast-track discharge-ready patients.")
    elif level["key"] == "busy":
        actions.append("Pre-stage discharges for the next 2 h to protect buffer.")
        actions.append("Keep boarding under 4 h; notify bed management of any admit backlog.")
    else:
        actions.append("Continue routine monitoring; preserve discharge flow.")

    if admits and (admits / ed_beds if ed_beds else 0) > 0.15:
        actions.append(f"Prioritise finding inpatient beds for the {admits:.0f} admitted patients waiting in ED.")
    if lw > WAIT_TARGET_HRS:
        actions.append(f"Triage boarders with waits >{WAIT_TARGET_HRS:.0f} h for expedited inpatient placement.")
    if velocity > VELOCITY_BUSY:
        actions.append("Alert staffing: inflow is above normal — consider a second physician/nurse pod.")

    # ---- drivers ----------------------------------------------------------
    csv_typical = (csv_summary or {}).get("typical_census") or None
    drivers = _drivers(features, csv_typical)

    # ---- context note (CSV baselines) --------------------------------------
    context_note = _context_note(score, level, csv_summary)

    # ---- environment note (web + AQI/weather) ------------------------------
    environment_note = _environment_note(web)

    return {
        "score": score,
        "level": level["key"],
        "level_label": level["label"],
        "summary": summary,
        "factors": factors[:6],
        "actions": actions[:5],
        "terms": terms,
        "forecast": {
            "score_2h": forecast_2h,
            "level": f_level["key"],
            "level_label": f_level["label"],
        },
        "drivers": drivers,
        "context_note": context_note,
        "environment_note": environment_note,
    }


def _context_note(score: float, level: dict, csv_summary: dict | None) -> str:
    if not csv_summary:
        return "Historical context unavailable (CSV not loaded)."
    monthly = csv_summary.get("monthly") or {}
    global_ = csv_summary.get("global") or {}
    month = csv_summary.get("month")
    parts = []
    if monthly and month:
        med = monthly.get("median")
        if med is not None:
            rel = "above" if score > med else ("below" if score < med else "at")
            parts.append(
                f"For this hospital, {csv_summary.get('hospital_type', 'this ED')} "
                f"typical NEDOCS for month {month} is ≈{med} "
                f"(median over {monthly.get('count', '?')} historical days) — "
                f"the current {score:.0f} is {rel} that baseline."
            )
    aqi_ctx = csv_summary.get("aqi_bins") or {}
    if aqi_ctx:
        # pick the middle-most referenced bin that exists
        keys = ["<50", "50-100", "100-150", "150-200", ">200"]
        found = [k for k in keys if k in aqi_ctx]
        if found:
            k = found[len(found) // 2]
            parts.append(
                f"Under comparable air-quality days ({k} AQI), historical NEDOCS "
                f"averages {aqi_ctx[k]['mean']} ({aqi_ctx[k]['count']} days)."
            )
    if not parts:
        gmean = global_.get("mean")
        if gmean is not None:
            parts.append(
                f"Overall historical mean NEDOCS for this hospital type: {gmean} "
                f"(90th percentile {global_.get('p90', '—')})."
            )
    return " ".join(parts[:2])


def _environment_note(web: dict | None) -> str:
    if not web or not web.get("ok"):
        return "Live Delhi weather/AQI feed unavailable — environmental context not shown."
    text = web.get("weather_text", "…")
    temp = web.get("temperature_c")
    aqi = web.get("aqi")
    cat = web.get("aqi_category", "")
    base = f"Live Delhi: {temp}°C, {text}"
    if aqi is not None:
        base += f", AQI {aqi:.0f} ({cat})"
    base += "."
    if aqi is not None and aqi >= AQI_UNHEALTHY:
        base += (f" Air quality is {cat.lower()} — elevated respiratory/COPD "
                 f"inflow pressure is plausible.")
    elif temp is not None and temp >= 40:
        base += " Extreme heat increases heatstroke/heat-exhaustion presentations."
    return base
