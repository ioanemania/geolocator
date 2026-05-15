from abc import ABC, abstractmethod

import httpx

from app.config import settings
from app.models.geolocation import Coordinates, GeolocationResponse
from app.services.geolocation.errors import (
    GeolocationNotFoundError,
    InvalidIPAddressError,
    RateLimitError,
    ReservedIPAddressError,
    UpstreamError,
    UpstreamTimeoutError,
)

_IP_API_FAIL_MESSAGES: dict[
    str, type[GeolocationNotFoundError | InvalidIPAddressError | ReservedIPAddressError]
] = {
    "invalid query": InvalidIPAddressError,
    "private range": ReservedIPAddressError,
    "reserved range": ReservedIPAddressError,
}


class GeolocationProvider(ABC):
    @abstractmethod
    async def get_by_ip(self, ip: str) -> GeolocationResponse: ...


class IPApiProvider(GeolocationProvider):
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def get_by_ip(self, ip: str) -> GeolocationResponse:
        try:
            response = await self._client.get(
                f"{settings.ip_api_base_url}/{ip}",
                timeout=settings.request_timeout,
            )
        except httpx.TimeoutException as exc:
            raise UpstreamTimeoutError("The geolocation provider did not respond in time.") from exc
        except httpx.HTTPError as exc:
            raise UpstreamError(f"Failed to reach the geolocation provider: {exc}") from exc

        if response.status_code == 429:
            raise RateLimitError("Rate limit exceeded. Please try again later.")

        if response.status_code != 200:
            raise UpstreamError(
                f"Geolocation provider returned an unexpected status: {response.status_code}."
            )

        data = response.json()

        if data.get("status") == "fail":
            message: str = data.get("message", "")
            exc_class = _IP_API_FAIL_MESSAGES.get(message, GeolocationNotFoundError)
            raise exc_class(f"Geolocation lookup failed: {message or 'unknown reason'}.")

        return GeolocationResponse(
            ip=data["query"],
            country=data.get("country", ""),
            country_code=data.get("countryCode", ""),
            region=data.get("regionName", ""),
            city=data.get("city", ""),
            postal_code=data.get("zip", ""),
            coordinates=Coordinates(
                latitude=data.get("lat", 0.0),
                longitude=data.get("lon", 0.0),
            ),
            timezone=data.get("timezone", ""),
            isp=data.get("isp", ""),
            organization=data.get("org", ""),
        )
