"""Realistic ED stream generator for PredictED.

Two modes:
  * in-process demo engine (default) — used by the FastAPI app when no MQTT
    broker is reachable, keeps every archetype streaming into the live store.
  * `python -m backend.ingestion.simulator --mqtt` — publishes the same
    streams to an external broker (predictED/state, predictED/sensor) for
    testing the real MQTT path.

Distributions mirror the domain notes in the original codebase: quiet nights,
evening surges, weekend bumps (Data.py), occasional "bus crash" surges with
frantic IMU chaos and high arrival velocity (update_dataset.py).
"""
from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime

import numpy as np

from ..config import settings
from ..database import (
    SENSOR_IMU, SENSOR_MIC, SENSOR_ULTRASOUND, BackendDatabase, db as default_db,
)
from ..state import LiveStore, store as default_store
from .mqtt_listener import SENSOR_TOPIC, STATE_TOPIC

# base parameters per archetype (arrivals/min, census scale)
ARCH_PARAMS = {
    "urban_big":   {"arrivals_per_min": 0.9, "pts": 46.0, "admits": 9.0, "vents": 2.2},
    "urban_small": {"arrivals_per_min": 0.30, "pts": 10.0, "admits": 1.6, "vents": 0.3},
    "rural_big":   {"arrivals_per_min": 0.22, "pts": 12.0, "admits": 2.6, "vents": 0.7},
    "rural_small": {"arrivals_per_min": 0.09, "pts": 5.0, "admits": 0.7, "vents": 0.1},
}

# gentle random-walk on census so the trend chart shows realistic drift
CENSUS_SMOOTHING = 0.28


def _hour_factor() -> float:
    h = datetime.now().hour
    factor = 1.0
    if 17 <= h <= 22:
        factor += 0.35
    elif h >= 23 or h <= 5:
        factor -= 0.35
    elif 12 <= h <= 15:
        factor += 0.15
    if datetime.now().weekday() >= 5:  # weekend surge
        factor += 0.18
    return factor


class ArchetypeSim:
    """Drives one hospital archetype's census + sensor streams."""

    def __init__(self, key: str, seed: int):
        reg = settings.archetype_registry[key]
        self.key = key
        self.context = reg["context"]
        self.hospital_type = reg["hospital_type"]
        self.bed_defaults = reg["bed_defaults"]
        p = ARCH_PARAMS[key]
        self.arrivals_per_min = p["arrivals_per_min"]
        self.pts_target = p["pts"]
        self.admits_target = p["admits"]
        self.rng = np.random.default_rng(seed)
        self.ed_pts = float(p["pts"])
        self.admits = float(p["admits"])
        self.vents = float(p["vents"])
        self.chaos = 1.2
        self.surge_until = 0.0
        self.next_surge_at = time.time() + self.rng.uniform(120, 260)

    # ------------------------------------------------------------- helpers
    @property
    def ed_beds(self) -> float:
        return float(self.bed_defaults["ed_beds"])

    @property
    def hosp_beds(self) -> float:
        return float(self.bed_defaults["hosp_beds"])

    def _maybe_surge(self) -> None:
        now = time.time()
        if now >= self.next_surge_at:
            self.surge_until = now + self.rng.uniform(70, 150)
            self.next_surge_at = now + self.rng.uniform(240, 480)

    def _surging(self) -> bool:
        return time.time() < self.surge_until

    def arrivals_per_minute(self) -> float:
        base = self.arrivals_per_min * _hour_factor()
        return base * 2.6 if self._surging() else base

    def chaos_target(self) -> float:
        if self._surging():
            return float(self.rng.uniform(6.5, 9.2))
        if self.rng.random() < 0.10:
            return float(self.rng.uniform(3.0, 5.0))
        return float(self.rng.uniform(0.4, 2.6))

    # ------------------------------------------------------------- census
    def census_snapshot(self) -> dict:
        self._maybe_surge()
        factor = _hour_factor()
        surge = 1.35 if self._surging() else 1.0
        target_pts = min(self.pts_target * factor * surge, self.ed_beds * 1.5)
        target_admits = min(self.admits_target * factor * surge,
                            self.ed_pts * 0.55)

        self.ed_pts += (target_pts - self.ed_pts) * CENSUS_SMOOTHING
        self.admits += (target_admits - self.admits) * CENSUS_SMOOTHING
        self.ed_pts += float(self.rng.normal(0, 1.6))
        self.admits += float(self.rng.normal(0, 0.6))
        self.ed_pts = float(np.clip(self.ed_pts, self.ed_beds * 0.12, self.ed_beds * 1.6))
        self.admits = float(np.clip(self.admits, 0.0, self.ed_pts * 0.6))
        self.vents = max(0.0, float(np.clip(
            self.vents + (target_admits * 0.15 - self.vents) * 0.15
            + self.rng.normal(0, 0.25), 0.0, 12.0)))

        longest = float(np.clip(
            self.admits * 0.72 + self.rng.uniform(0.0, 2.8)
            + (6.0 if self._surging() else 0.0), 0.2, 22.0))
        last = float(np.clip(
            0.35 + (self.ed_pts / self.ed_beds) * 1.4 + self.rng.uniform(0.0, 1.4),
            0.1, 8.0))

        return {
            "ed_pts": round(self.ed_pts),
            "ed_beds": self.ed_beds,
            "admits": round(self.admits),
            "hosp_beds": self.hosp_beds,
            "vents": round(self.vents, 1),
            "longest_wait": round(longest, 2),
            "last_wait": round(last, 2),
        }

    # ------------------------------------------------------------- sensors
    def sensor_values(self) -> tuple[float, float]:
        """(imu variance row, mic decibels row) around the chaos target."""
        target = self.chaos_target()
        self.chaos += (target - self.chaos) * 0.2
        imu = float(np.clip(self.chaos + self.rng.normal(0, 0.5), 0.0, 10.0))
        mic = float(np.clip(46 + self.chaos * 3.4 + self.rng.normal(0, 5.0), 32.0, 102.0))
        return round(imu, 2), round(mic, 1)


