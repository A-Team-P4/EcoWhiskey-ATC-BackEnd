"""Pydantic schemas for METAR data."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CloudLayer(BaseModel):
    """Cloud layer information."""

    cover: str = Field(..., description="Cloud coverage (e.g., FEW, SCT, BKN, OVC)")
    base: int = Field(..., description="Cloud base altitude in feet AGL")


class MetarResponse(BaseModel):
    """METAR weather data response schema."""

    icaoId: str = Field(..., description="ICAO airport code")
    temp: float = Field(..., description="Temperature in Celsius")
    dewp: float = Field(..., description="Dew point in Celsius")
    wdir: int = Field(..., description="Wind direction in degrees")
    wspd: int = Field(..., description="Wind speed in knots")
    visib: str = Field(..., description="Visibility")
    altim: float = Field(..., description="Altimeter setting in inches of mercury")
    rawOb: str = Field(..., description="Raw METAR observation text")
    clouds: Optional[List[CloudLayer]] = Field(
        None, description="Cloud layer information"
    )
    fltCat: str = Field(
        ..., description="Flight category (VFR, MVFR, IFR, LIFR)"
    )

    class Config:
        populate_by_name = True
