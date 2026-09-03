"""Wrapper around the trained Random Forest (predictED_rf_model.joblib).

The model forecasts NEDOCS ~2 hours ahead from 9 features. Feature order must
match training exactly.
"""
from __future__ import annotations

import threading

import joblib
import numpy as np

from ..config import settings

# Order the model was trained on (train_model.py) — keep identical.
MODEL_FEATURES = [
    "ed_pts", "ed_beds", "admits", "hosp_beds", "vents",
    "longest_wait", "last_wait", "arrival_velocity", "equipment_chaos_index",
]

CENSUS_FEATURES = MODEL_FEATURES[:7]
HARDWARE_FEATURES = MODEL_FEATURES[7:]

FEATURE_META = {
    "ed_pts": {
        "label": "ED patients",
        "unit": "pts",
        "step": 1,
        "tag": "CENSUS",
        "help": "Patients currently in the Emergency Department",
    },
    "ed_beds": {
        "label": "ED beds",
        "unit": "beds",
        "step": 1,
        "tag": "CENSUS",
        "help": "Licensed ED treatment beds",
    },
    "admits": {
        "label": "Admitted patients waiting",
        "unit": "pts",
        "step": 1,
        "tag": "CENSUS",
        "help": "Admitted patients boarded in the ED awaiting an inpatient bed",
    },
    "hosp_beds": {
        "label": "Hospital beds",
        "unit": "beds",
        "step": 1,
        "tag": "CENSUS",
        "help": "Total inpatient hospital bed capacity",
    },
    "vents": {
        "label": "Patients on ventilators",
        "unit": "pts",
        "step": 1,
        "tag": "CENSUS",
        "help": "ED patients requiring ventilatory support",
    },
    "longest_wait": {
        "label": "Longest admit wait",
        "unit": "h",
        "step": 0.25,
        "tag": "FLOW",
        "help": "Longest wait (hours) for an admitted ED patient",
    },
    "last_wait": {
        "label": "Last patient wait",
        "unit": "h",
        "step": 0.25,
        "tag": "FLOW",
        "help": "Wait (hours) of the most recently seen ED patient",
    },
    "arrival_velocity": {
        "label": "Arrival velocity",
        "unit": "pts/min",
        "step": 0.05,
        "tag": "HARDWARE",
        "help": "Ultrasound-inflow triggers per minute (15-min window)",
    },
    "equipment_chaos_index": {
        "label": "Movement chaos (IMU)",
        "unit": "0-10",
        "step": 0.5,
        "tag": "HARDWARE",
        "help": "Equipment/patient movement intensity from IMU variance",
    },
}

# Typical normal centres for each feature — used to turn feature-importance
# into "how far above normal is this driver right now".
NORMAL_CENTERS = {
    "ed_pts": 28.0,
    "ed_beds": 40.0,
    "admits": 8.0,
    "hosp_beds": 350.0,
    "vents": 2.0,
    "longest_wait": 2.5,
    "last_wait": 1.0,
    "arrival_velocity": 0.25,
    "equipment_chaos_index": 1.5,
}


class _ModelHolder:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._model = None
        self._feature_names = None

    def load(self):
        with self._lock:
            if self._model is None:
                self._model = joblib.load(str(settings.model_path))
                names = getattr(self._model, "feature_names_in_", None)
                self._feature_names = (
                    list(names) if names is not None else list(MODEL_FEATURES)
                )
            return self._model

    @property
    def model(self):
        return self.load()

    def predict_2h(self, features: dict) -> float:
        """Forecast NEDOCS ~2 h ahead for the given 9-feature census."""
        model = self.load()
        import pandas as pd

        row = {f: float(features.get(f, 0.0)) for f in MODEL_FEATURES}
        # use a DataFrame so sklearn is happy with feature names
        frame = pd.DataFrame([row], columns=MODEL_FEATURES)
        pred = float(np.clip(model.predict(frame)[0], 0.0, 250.0))
        return round(pred, 2)

    def importances(self) -> dict[str, float]:
        model = self.load()
        names = getattr(model, "feature_names_in_", None)
        if names is None:
            names = MODEL_FEATURES
        return dict(zip(list(names), model.feature_importances_))


holder = _ModelHolder()


def predict_2h(features: dict) -> float:
    return holder.predict_2h(features)


def feature_importances() -> dict[str, float]:
    return holder.importances()


def array_from_features(features: dict) -> np.ndarray:
    return np.array([[float(features.get(f, 0.0)) for f in MODEL_FEATURES]])
