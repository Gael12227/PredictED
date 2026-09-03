"""Pure NEDOCS math — ported from the original ``Data.py`` + level bands."""
from __future__ import annotations

# NEDOCS interpretative bands used by the existing PredictED apps
# (gauge steps: <60 / 60-100 / 100-140 / >=140).
LEVELS = [
    {"key": "not_busy", "label": "Not busy", "min": -1e9, "max": 60.0},
    {"key": "busy", "label": "Busy", "min": 60.0, "max": 100.0},
    {"key": "overcrowded", "label": "Overcrowded", "min": 100.0, "max": 140.0},
    {"key": "critical", "label": "Critical", "min": 140.0, "max": 1e9},
]


def calculate_nedocs(
    ed_pts, ed_beds, admits, hosp_beds, vents, longest_wait, last_wait
) -> float:
    """Standard NEDOCS score (same formula as ``Data.py``)."""
    if ed_beds <= 0 or hosp_beds <= 0:
        return 0.0
    score = (
        (85.8 * (ed_pts / ed_beds))
        + (600.0 * (admits / hosp_beds))
        + (13.4 * vents)
        + (0.93 * longest_wait)
        + (5.64 * last_wait)
        - 20.0
    )
    return max(0.0, round(float(score), 2))


def score_from_features(features: dict) -> float:
    return calculate_nedocs(
        features.get("ed_pts", 0),
        features.get("ed_beds", 1),
        features.get("admits", 0),
        features.get("hosp_beds", 1),
        features.get("vents", 0),
        features.get("longest_wait", 0),
        features.get("last_wait", 0),
    )


def level_of(score: float) -> dict:
    for band in LEVELS:
        if band["min"] <= score < band["max"]:
            return band
    return LEVELS[-1]


def level_index(score: float) -> int:
    """0..3 — ascending severity (drives colours in the UI)."""
    for i, band in enumerate(LEVELS):
        if band["min"] <= score < band["max"]:
            return i
    return len(LEVELS) - 1


def nedocs_terms(features: dict) -> list[dict]:
    """Each additive NEDOCS term's raw point contribution (before -20)."""
    ed_pts = features.get("ed_pts", 0)
    ed_beds = features.get("ed_beds", 1)
    admits = features.get("admits", 0)
    hosp_beds = features.get("hosp_beds", 1)
    vents = features.get("vents", 0)
    longest_wait = features.get("longest_wait", 0)
    last_wait = features.get("last_wait", 0)
    raw = [
        {"key": "ed_occupancy", "label": "ED occupancy", "points": 85.8 * (ed_pts / ed_beds) if ed_beds else 0.0},
        {"key": "admit_backlog", "label": "Admitted patients in ED", "points": 600.0 * (admits / hosp_beds) if hosp_beds else 0.0},
        {"key": "ventilators", "label": "Ventilator demand", "points": 13.4 * vents},
        {"key": "longest_wait", "label": "Longest admit wait", "points": 0.93 * longest_wait},
        {"key": "last_wait", "label": "Latest patient wait", "points": 5.64 * last_wait},
    ]
    for t in raw:
        t["points"] = round(t["points"], 2)
    return raw
