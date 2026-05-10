from __future__ import annotations

from fastapi import FastAPI

from backend.features.websocket.schemas import RealtimeEvent


async def publish_realtime_event(application: FastAPI, event: str, zone_id: str, payload: dict) -> None:
    message = RealtimeEvent(event=event, payload=payload).model_dump_json()
    redis_client = getattr(application.state.prediction_cache, "_redis_client", None)
    if redis_client is not None:
        await redis_client.publish(f"ws:zone:{zone_id}", message)
    await application.state.websocket_manager.send_zone(zone_id, RealtimeEvent(event=event, payload=payload))
