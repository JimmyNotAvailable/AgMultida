from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class CurrentWeather(BaseModel):
    model_config = ConfigDict(extra="ignore")

    time: datetime
    temperature_2m: Optional[float] = None
    relative_humidity_2m: Optional[float] = None
    precipitation: Optional[float] = None
    wind_speed_10m: Optional[float] = None


class HourlyWeather(BaseModel):
    model_config = ConfigDict(extra="ignore")

    time: list[datetime] = Field(default_factory=list)
    temperature_2m: list[float | None] = Field(default_factory=list)
    relative_humidity_2m: list[float | None] = Field(default_factory=list)
    precipitation_probability: list[float | None] = Field(default_factory=list)
    precipitation: list[float | None] = Field(default_factory=list)


class ZoneWeatherResponse(BaseModel):
    zone_id: str
    latitude: float
    longitude: float
    source: str = "open-meteo"
    current: Optional[CurrentWeather] = None
    hourly: Optional[HourlyWeather] = None
    updated_at: datetime
