"""XAI explainer: convert attention weights to feature importance payload.

Maps raw cross-attention weights [49] to human-readable feature importance
list matching schemas.py::FeatureImportance. Feature names sourced from
contracts/data_contract.yaml sensor_seq features + weather_ctx.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# Feature names aligned with data_contract.yaml
SENSOR_FEATURES = [
    "soil_moisture", "soil_temp", "air_temp", "humidity",
    "ec", "ph", "rain_3h", "rain_24h",
]
WEATHER_FEATURES = [
    "rain_forecast_3h", "rain_24h_cumulative", "temp_max_24h",
    "temp_min_24h", "humidity_avg_24h", "et0_daily",
]

# Attention weight layout: [48 sensor timesteps, 1 weather token] = 49
SENSOR_TIMESTEPS = 48
WEATHER_TOKENS = 1


@dataclass
class FeatureExplanation:
    """Single feature contribution for XAI payload."""
    feature: str
    weight: float
    trend: str  # increasing | decreasing | stable | unknown


def explain_attention(
    attention_weights: list[float] | np.ndarray,
    sensor_recent: np.ndarray | None = None,
    top_k: int = 5,
) -> list[FeatureExplanation]:
    """Convert attention weights to feature importance list.

    Args:
        attention_weights: [49] cross-attention weights.
        sensor_recent: [48, 8] recent sensor data for trend detection.
            If None, trends default to "unknown".
        top_k: Number of top features to return.

    Returns:
        Sorted list of top-k FeatureExplanation items.
    """
    weights = np.array(attention_weights, dtype=np.float32)
    assert len(weights) == SENSOR_TIMESTEPS + WEATHER_TOKENS, (
        f"Expected {SENSOR_TIMESTEPS + WEATHER_TOKENS} weights, got {len(weights)}"
    )

    # Aggregate sensor attention: sum over timesteps per feature
    sensor_weights = weights[:SENSOR_TIMESTEPS]  # [48]
    weather_weight = weights[SENSOR_TIMESTEPS]     # scalar

    # Distribute sensor timestep attention across 8 features equally
    # (refined version would use per-feature attention from a more granular model)
    per_feature_sensor = float(sensor_weights.sum()) / len(SENSOR_FEATURES)

    explanations: list[FeatureExplanation] = []

    for i, feat_name in enumerate(SENSOR_FEATURES):
        trend = _detect_trend(sensor_recent, i) if sensor_recent is not None else "unknown"
        explanations.append(FeatureExplanation(
            feature=feat_name,
            weight=round(per_feature_sensor, 4),
            trend=trend,
        ))

    # Weather contribution (aggregated as single token)
    explanations.append(FeatureExplanation(
        feature="weather_context",
        weight=round(float(weather_weight), 4),
        trend="unknown",
    ))

    # Normalize weights to sum to 1.0
    total = sum(e.weight for e in explanations)
    if total > 0:
        for e in explanations:
            e.weight = round(e.weight / total, 4)

    # Sort by weight descending, return top-k
    explanations.sort(key=lambda x: x.weight, reverse=True)
    return explanations[:top_k]


def _detect_trend(sensor_data: np.ndarray, feature_idx: int) -> str:
    """Simple trend detection on the last 12 hours of a sensor feature."""
    if sensor_data is None or sensor_data.shape[0] < 12:
        return "unknown"

    recent = sensor_data[-12:, feature_idx]
    if np.all(np.isnan(recent)):
        return "unknown"

    slope = np.polyfit(range(len(recent)), recent, 1)[0]
    if slope > 0.01:
        return "increasing"
    elif slope < -0.01:
        return "decreasing"
    return "stable"
