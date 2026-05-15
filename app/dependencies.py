from fastapi import Request

from app.services.geolocation import GeolocationService, IPApiProvider


def get_geolocation_service(request: Request) -> GeolocationService:
    return GeolocationService(provider=IPApiProvider(client=request.app.state.http_client))
