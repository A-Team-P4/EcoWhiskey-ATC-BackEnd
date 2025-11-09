"""METAR weather data proxy endpoints."""

import httpx
from fastapi import APIRouter, HTTPException, status

from app.views.metar import MetarResponse

router = APIRouter(prefix="/metar", tags=["metar"])


@router.get("/{icao_code}", response_model=MetarResponse)
async def get_metar(icao_code: str) -> MetarResponse:
    """
    Proxy endpoint to fetch METAR data from Aviation Weather API.
    Avoids CORS issues when calling from web frontend.

    Args:
        icao_code: ICAO airport code (e.g., "MRPV")

    Returns:
        METAR weather data for the specified airport

    Raises:
        HTTPException: 404 if no METAR data available, 500 for other errors
    """
    icao_code = icao_code.upper()

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"https://aviationweather.gov/api/data/metar?ids={icao_code}&format=json",
                timeout=10.0,
            )
            response.raise_for_status()

            data = response.json()

            if not data or len(data) == 0:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No METAR data available for {icao_code}",
                )

            return MetarResponse(**data[0])

        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Error fetching METAR data: {str(e)}",
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Unable to connect to Aviation Weather API: {str(e)}",
            )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Invalid response from Aviation Weather API: {str(e)}",
            )
