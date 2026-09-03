"""MQTT ingestion.

Topics (JSON payloads):

  predictED/state    {hospital_type, ed_pts, ed_beds, admits, hosp_beds,
                      vents, longest_wait, last_wait, source?}
  predictED/sensor   {hospital_type, sensor_type, value}

sensor_type ∈ {ultrasound_inflow, imu_variance, mic_decibels}.
"""
from __future__ import annotations

import json
import time

import aiomqtt

from ..config import settings
from ..database import BackendDatabase, db as default_db
from ..state import LiveStore

STATE_TOPIC = "predictED/state"
SENSOR_TOPIC = "predictED/sensor"

SENSOR_TYPES = {"ultrasound_inflow", "imu_variance", "mic_decibels"}
CENSUS_KEYS = {"ed_pts", "ed_beds", "admits", "hosp_beds", "vents",
               "longest_wait", "last_wait"}


def _decode(payload: bytes) -> dict | None:
    try:
        data = json.loads(payload.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def apply_state_message(store: LiveStore, data: dict, db: BackendDatabase) -> bool:
    hospital_type = data.get("hospital_type")
    census = {k: data[k] for k in CENSUS_KEYS if k in data}
    if not hospital_type or len(census) < 2:
        return False
    source = data.get("source", "emr")
    ok = store.set_emr(hospital_type, census, source=source, db=db)
    if ok:
        store.record_trend(hospital_type)
    return ok


def apply_sensor_message(store: LiveStore, data: dict, db: BackendDatabase) -> bool:
    hospital_type = data.get("hospital_type")
    sensor_type = data.get("sensor_type")
    value = data.get("value")
    if not hospital_type or sensor_type not in SENSOR_TYPES or value is None:
        return False
    try:
        value = float(value)
    except (TypeError, ValueError):
        return False
    if store.archetype_for(hospital_type) is None:
        return False
    db.insert_hardware(sensor_type, value, hospital_type=hospital_type)
    hw = db.hardware_features(window_minutes=settings.hardware_window_min,
                              hospital_type=hospital_type)
    store.refresh_hardware(hospital_type, hw)
    return True


async def run(store: LiveStore, db: BackendDatabase) -> None:
    """Connect + consume forever. Raises on connect failure so the caller can
    fall back to demo mode."""
    client = aiomqtt.Client(
        hostname=settings.mqtt_host,
        port=settings.mqtt_port,
        identifier=f"predictED-backend-{int(time.time())}",
    )
    async with client:
        await client.subscribe([(STATE_TOPIC, 0), (SENSOR_TOPIC, 0)])
        store.mqtt.update({"connected": True, "error": None})
        store.demo["active"] = False
        async for message in client.messages:
            store.mqtt["last_message_ts"] = time.time()
            data = _decode(message.payload)
            if data is None:
                continue
            topic = message.topic.value
            if topic == STATE_TOPIC:
                apply_state_message(store, data, db)
            elif topic == SENSOR_TOPIC:
                apply_sensor_message(store, data, db)


async def try_connect_and_run(store: LiveStore, db: BackendDatabase) -> None:
    """Wrapper that marks connection errors on the store instead of crashing."""
    try:
        await run(store, db)
    except Exception as exc:  # noqa: BLE001
        store.mqtt.update({
            "connected": False,
            "error": f"{type(exc).__name__}: {exc}",
        })
        raise
