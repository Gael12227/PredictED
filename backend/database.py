"""SQLite persistence for PredictED v2.

Keeps the original ``hardware_logs`` schema (ESP32/NodeMCU/RPi telemetry)
plus an added ``hospital_type`` column that scopes windows per archetype, and
adds an ``emr_snapshots`` table for full ED-census snapshots arriving from
the MQTT ``predictED/state`` topic (EMR bridge / simulator / manual override).
"""
from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timedelta

from .config import settings

# Column names of the census snapshot table (subset of the 9 model features
# that describe the clinical census; the hardware pair is derived from logs).
CENSUS_COLUMNS = [
    "ed_pts", "ed_beds", "admits", "hosp_beds", "vents",
    "longest_wait", "last_wait",
]

# sensor_type values understood by the feature engine
SENSOR_ULTRASOUND = "ultrasound_inflow"
SENSOR_IMU = "imu_variance"
SENSOR_MIC = "mic_decibels"


class BackendDatabase:
    """Thin wrapper over the PredictED sqlite database (thread-safe writes)."""

    def __init__(self, db_path=None):
        self.db_path = str(db_path or settings.db_path)
        self._write_lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._write_lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS hardware_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    sensor_type TEXT,
                    value REAL
                )
                """
            )
            # scope rows to a hospital archetype (backwards-compatible)
            cols = {r[1] for r in conn.execute("PRAGMA table_info(hardware_logs)")}
            if "hospital_type" not in cols:
                conn.execute(
                    "ALTER TABLE hardware_logs ADD COLUMN hospital_type TEXT DEFAULT ''"
                )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS emr_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    hospital_type TEXT,
                    ed_pts REAL, ed_beds REAL, admits REAL, hosp_beds REAL,
                    vents REAL, longest_wait REAL, last_wait REAL,
                    source TEXT DEFAULT 'emr'
                )
                """
            )
            conn.commit()

    # ------------------------------------------------------------------ writes
    def insert_hardware(self, sensor_type: str, value: float,
                        hospital_type: str | None = None) -> None:
        with self._write_lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO hardware_logs (sensor_type, value, hospital_type) "
                "VALUES (?, ?, ?)",
                (sensor_type, float(value), hospital_type or ""),
            )
            conn.commit()

    def insert_emr(self, hospital_type: str, census: dict, source: str = "emr") -> None:
        cols = ", ".join(CENSUS_COLUMNS)
        marks = ", ".join("?" for _ in CENSUS_COLUMNS)
        values = [float(census.get(c, 0.0)) for c in CENSUS_COLUMNS]
        with self._write_lock, self._connect() as conn:
            conn.execute(
                f"INSERT INTO emr_snapshots "
                f"(hospital_type, source, {cols}) VALUES (?, ?, {marks})",
                [hospital_type, source, *values],
            )
            conn.commit()

    # ------------------------------------------------------------------ reads
    def hardware_features(self, window_minutes: float | None = None,
                          hospital_type: str | None = None) -> dict:
        """Rolling hardware-derived features over the last window.

        arrival_velocity = ultrasound triggers per minute in the window
        equipment_chaos_index = avg IMU variance over the window (0-10 scale)
        ambient_noise_db = avg mic level over the window
        """
        window_minutes = window_minutes or settings.hardware_window_min
        since = (datetime.utcnow() - timedelta(minutes=window_minutes)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        scope = " AND hospital_type = ?" if hospital_type else ""
        args_scope = (hospital_type,) if hospital_type else ()
        out = {}

        def _agg(col: str, sensor: str):
            with self._connect() as conn:
                row = conn.execute(
                    f"SELECT {col}(value) AS v FROM hardware_logs "
                    "WHERE sensor_type = ? AND timestamp >= ?" + scope,
                    (sensor, since, *args_scope),
                ).fetchone()
            return row["v"] if row is not None else None

        count = _agg("COUNT", SENSOR_ULTRASOUND) or 0.0
        chaos = _agg("AVG", SENSOR_IMU)
        noise = _agg("AVG", SENSOR_MIC)
        return {
            "arrival_velocity": round(float(count) / window_minutes, 3),
            "equipment_chaos_index": round(float(chaos) if chaos else 0.0, 2),
            "ambient_noise_db": round(float(noise) if noise else 0.0, 1),
            "window_minutes": window_minutes,
        }

    def recent_emr(self, hospital_type: str, limit: int = 3) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM emr_snapshots WHERE hospital_type = ? "
                "ORDER BY id DESC LIMIT ?",
                (hospital_type, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def count_rows(self) -> dict:
        with self._connect() as conn:
            hw = conn.execute("SELECT COUNT(*) AS c FROM hardware_logs").fetchone()["c"]
            emr = conn.execute("SELECT COUNT(*) AS c FROM emr_snapshots").fetchone()["c"]
        return {"hardware_logs": hw, "emr_snapshots": emr}


# module-level singleton
db = BackendDatabase()
