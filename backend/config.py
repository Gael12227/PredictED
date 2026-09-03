"""Central configuration for the PredictED v2 backend.

Everything is tunable via environment variables (PREDICTED_*), with sane
defaults so `uvicorn backend.main:app` works out of the box in demo mode.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


@dataclass
class Settings:
    # --- paths -----------------------------------------------------------
    root: Path = ROOT
    model_path: Path = ROOT / "predictED_rf_model.joblib"
    db_path: Path = ROOT / "predictED_live.db"
    csv_urban: Path = ROOT / "Delhi_urban.csv"
    csv_rural: Path = ROOT / "delhi_Rural.csv"

    # --- MQTT --------------------------------------------------------------
    mqtt_host: str = os.getenv("PREDICTED_MQTT_HOST", "127.0.0.1")
    mqtt_port: int = _int_env("PREDICTED_MQTT_PORT", 1883)
    mqtt_enabled: bool = _bool_env("PREDICTED_MQTT_ENABLED", True)
    mqtt_connect_timeout: float = _float_env("PREDICTED_MQTT_CONNECT_TIMEOUT", 6.0)
    # demo mode: "auto" (fall back to built-in simulator when no broker),
    # "always", "never"
    demo_mode: str = os.getenv("PREDICTED_DEMO_MODE", "auto").strip().lower()

    # --- Open-Meteo (keyless public API for Delhi) --------------------------
    web_enabled: bool = _bool_env("PREDICTED_WEB_ENABLED", True)
    delhi_lat: float = 28.6139
    delhi_lon: float = 77.2090
    weather_url: str = (
        "https://api.open-meteo.com/v1/forecast"
        "?latitude={lat}&longitude={lon}"
        "&current=temperature_2m,apparent_temperature,relative_humidity_2m,"
        "weather_code,wind_speed_10m,is_day"
    )
    air_quality_url: str = (
        "https://air-quality-api.open-meteo.com/v1/air-quality"
        "?latitude={lat}&longitude={lon}"
        "&current=us_aqi,pm2_5,pm10"
    )
    web_interval_sec: float = _float_env("PREDICTED_WEB_INTERVAL", 300.0)

    # --- timing ---------------------------------------------------------------
    census_interval_sec: float = _float_env("PREDICTED_CENSUS_INTERVAL", 6.0)
    sensor_interval_sec: float = _float_env("PREDICTED_SENSOR_INTERVAL", 2.0)
    broadcast_interval_sec: float = _float_env("PREDICTED_BROADCAST_INTERVAL", 2.0)
    hardware_window_min: float = 15.0

    # --- trends ---------------------------------------------------------------
    trend_max_points: int = _int_env("PREDICTED_TREND_MAX", 360)  # ~36 min at 6 s
    ws_tail_points: int = 120

    # A "live" census is considered fresh for this long (seconds).
    staleness_sec: float = _float_env("PREDICTED_STALENESS_SEC", 120.0)

    # WMO weather codes → short human text (subset is enough for the demo)
    weather_text: dict = field(
        default_factory=lambda: {
            0: "Clear sky",
            1: "Mostly clear",
            2: "Partly cloudy",
            3: "Overcast",
            45: "Fog",
            48: "Icy fog",
            51: "Light drizzle",
            53: "Drizzle",
            55: "Heavy drizzle",
            61: "Light rain",
            63: "Rain",
            65: "Heavy rain",
            66: "Freezing rain",
            67: "Freezing rain",
            71: "Light snow",
            73: "Snow",
            75: "Heavy snow",
            80: "Rain showers",
            81: "Rain showers",
            82: "Violent showers",
            95: "Thunderstorm",
            96: "Thunderstorm + hail",
            99: "Thunderstorm + hail",
        }
    )

    @property
    def archetype_registry(self) -> dict:
        return {
            "urban_big": {
                "context": "urban",
                "hospital_type": "Big Urban (Delhi)",
                "bed_defaults": {"ed_beds": 60, "hosp_beds": 850},
            },
            "urban_small": {
                "context": "urban",
                "hospital_type": "Small Urban (Delhi)",
                "bed_defaults": {"ed_beds": 15, "hosp_beds": 60},
            },
            "rural_big": {
                "context": "rural",
                "hospital_type": "Big Rural (Delhi Outskirts)",
                "bed_defaults": {"ed_beds": 15, "hosp_beds": 100},
            },
            "rural_small": {
                "context": "rural",
                "hospital_type": "Small Rural (Delhi Outskirts)",
                "bed_defaults": {"ed_beds": 3, "hosp_beds": 10},
            },
        }


settings = Settings()
