from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from core.errors import AgTechError, ErrorCode
from core.schemas import ConfidenceFlag, IrrigationDecision, PredictResponse, RecommendFromCacheRequest, RecommendRequest
from features.prediction.cache import PredictionCacheService
from features.recommendation.policy import RECOMMENDATION_LATEST_TTL_SECONDS, apply_recommendation_policy

logger = logging.getLogger("agmultida.recommendation")


@dataclass(frozen=True)
class DecisionCacheEntry:
    decision: IrrigationDecision
    zone_id: str
    created_at: datetime
    trace_id: str

    def to_payload(self) -> dict:
        return {
            "decision": self.decision.model_dump(mode="json"),
            "zone_id": self.zone_id,
            "created_at": self.created_at.isoformat(),
            "trace_id": self.trace_id,
        }

    @classmethod
    def from_payload(cls, payload: dict) -> "DecisionCacheEntry":
        return cls(
            decision=IrrigationDecision.model_validate(payload["decision"]),
            zone_id=payload["zone_id"],
            created_at=datetime.fromisoformat(payload["created_at"]),
            trace_id=payload["trace_id"],
        )


@dataclass(frozen=True)
class MemoryDecisionEntry:
    value: DecisionCacheEntry
    expires_at: datetime


class DecisionCacheService:
    def __init__(self, redis_client: object | None = None, namespace: str = "decision") -> None:
        self._redis_client = redis_client
        self._namespace = namespace
        self._entries: dict[str, MemoryDecisionEntry] = {}

    async def store_latest(self, zone_id: str, decision: IrrigationDecision, trace_id: str) -> None:
        entry = DecisionCacheEntry(decision=decision, zone_id=zone_id, created_at=datetime.now(timezone.utc), trace_id=trace_id)
        key = self.latest_key(zone_id)
        self._set_memory(key, entry)
        if self._redis_client is None:
            return
        try:
            await self._redis_client.set(key, json.dumps(entry.to_payload(), separators=(",", ":")), ex=RECOMMENDATION_LATEST_TTL_SECONDS)
        except Exception:
            return

    async def get_latest(self, zone_id: str) -> DecisionCacheEntry | None:
        key = self.latest_key(zone_id)
        memory = self._entries.get(key)
        if memory is not None and memory.expires_at > datetime.now(timezone.utc):
            return memory.value
        if memory is not None:
            self._entries.pop(key, None)
        if self._redis_client is None:
            return None
        try:
            raw = await self._redis_client.get(key)
        except Exception:
            return None
        if raw is None:
            return None
        try:
            payload = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
            entry = DecisionCacheEntry.from_payload(payload)
        except Exception:
            return None
        self._set_memory(key, entry)
        return entry

    def latest_key(self, zone_id: str) -> str:
        return f"{self._namespace}:{zone_id}:latest"

    def _set_memory(self, key: str, entry: DecisionCacheEntry) -> None:
        self._entries[key] = MemoryDecisionEntry(
            value=entry,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=RECOMMENDATION_LATEST_TTL_SECONDS),
        )


class RecommendationService:
    def __init__(self, prediction_cache: PredictionCacheService, decision_cache: DecisionCacheService, alert_service: object | None = None) -> None:
        self._prediction_cache = prediction_cache
        self._decision_cache = decision_cache
        self._alert_service = alert_service

    async def recommend_from_cache(self, req: RecommendFromCacheRequest) -> IrrigationDecision:
        prediction_entry = await self._prediction_cache.get_latest(req.zone_id)
        if prediction_entry is None:
            raise AgTechError(
                error_code=ErrorCode.PREDICTION_CACHE_MISS,
                message="Prediction cache miss",
                details={"zone_id": req.zone_id},
                status_code=409,
            )
        prediction = prediction_entry.response
        recommend_request = RecommendRequest(
            zone_id=req.zone_id,
            stress_prob=prediction.stress_prob,
            uncertainty=prediction.uncertainty,
            degraded_mode=prediction.degraded_mode,
            soil_moisture=req.soil_moisture,
            rain_forecast_3h=req.rain_forecast_3h,
            attention_weights=req.attention_weights or prediction.attention_weights,
        )
        decision = await self.recommend(recommend_request, trace_id=str(prediction.trace_id), emit_alert=False)
        await self._emit_alert(req.zone_id, decision, prediction)
        return decision

    async def recommend(self, req: RecommendRequest, trace_id: str | None = None, emit_alert: bool = True) -> IrrigationDecision:
        from decision_engine.main import evaluate_decision

        decision = evaluate_decision(req)
        decision = apply_recommendation_policy(
            decision,
            rain_forecast_3h_mm=req.rain_forecast_3h * 100,
            uncertainty=req.uncertainty,
            degraded_mode=req.degraded_mode,
        )
        trace = trace_id or str(decision.trace_id)
        await self._decision_cache.store_latest(req.zone_id, decision, trace)
        if emit_alert:
            await self._emit_alert(req.zone_id, decision, self._prediction_from_request(req))
        self._log_created(req, decision, trace)
        return decision

    async def _emit_alert(self, zone_id: str, decision: IrrigationDecision, prediction: PredictResponse | None, *, imagery_stale: bool = False) -> None:
        if self._alert_service is None:
            return
        create_for_recommendation = getattr(self._alert_service, "create_for_recommendation", None)
        if create_for_recommendation is None:
            return
        await create_for_recommendation(zone_id, decision, prediction, imagery_stale=imagery_stale)

    @staticmethod
    def _prediction_from_request(req: RecommendRequest) -> PredictResponse:
        return PredictResponse(
            zone_id=req.zone_id,
            timestamp=datetime.now(timezone.utc),
            stress_prob=req.stress_prob,
            uncertainty=req.uncertainty,
            confidence_flag=ConfidenceFlag.LOW if req.degraded_mode else ConfidenceFlag.HIGH,
            degraded_mode=req.degraded_mode,
            attention_weights=req.attention_weights,
            model_version="recommendation-derived",
            latency_ms=0.0,
        )

    def _log_created(self, req: RecommendRequest, decision: IrrigationDecision, trace_id: str) -> None:
        logger.info(
            "recommendation_created",
            extra={
                "event": "recommendation_created",
                "zone_id": req.zone_id,
                "action": decision.action.value,
                "volume_mm": decision.volume_mm,
                "reason": decision.reason,
                "uncertainty": req.uncertainty,
                "degraded_mode": req.degraded_mode,
                "trace_id": trace_id,
            },
        )
