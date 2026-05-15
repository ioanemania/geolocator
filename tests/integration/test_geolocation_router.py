import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.config import settings
from app.main import create_app
from tests.conftest import IP_API_SUCCESS_PAYLOAD


@pytest.fixture()
def client() -> TestClient:
    with TestClient(create_app()) as c:
        yield c


# ---------------------------------------------------------------------------
# GET /v1/geolocation/{ip}
# ---------------------------------------------------------------------------


@respx.mock
def test_get_ip_geolocation_success(client: TestClient) -> None:
    respx.get(f"{settings.ip_api_base_url}/8.8.8.8").mock(
        return_value=httpx.Response(200, json=IP_API_SUCCESS_PAYLOAD)
    )

    response = client.get("/v1/geolocation/8.8.8.8")

    assert response.status_code == 200
    body = response.json()
    assert body["ip"] == "8.8.8.8"
    assert body["country"] == "United States"
    assert body["country_code"] == "US"
    assert body["coordinates"]["latitude"] == 39.03


@respx.mock
def test_get_ip_geolocation_invalid_ip_returns_400(client: TestClient) -> None:
    respx.get(f"{settings.ip_api_base_url}/bad-ip").mock(
        return_value=httpx.Response(200, json={"status": "fail", "message": "invalid query"})
    )

    response = client.get("/v1/geolocation/bad-ip")

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "INVALID_IP_ADDRESS"


@respx.mock
def test_get_ip_geolocation_private_ip_returns_400(client: TestClient) -> None:
    respx.get(f"{settings.ip_api_base_url}/10.0.0.1").mock(
        return_value=httpx.Response(200, json={"status": "fail", "message": "private range"})
    )

    response = client.get("/v1/geolocation/10.0.0.1")

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "RESERVED_IP_ADDRESS"


@respx.mock
def test_get_ip_geolocation_rate_limit_returns_429(client: TestClient) -> None:
    respx.get(f"{settings.ip_api_base_url}/8.8.8.8").mock(return_value=httpx.Response(429))

    response = client.get("/v1/geolocation/8.8.8.8")

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"


@respx.mock
def test_get_ip_geolocation_upstream_timeout_returns_504(client: TestClient) -> None:
    respx.get(f"{settings.ip_api_base_url}/8.8.8.8").mock(
        side_effect=httpx.TimeoutException("timed out")
    )

    response = client.get("/v1/geolocation/8.8.8.8")

    assert response.status_code == 504
    assert response.json()["error"]["code"] == "UPSTREAM_TIMEOUT"


# ---------------------------------------------------------------------------
# GET /v1/geolocation/me
# ---------------------------------------------------------------------------


@respx.mock
def test_get_my_geolocation_extracts_forwarded_ip(client: TestClient) -> None:
    """Verify /me reads X-Forwarded-For and returns geolocation for that IP."""
    respx.get(f"{settings.ip_api_base_url}/8.8.8.8").mock(
        return_value=httpx.Response(200, json=IP_API_SUCCESS_PAYLOAD)
    )

    response = client.get("/v1/geolocation/me", headers={"X-Forwarded-For": "8.8.8.8"})

    assert response.status_code == 200
    assert response.json()["ip"] == "8.8.8.8"
