"""WebSocket endpoint + broadcaster.

The broadcaster task (started in ``main.lifespan``) pushes the full payload
for both contexts to every connected client every ``broadcast_interval_sec``,
so the React UI simply renders whatever arrives — no per-client polling.
"""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .. import payload as payload_mod
from ..config import settings

router = APIRouter()


def _clients(app) -> set:
    return app.state.ws_clients


@router.websocket("/ws/dashboard")
async def dashboard_socket(websocket: WebSocket):
    app = websocket.app
    await websocket.accept()
    _clients(app).add(websocket)
    try:
        # send an immediate snapshot so the UI isn't blank on connect
        await websocket.send_text(json.dumps(payload_mod.full_payload()))
        while True:
            # client ping/keepalive; raises on disconnect
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text(json.dumps({"pong": True}))
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001
        pass
    finally:
        _clients(app).discard(websocket)


async def broadcast_loop(app) -> None:
    """Background task: push a fresh payload to every connected socket."""
    while True:
        await asyncio.sleep(settings.broadcast_interval_sec)
        try:
            payload = payload_mod.full_payload()
            text = json.dumps(payload)
        except Exception:  # noqa: BLE001 - a bad payload must not kill the loop
            continue
        dead = []
        for ws in list(_clients(app)):
            try:
                await ws.send_text(text)
            except Exception:  # noqa: BLE001
                dead.append(ws)
        for ws in dead:
            _clients(app).discard(ws)
