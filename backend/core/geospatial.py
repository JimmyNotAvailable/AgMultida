from __future__ import annotations

from backend.core.errors import AgTechError, ErrorCode


Coordinate = tuple[float, float]


def calculate_centroid(polygon: list[list[float]]) -> Coordinate:
    if len(polygon) < 4:
        raise AgTechError(
            error_code=ErrorCode.VALIDATION_ERROR,
            message="Polygon must contain at least four coordinates",
            status_code=400,
        )
    points = polygon[:-1]
    longitude = sum(point[0] for point in points) / len(points)
    latitude = sum(point[1] for point in points) / len(points)
    return latitude, longitude