def warm_up(db: BackendDatabase, key: str) -> None:
    """Backfill ~15 min of plausible telemetry so windows show life instantly."""
    sim = ArchetypeSim(key, seed=1000 + (sum(ord(c) for c in key) % 900))
    now = time.time()
    step_min = 1.0 / 3.0  # 20 s
    n_steps = int(settings.hardware_window_min / step_min)
    rate = sim.arrivals_per_min * step_min
    with db._write_lock, db._connect() as conn:
        for i in range(n_steps):
            ts = datetime.utcfromtimestamp(
                now - (n_steps - i) * step_min * 60.0
            ).strftime("%Y-%m-%d %H:%M:%S")
            for _ in range(int(sim.rng.poisson(rate))):
                conn.execute(
                    "INSERT INTO hardware_logs (timestamp, sensor_type, value, hospital_type) "
                    "VALUES (?, ?, 1.0, ?)",
                    (ts, SENSOR_ULTRASOUND, sim.hospital_type),
                )
            if i % 3 == 0:
                imu, mic = sim.sensor_values()
                conn.execute(
                    "INSERT INTO hardware_logs (timestamp, sensor_type, value, hospital_type) "
                    "VALUES (?, ?, ?, ?)",
                    (ts, SENSOR_IMU, imu, sim.hospital_type),
                )
                conn.execute(
                    "INSERT INTO hardware_logs (timestamp, sensor_type, value, hospital_type) "
                    "VALUES (?, ?, ?, ?)",
                    (ts, SENSOR_MIC, mic, sim.hospital_type),
                )
        conn.commit()


