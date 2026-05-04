"""Decision Engine client abstraction with stub/live modes.

LiveDecisionClient calls evaluate_decision() directly (in-process)
because it is a pure function with zero I/O. No HTTP overhead, no
timeout surface, sub-microsecond execution.

If the decision engine is later deployed as a separate service, swap
LiveDecisionClient for an HTTP variant -- the Protocol contract ensures
endpoint handlers require zero code change.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from core.schemas import (
    IrrigationDecision,
    RecAction,
    RecommendRequest,
)


@runtime_checkable
class DecisionClient(Protocol):
    """Structural contract for decision engine communication."""

    def recommend(self, req: RecommendRequest) -> IrrigationDecision: ...


class StubDecisionClient:
    """Returns hardcoded mock decisions for testing and stub mode.

    Values match original Batch 2 inline stubs in api_gateway/main.py.
    """

    def recommend(self, req: RecommendRequest) -> IrrigationDecision:
        return IrrigationDecision(
            action=RecAction.LIGHT,
            volume_mm=5.0,
            require_ack=False,
            reason="stub_early_watch",
        )


class LiveDecisionClient:
    """Calls evaluate_decision() in-process. No HTTP needed.

    The decision engine is a pure function: deterministic output
    from deterministic input, no I/O, no state mutation.
    Import is deferred to avoid circular dependency at module level.
    """

    def recommend(self, req: RecommendRequest) -> IrrigationDecision:
        from decision_engine.main import evaluate_decision
        return evaluate_decision(req)
