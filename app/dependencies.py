from fastapi import Request

from app.services.geolocation import (
    GeoLite2Provider,
    GeolocationProvider,
    GeolocationService,
    IPApiProvider,
)


def get_geolocation_service(request: Request) -> GeolocationService:
    providers: list[GeolocationProvider] = [
        IPApiProvider(client=request.app.state.http_client),
        GeoLite2Provider(),
    ]

    return GeolocationService(providers=providers)
