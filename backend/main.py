"""PredictED v2 — FastAPI application.

Run from the project root:

    .venv/Scripts/python -m uvicorn backend.main:app --port 8000

Behaviour:
  * CSV contexts are loaded once at startup.
  * The web fetcher polls Open-Meteo (Delhi weather + AQI).
  * If an MQTT broker is reachable, ``predictED/state`` and
    ``predictED/sensor`` are consumed (real EMR bridge / hardware). Otherwise
    the built-in simulator keeps all four archetypes streaming so the
    dashboard is always alive (``PREDICTED_DEMO_MODE=never`` disables that).
  * A WebSocket broadcaster pushes the combined state every 2 s.
"""
from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core import csv_loader
from .config import settings
from .database import db
from .ingestion import web_fetcher
from .ingestion.simulator import DemoEngine
from .state import store
from .routers import api as api_router
from .routers import ws as ws_router

engine = DemoEngine(store, db)


async def _broker_reachable(timeout: float) -> bool:
    import aiomqtt

    try:
        async with aiomqtt.Client(
            hostname=settings.mqtt_host,
            port=settings.mqtt_port,
            identifier=f"predictED-probe-{int(time.time())}",
        ) as client:
            if hasattr(client, "ping"):
                await client.ping()
        return True
    except Exception:  # noqa: BLE001
        return False


async def _mqtt_supervisor() -> None:
    """Run the listener; if the connection dies, fall back to the simulator."""
    from .ingestion.mqtt_listener import try_connect_and_run

    while True:
        try:
            await try_connect_and_run(store, db)
        except Exception as exc:  # noqa: BLE001
            store.mqtt.update({"connected": False,
                               "error": f"{type(exc).__name__}: {exc}"})
            if settings.demo_mode in ("auto", "always"):
                if not engine.running():
                    await engine.start()
            # reconnect attempts until a broker appears
            await asyncio.sleep(5.0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    csv_loader.load()
    app.state.ws_clients = set()

    tasks = [asyncio.create_task(web_fetcher.run(store)),
             asyncio.create_task(ws_router.broadcast_loop(app))]

    mqtt_ok = False
    if settings.mqtt_enabled and settings.demo_mode != "always":
        mqtt_ok = await _broker_reachable(settings.mqtt_connect_timeout)
        if mqtt_ok:
            store.mqtt["error"] = None
            tasks.append(asyncio.create_task(_mqtt_supervisor()))
        else:
            store.mqtt.update({"connected": False,
                               "error": "No MQTT broker reachable "
                                        f"({settings.mqtt_host}:{settings.mqtt_port})."})

    if not mqtt_ok and settings.demo_mode in ("auto", "always"):
        await engine.start()

    yield

    for t in tasks:
        t.cancel()
    await engine.stop()


app = FastAPI(title="PredictED Intelligence API", version="2.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router.router)
app.include_router(ws_router.router)


@app.get("/")
def root():
    return {"service": "PredictED v2",
            "docs": "/docs",
            "state": "/api/state",
            "websocket": "/ws/dashboard",
            "started_at": store.started_at}
