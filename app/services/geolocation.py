import httpx
from fastapi import Request

from app.config import settings
from app.models.geolocation import Coordinates, GeolocationResponse


class GeolocationError(Exception):
    """Base class for geolocation errors."""

    http_status: int
    error_code: str

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InvalidIPAddressError(GeolocationError):
    http_status = 400
    error_code = "INVALID_IP_ADDRESS"


class ReservedIPAddressError(GeolocationError):
    http_status = 400
    error_code = "RESERVED_IP_ADDRESS"


class GeolocationNotFoundError(GeolocationError):
    http_status = 404
    error_code = "GEOLOCATION_NOT_FOUND"


class RateLimitError(GeolocationError):
    http_status = 429
    error_code = "RATE_LIMIT_EXCEEDED"


class UpstreamError(GeolocationError):
    http_status = 502
    error_code = "UPSTREAM_ERROR"


class UpstreamTimeoutError(GeolocationError):
    http_status = 504
    error_code = "UPSTREAM_TIMEOUT"


_IP_API_FAIL_MESSAGES: dict[str, type[GeolocationError]] = {
    "invalid query": InvalidIPAddressError,
    "private range": ReservedIPAddressError,
    "reserved range": ReservedIPAddressError,
}


def _extract_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    if request.client:
        return request.client.host

    raise UpstreamError("Unable to determine client IP address.")


class GeolocationService:
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

    async def get_by_request(self, request: Request) -> GeolocationResponse:
        ip = _extract_client_ip(request)
        return await self.get_by_ip(ip)