async def run_stream(store: LiveStore, db: BackendDatabase, key: str,
                     interval: float) -> None:
    """Per-archetype demo stream task (sensors every tick, census every N ticks)."""
    sim = ArchetypeSim(key, seed=sum(ord(c) for c in key))
    tick = 0
    census_every = max(1, int(round(settings.census_interval_sec / interval)))
    while True:
        dt_min = interval / 60.0
        for _ in range(int(sim.rng.poisson(sim.arrivals_per_minute() * dt_min))):
            db.insert_hardware(SENSOR_ULTRASOUND, 1.0, hospital_type=sim.hospital_type)
        imu, mic = sim.sensor_values()
        db.insert_hardware(SENSOR_IMU, imu, hospital_type=sim.hospital_type)
        db.insert_hardware(SENSOR_MIC, mic, hospital_type=sim.hospital_type)

        hw = db.hardware_features(window_minutes=settings.hardware_window_min,
                                  hospital_type=sim.hospital_type)
        store.refresh_hardware(sim.hospital_type, hw)

        if tick % census_every == 0:
            census = sim.census_snapshot()
            store.set_emr(sim.hospital_type, census, source="simulator", db=db)
            store.record_trend(sim.hospital_type)
        tick += 1
        await asyncio.sleep(interval)


class DemoEngine:
    def __init__(self, store: LiveStore | None = None, db: BackendDatabase | None = None):
        self.store = store or default_store
        self.db = db or default_db
        self._tasks: list[asyncio.Task] = []
        self._warmed: set[str] = set()

    async def start(self) -> None:
        if self._tasks:
            return
        for key in settings.archetype_registry:
            if key not in self._warmed:
                try:
                    warm_up(self.db, key)
                except Exception:  # noqa: BLE001 - warm-up is best-effort
                    pass
                self._warmed.add(key)
        interval = settings.sensor_interval_sec
        for key in settings.archetype_registry:
            self._tasks.append(asyncio.create_task(
                run_stream(self.store, self.db, key, interval)))
        self.store.demo["active"] = True
        self.store.demo["note"] = (
            "Built-in simulator active (no MQTT broker connected). "
            "Streams mimic EMR census + edge-sensor telemetry for all four "
            "Delhi archetypes."
        )

    async def stop(self) -> None:
        for t in self._tasks:
            t.cancel()
        self._tasks = []
        self.store.demo["active"] = False

    def running(self) -> bool:
        return bool(self._tasks)


# ---------------------------------------------------------------------------
# Standalone MQTT publisher (python -m backend.ingestion.simulator --mqtt)
# ---------------------------------------------------------------------------
async def _publish_mqtt(host: str, port: int) -> None:
    import aiomqtt

    async with aiomqtt.Client(hostname=host, port=port,
                              identifier=f"predictED-sim-{int(time.time())}") as client:
        print(f"Publishing to mqtt://{host}:{port} (Ctrl+C to stop)")
        sims = {k: ArchetypeSim(k, seed=sum(ord(c) for c in k))
                for k in settings.archetype_registry}
        last_census = {}
        while True:
            for key, sim in sims.items():
                sim._maybe_surge()
                imu, mic = sim.sensor_values()
                if sim.rng.random() < sim.arrivals_per_minute() * (2 / 60):
                    await client.publish(SENSOR_TOPIC, payload=json.dumps({
                        "hospital_type": sim.hospital_type,
                        "sensor_type": SENSOR_ULTRASOUND, "value": 1.0,
                    }).encode())
                await client.publish(SENSOR_TOPIC, payload=json.dumps({
                    "hospital_type": sim.hospital_type,
                    "sensor_type": SENSOR_IMU, "value": imu,
                }).encode())
                await client.publish(SENSOR_TOPIC, payload=json.dumps({
                    "hospital_type": sim.hospital_type,
                    "sensor_type": SENSOR_MIC, "value": mic,
                }).encode())
                now = time.time()
                if now - last_census.get(key, 0) >= 6:
                    last_census[key] = now
                    await client.publish(STATE_TOPIC, payload=json.dumps({
                        "hospital_type": sim.hospital_type, "source": "emr",
                        **sim.census_snapshot(),
                    }).encode())
            await asyncio.sleep(2)


def main() -> None:
    import sys

    if "--mqtt" in sys.argv:
        asyncio.run(_publish_mqtt(settings.mqtt_host, settings.mqtt_port))
    else:
        async def _demo_forever():
            engine = DemoEngine()
            await engine.start()
            while True:
                await asyncio.sleep(3600)

        print("Running in-process demo engine (no broker). Use --mqtt to publish.")
        asyncio.run(_demo_forever())


if __name__ == "__main__":
    main()
