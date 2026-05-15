from fastapi import Request

from app.models.geolocation import GeolocationResponse
from app.services.geolocation.errors import UpstreamError
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
    def __init__(self, provider: GeolocationProvider) -> None:
        self._provider = provider

    async def get_by_ip(self, ip: str) -> GeolocationResponse:
        return await self._provider.get_by_ip(ip)

    async def get_by_request(self, request: Request) -> GeolocationResponse:
        ip = _extract_client_ip(request)
        return await self._provider.get_by_ip(ip)
