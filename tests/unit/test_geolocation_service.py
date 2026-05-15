import httpx
import pytest
import respx

from app.config import settings
from app.services.geolocation import (
    GeolocationNotFoundError,
    InvalidIPAddressError,
    IPApiProvider,
    RateLimitError,
    ReservedIPAddressError,
    UpstreamError,
    UpstreamTimeoutError,
)
from tests.conftest import IP_API_SUCCESS_PAYLOAD


@pytest.fixture()
def provider() -> IPApiProvider:
    return IPApiProvider(client=httpx.AsyncClient())


@respx.mock
async def test_get_by_ip_success(provider: IPApiProvider) -> None:
    respx.get(f"{settings.ip_api_base_url}/8.8.8.8").mock(
        return_value=httpx.Response(200, json=IP_API_SUCCESS_PAYLOAD)
    )

    result = await provider.get_by_ip("8.8.8.8")

    assert result.ip == "8.8.8.8"
    assert result.country == "United States"
    assert result.country_code == "US"
    assert result.city == "Ashburn"
    assert result.coordinates.latitude == 39.03
    assert result.coordinates.longitude == -77.5


@respx.mock
async def test_get_by_ip_invalid_query_raises_invalid_ip_error(
    provider: IPApiProvider,
) -> None:
    respx.get(f"{settings.ip_api_base_url}/not-an-ip").mock(
        return_value=httpx.Response(200, json={"status": "fail", "message": "invalid query"})
    )

    with pytest.raises(InvalidIPAddressError):
        await provider.get_by_ip("not-an-ip")


@respx.mock
async def test_get_by_ip_private_range_raises_reserved_error(
    provider: IPApiProvider,
) -> None:
    respx.get(f"{settings.ip_api_base_url}/192.168.1.1").mock(
        return_value=httpx.Response(200, json={"status": "fail", "message": "private range"})
    )

    with pytest.raises(ReservedIPAddressError):
        await provider.get_by_ip("192.168.1.1")


@respx.mock
async def test_get_by_ip_unknown_fail_raises_not_found(
    provider: IPApiProvider,
) -> None:
    respx.get(f"{settings.ip_api_base_url}/1.2.3.4").mock(
        return_value=httpx.Response(200, json={"status": "fail", "message": ""})
    )

    with pytest.raises(GeolocationNotFoundError):
        await provider.get_by_ip("1.2.3.4")


@respx.mock
async def test_get_by_ip_rate_limit_raises_rate_limit_error(
    provider: IPApiProvider,
) -> None:
    respx.get(f"{settings.ip_api_base_url}/8.8.8.8").mock(return_value=httpx.Response(429))

    with pytest.raises(RateLimitError):
        await provider.get_by_ip("8.8.8.8")


@respx.mock
async def test_get_by_ip_upstream_5xx_raises_upstream_error(
    provider: IPApiProvider,
) -> None:
    respx.get(f"{settings.ip_api_base_url}/8.8.8.8").mock(return_value=httpx.Response(503))

    with pytest.raises(UpstreamError):
        await provider.get_by_ip("8.8.8.8")


@respx.mock
async def test_get_by_ip_timeout_raises_upstream_timeout_error(
    provider: IPApiProvider,
) -> None:
    respx.get(f"{settings.ip_api_base_url}/8.8.8.8").mock(
        side_effect=httpx.TimeoutException("timed out")
    )

    with pytest.raises(UpstreamTimeoutError):
        await provider.get_by_ip("8.8.8.8")
