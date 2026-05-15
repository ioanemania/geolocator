from fastapi import APIRouter, Depends, Request

from app.dependencies import get_geolocation_service
from app.models.errors import ErrorResponse
from app.models.geolocation import GeolocationResponse
from app.services.geolocation import GeolocationService

router = APIRouter(prefix="/geolocation", tags=["Geolocation"])

_error_responses: dict[int | str, dict[str, object]] = {
    400: {"model": ErrorResponse, "description": "Invalid or reserved IP address"},
    404: {"model": ErrorResponse, "description": "Geolocation data not found for the IP"},
    429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
    502: {"model": ErrorResponse, "description": "Upstream geolocation provider error"},
    504: {"model": ErrorResponse, "description": "Upstream geolocation provider timed out"},
}


@router.get(
    "/me",
    response_model=GeolocationResponse,
    summary="Get geolocation for the requesting client",
    description=(
        "Automatically detects the client's IP address from the request "
        "and returns its geolocation information."
    ),
    responses=_error_responses,
)
async def get_my_geolocation(
    request: Request,
    service: GeolocationService = Depends(get_geolocation_service),
) -> GeolocationResponse:
    return await service.get_by_request(request)


@router.get(
    "/{ip}",
    response_model=GeolocationResponse,
    summary="Get geolocation for a specific IP address",
    description=(
        "Looks up geolocation information for the given IPv4 address, "
        "including country, region, city, coordinates, timezone, and ISP."
    ),
    responses=_error_responses,
)
async def get_ip_geolocation(
    ip: str,
    service: GeolocationService = Depends(get_geolocation_service),
) -> GeolocationResponse:
    return await service.get_by_ip(ip)
