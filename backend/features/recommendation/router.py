from __future__ import annotations

from fastapi import APIRouter, Request

from backend.core.schemas import IrrigationDecision, RecommendFromCacheRequest, RecommendRequest
from backend.features.websocket.publish import publish_realtime_event

router = APIRouter(tags=["recommendation"])


@router.post("/v1/recommend", response_model=IrrigationDecision)
async def recommend(req: RecommendRequest, request: Request):
    if request.app.state.gateway_mode == "stub":
        decision = request.app.state.decision_client.recommend(req)
    else:
        decision = await request.app.state.recommendation_service.recommend(req)
    request.app.state.zone_status_cache.invalidate(req.zone_id)
    await request.app.state.zone_status_aggregate.invalidate(req.zone_id)
    await publish_realtime_event(request.app, "recommendation_created", req.zone_id, {"zone_id": req.zone_id, "action": decision.action.value})
    return decision


@router.post("/v1/recommend/from-cache", response_model=IrrigationDecision)
async def recommend_from_cache(req: RecommendFromCacheRequest, request: Request):
    decision = await request.app.state.recommendation_service.recommend_from_cache(req)
    request.app.state.zone_status_cache.invalidate(req.zone_id)
    await request.app.state.zone_status_aggregate.invalidate(req.zone_id)
    return decision
