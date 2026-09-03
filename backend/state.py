"""Thread-safe live state for all hospital archetypes.

Holds the most recent EMR census, the rolling hardware-derived features, any
manual overrides, trend rings, and global source status. Everything needed to
build dashboard payloads lives here; the payload/explanation builders live in
``payload.py`` (pure reads), while ingestion modules mutate via the methods
below.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field

from .config import settings
from .core import nedocs as n
from .core.predictor import CENSUS_FEATURES, HARDWARE_FEATURES, MODEL_FEATURES, predict_2h


@dataclass
class ArchetypeState:
    key: str
    context: str
    hospital_type: str
    # source values (never overwritten by overrides)
    census: dict = field(default_factory=dict)      # feats -> (value, ts)
    hardware: dict = field(default_factory=dict)    # feats -> (value, ts)
    # manual override: feature -> value (applies until cleared)
    override: dict = field(default_factory=dict)
    override_ts: float | None = None
    override_source: str | None = None
    census_source: str = "default"                  # default | emr | simulator
    trend: deque = field(default_factory=lambda: deque(maxlen=settings.trend_max_points))
    last_census_ts: float = 0.0
    last_sensor_ts: float = 0.0

    def effective(self) -> dict:
        feats = {}
        for f in MODEL_FEATURES:
            if f in self.override:
                feats[f] = self.override[f]
            elif f in self.census:
                feats[f] = self.census[f][0]
            elif f in self.hardware:
                feats[f] = self.hardware[f][0]
            else:
                feats[f] = 0.0
        # ambient noise is shown read-only (drives explainer rules only)
        if "ambient_noise_db" in self.override:
            feats["ambient_noise_db"] = self.override["ambient_noise_db"]
        elif "ambient_noise_db" in self.hardware:
            feats["ambient_noise_db"] = self.hardware["ambient_noise_db"][0]
        return feats

    def staleness_s(self) -> dict:
        now = time.time()
        out = {}
        for f in MODEL_FEATURES:
            ts = None
            if f in self.census:
                ts = self.census[f][1]
            elif f in self.hardware:
                ts = self.hardware[f][1]
            if f in self.override:
                ts = self.override_ts
            out[f] = round(now - ts, 1) if ts else None
        return out


class LiveStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.registry: dict[str, ArchetypeState] = {}
        for key, info in settings.archetype_registry.items():
            state = ArchetypeState(
                key=key,
                context=info["context"],
                hospital_type=info["hospital_type"],
            )
            # sensible static defaults so the model is never fed zeros
            beds = info["bed_defaults"]
            census_defaults = {
                "ed_pts": 22.0 if info["context"] == "urban" else 12.0,
                "ed_beds": beds["ed_beds"],
                "admits": 5.0 if info["context"] == "urban" else 2.0,
                "hosp_beds": beds["hosp_beds"],
                "vents": 1.0,
                "longest_wait": 2.5,
                "last_wait": 0.9,
            }
            now = time.time()
            for f, v in census_defaults.items():
                state.census[f] = (float(v), now)
            state.hardware["arrival_velocity"] = (0.15, now)
            state.hardware["equipment_chaos_index"] = (0.6, now)
            state.last_census_ts = now
            self.registry[key] = state

        # source / web / mqtt status
        self.mqtt: dict = {"enabled": settings.mqtt_enabled, "connected": False,
                           "last_message_ts": None, "error": None}
        self.demo: dict = {"active": False, "mode": settings.demo_mode,
                           "note": None}
        self.web: dict = {"ok": False, "fetched_at": None, "error": None}
        self.started_at: float = time.time()

    # ------------------------------------------------------------ mutations
    def archetype_for(self, hospital_type: str) -> ArchetypeState | None:
        with self._lock:
            for st in self.registry.values():
                if st.hospital_type == hospital_type:
                    return st
        return None

    def set_emr(self, hospital_type: str, census: dict, source: str = "emr",
                db=None) -> bool:
        """New census snapshot from the EMR bridge/simulator. Returns False if
        the hospital_type is unknown. Persists to sqlite when ``db`` given."""
        st = self.archetype_for(hospital_type)
        if st is None:
            return False
        now = time.time()
        with self._lock:
            st.census_source = source
            for f in CENSUS_FEATURES:
                if f in census and census[f] is not None:
                    st.census[f] = (float(census[f]), now)
            st.last_census_ts = now
        if db is not None:
            db.insert_emr(hospital_type, census, source)
        return True

    def refresh_hardware(self, hospital_type: str, hw: dict) -> bool:
        """Update hardware-derived features from a fresh DB window."""
        st = self.archetype_for(hospital_type)
        if st is None:
            return False
        now = time.time()
        with self._lock:
            for f in HARDWARE_FEATURES:
                if f in hw and hw[f] is not None:
                    st.hardware[f] = (float(hw[f]), now)
            st.hardware["ambient_noise_db"] = (float(hw.get("ambient_noise_db", 0.0)), now)
            st.last_sensor_ts = now
        return True

    def set_override(self, hospital_type: str, features: dict) -> bool:
        st = self.archetype_for(hospital_type)
        if st is None:
            return False
        now = time.time()
        with self._lock:
            for f in MODEL_FEATURES:
                if f in features and features[f] is not None:
                    st.override[f] = float(features[f])
            st.override_ts = now
            st.override_source = "dashboard"
        return True

    def clear_override(self, hospital_type: str) -> bool:
        st = self.archetype_for(hospital_type)
        if st is None:
            return False
        with self._lock:
            st.override.clear()
            st.override_ts = None
            st.override_source = None
        return True

    def record_trend(self, hospital_type: str) -> None:
        """Append one (time, current, forecast) point from effective features."""
        st = self.archetype_for(hospital_type)
        if st is None:
            return
        feats = st.effective()
        try:
            score_now = n.score_from_features(feats)
            score_2h = predict_2h(feats)
        except Exception:
            return
        with self._lock:
            st.trend.append({"t": time.time(), "now": score_now, "f2h": score_2h})

    # ------------------------------------------------------------ reads
    def archetypes(self, context: str) -> list[ArchetypeState]:
        with self._lock:
            return [s for s in self.registry.values() if s.context == context]

    def snapshot(self) -> dict:
        """Small diagnostic snapshot (health endpoint)."""
        with self._lock:
            return {
                "started_at": self.started_at,
                "mqtt": dict(self.mqtt),
                "demo": dict(self.demo),
                "web": dict(self.web),
                "archetypes": [
                    {
                        "key": s.key,
                        "hospital_type": s.hospital_type,
                        "overridden": bool(s.override),
                        "trend_points": len(s.trend),
                        "last_census_ts": s.last_census_ts,
                    }
                    for s in self.registry.values()
                ],
            }


store = LiveStore()
