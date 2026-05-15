import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.geolocation import GeolocationService

IP_API_SUCCESS_PAYLOAD = {
    "status": "success",
    "country": "United States",
    "countryCode": "US",
    "regionName": "Virginia",
    "city": "Ashburn",
    "zip": "20149",
    "lat": 39.03,
    "lon": -77.5,
    "timezone": "America/New_York",
    "isp": "Google LLC",
    "org": "AS15169 Google LLC",
    "query": "8.8.8.8",
}


@pytest.fixture()
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture()
def test_client() -> TestClient:
    """Sync TestClient with a real (but mockable) httpx client attached."""
    application = create_app()
    with TestClient(application) as client:
        yield client


@pytest.fixture()
def mock_geolocation_service(mocker: pytest.MonkeyPatch) -> GeolocationService:
    """Return a GeolocationService backed by a mock AsyncClient."""
    mock_client = mocker.MagicMock(spec=httpx.AsyncClient)
    return GeolocationService(client=mock_client)
