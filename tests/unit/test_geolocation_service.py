from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.geolocation import Coordinates, GeolocationResponse
from app.services.geolocation import GeolocationProvider, GeolocationService
from app.services.geolocation.errors import (
    GeolocationNotFoundError,
    InvalidIPAddressError,
    RateLimitError,
    ReservedIPAddressError,
    UpstreamError,
    UpstreamTimeoutError,
)

_RESULT = GeolocationResponse(
    ip="8.8.8.8",
    country="United States",
    country_code="US",
    region="Virginia",
    city="Ashburn",
    postal_code="20149",
    coordinates=Coordinates(latitude=39.03, longitude=-77.5),
    timezone="America/New_York",
    isp="Google LLC",
    organization="AS15169 Google LLC",
    provider="ip-api",
)


def _mock_provider(*, side_effect: Exception | None = None) -> MagicMock:
    provider = MagicMock(spec=GeolocationProvider)
    if side_effect is not None:
        provider.get_by_ip = AsyncMock(side_effect=side_effect)
    else:
        provider.get_by_ip = AsyncMock(return_value=_RESULT)
    return provider


async def test_single_provider_success() -> None:
    service = GeolocationService(providers=[_mock_provider()])
    result = await service.get_by_ip("8.8.8.8")
    assert result == _RESULT


async def test_first_provider_fails_second_succeeds() -> None:
    failing = _mock_provider(side_effect=UpstreamError("down"))
    succeeding = _mock_provider()

    result = await GeolocationService(providers=[failing, succeeding]).get_by_ip("8.8.8.8")

    assert result == _RESULT
    failing.get_by_ip.assert_called_once_with("8.8.8.8")
    succeeding.get_by_ip.assert_called_once_with("8.8.8.8")


@pytest.mark.parametrize(
    "error",
    [
        UpstreamError("down"),
        UpstreamTimeoutError("timeout"),
        RateLimitError("rate"),
        GeolocationNotFoundError("nf"),
    ],
)
async def test_fallback_triggers_on_recoverable_errors(error: Exception) -> None:
    succeeding = _mock_provider()
    service = GeolocationService(providers=[_mock_provider(side_effect=error), succeeding])

    result = await service.get_by_ip("8.8.8.8")

    assert result == _RESULT
    succeeding.get_by_ip.assert_called_once()


async def test_all_providers_fail_raises_last_error() -> None:
    first_error = UpstreamError("first down")
    last_error = UpstreamTimeoutError("last timeout")

    service = GeolocationService(
        providers=[
            _mock_provider(side_effect=first_error),
            _mock_provider(side_effect=last_error),
        ]
    )

    with pytest.raises(UpstreamTimeoutError, match="last timeout"):
        await service.get_by_ip("8.8.8.8")


async def test_invalid_ip_fails_fast_without_trying_next_provider() -> None:
    second = _mock_provider()
    service = GeolocationService(
        providers=[_mock_provider(side_effect=InvalidIPAddressError("bad")), second]
    )

    with pytest.raises(InvalidIPAddressError):
        await service.get_by_ip("not-an-ip")

    second.get_by_ip.assert_not_called()


async def test_reserved_ip_fails_fast_without_trying_next_provider() -> None:
    second = _mock_provider()
    service = GeolocationService(
        providers=[_mock_provider(side_effect=ReservedIPAddressError("reserved")), second]
    )

    with pytest.raises(ReservedIPAddressError):
        await service.get_by_ip("192.168.1.1")

    second.get_by_ip.assert_not_called()


async def test_no_providers_raises_upstream_error() -> None:
    with pytest.raises(UpstreamError, match="No geolocation providers configured"):
        await GeolocationService(providers=[]).get_by_ip("8.8.8.8")
