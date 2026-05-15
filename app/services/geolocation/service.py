from fastapi import Request

from app.models.geolocation import GeolocationResponse
from app.services.geolocation.errors import (
    GeolocationError,
    InvalidIPAddressError,
    ReservedIPAddressError,
    UpstreamError,
)
from app.services.geolocation.providers import GeolocationProvider


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
    def __init__(self, providers: list[GeolocationProvider]) -> None:
        self._providers = providers

    async def get_by_ip(self, ip: str) -> GeolocationResponse:
        last_error: GeolocationError | None = None
        for provider in self._providers:
            try:
                return await provider.get_by_ip(ip)
            except (InvalidIPAddressError, ReservedIPAddressError):
                raise
            except GeolocationError as exc:
                last_error = exc
        if last_error is not None:
            raise last_error
        raise UpstreamError("No geolocation providers configured.")

    async def get_by_request(self, request: Request) -> GeolocationResponse:
        ip = _extract_client_ip(request)
        return await self.get_by_ip(ip)
