from __future__ import annotations

from fastapi import APIRouter, Request

from core.schemas import IrrigationDecision, RecommendFromCacheRequest

router = APIRouter(tags=["recommendation"])


@router.post("/v1/recommend/from-cache", response_model=IrrigationDecision)
async def recommend_from_cache(req: RecommendFromCacheRequest, request: Request):
    decision = await request.app.state.recommendation_service.recommend_from_cache(req)
    request.app.state.zone_status_cache.invalidate(req.zone_id)
    return decision
