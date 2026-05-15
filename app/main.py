from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.config import settings
from app.models.errors import ErrorDetail, ErrorResponse
from app.routers.geolocation import router as geolocation_router
from app.services.geolocation import GeolocationError


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    app.state.http_client = httpx.AsyncClient()
    yield
    await app.state.http_client.aclose()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "A microservice that provides IP address geolocation information "
            "by integrating with the ip-api.com API."
        ),
        lifespan=lifespan,
    )

    @app.exception_handler(GeolocationError)
    async def geolocation_error_handler(_request: object, exc: GeolocationError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.http_status,
            content=ErrorResponse(
                error=ErrorDetail(code=exc.error_code, message=exc.message)
            ).model_dump(),
        )

    app.include_router(geolocation_router, prefix="/v1")

    return app


app = create_app()
