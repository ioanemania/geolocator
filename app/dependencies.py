from fastapi import Request

from app.services.geolocation import GeolocationService


def get_geolocation_service(request: Request) -> GeolocationService:
    return GeolocationService(client=request.app.state.http_client)
