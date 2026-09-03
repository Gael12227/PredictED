"""Open-Meteo fetcher — live Delhi weather + AQI (keyless public API).

Runs as an asyncio task; failures are recorded on the store and retried on the
next cycle so the dashboard degrades gracefully (no crashes offline).
"""
from __future__ import annotations

import asyncio
import time

import httpx

from ..config import settings


def _aqi_category(us_aqi: float | None) -> str:
    if us_aqi is None:
        return "n/a"
    if us_aqi < 50:
        return "Good"
    if us_aqi < 100:
        return "Moderate"
    if us_aqi < 150:
        return "Unhealthy for sensitive groups"
    if us_aqi < 200:
        return "Unhealthy"
    if us_aqi < 300:
        return "Very unhealthy"
    return "Hazardous"


async def _fetch_json(client: httpx.AsyncClient, url: str) -> dict:
    resp = await client.get(url, timeout=10.0)
    resp.raise_for_status()
    return resp.json()


async def fetch_once() -> dict:
    """Returns the web context dict (or a failure dict)."""
    lat, lon = settings.delhi_lat, settings.delhi_lon
    weather_url = settings.weather_url.format(lat=lat, lon=lon)
    air_url = settings.air_quality_url.format(lat=lat, lon=lon)
    try:
        async with httpx.AsyncClient() as client:
            weather, air = await asyncio.gather(
                _fetch_json(client, weather_url),
                _fetch_json(client, air_url),
            )
        cur = weather.get("current", {})
        air_cur = air.get("current", {})
        wcode = cur.get("weather_code")
        return {
            "ok": True,
            "error": None,
            "fetched_at": time.time(),
            "temperature_c": cur.get("temperature_2m"),
            "apparent_temperature_c": cur.get("apparent_temperature"),
            "humidity_pct": cur.get("relative_humidity_2m"),
            "wind_kmh": cur.get("wind_speed_10m"),
            "weather_code": wcode,
            "weather_text": settings.weather_text.get(wcode, "Conditions vary"),
            "aqi": air_cur.get("us_aqi"),
            "aqi_category": _aqi_category(air_cur.get("us_aqi")),
            "pm2_5": air_cur.get("pm2_5"),
            "pm10": air_cur.get("pm10"),
        }
    except Exception as exc:  # noqa: BLE001 - network/API errors must not kill the app
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}",
                "fetched_at": time.time()}


async def run(store) -> None:
    """Background loop — fetch, store, sleep."""
    if not settings.web_enabled:
        store.web = {"ok": False, "error": "web fetching disabled",
                     "fetched_at": None}
        return
    while True:
        result = await fetch_once()
        store.web = result
        await asyncio.sleep(settings.web_interval_sec)
