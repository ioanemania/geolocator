from unittest.mock import MagicMock, patch

import geoip2.errors
import pytest

from app.services.geolocation import (
    GeoLite2Provider,
    GeolocationNotFoundError,
    InvalidIPAddressError,
    ReservedIPAddressError,
)


def _make_city_record(
    *,
    country_name: str = "United States",
    country_code: str = "US",
    region_name: str = "Virginia",
    city_name: str = "Ashburn",
    postal_code: str = "20149",
    latitude: float = 39.03,
    longitude: float = -77.5,
    timezone: str = "America/New_York",
) -> MagicMock:
    record = MagicMock()
    record.country.name = country_name
    record.country.iso_code = country_code
    record.subdivisions.most_specific.name = region_name
    record.city.name = city_name
    record.postal.code = postal_code
    record.location.latitude = latitude
    record.location.longitude = longitude
    record.location.time_zone = timezone
    return record


@pytest.fixture()
def mock_reader() -> MagicMock:
    return MagicMock()


@pytest.fixture()
def provider(mock_reader: MagicMock) -> GeoLite2Provider:
    with patch("geoip2.database.Reader", return_value=mock_reader):
        return GeoLite2Provider(db_path="data/GeoLite2-City.mmdb")


async def test_get_by_ip_success(provider: GeoLite2Provider, mock_reader: MagicMock) -> None:
    mock_reader.city.return_value = _make_city_record()

    result = await provider.get_by_ip("8.8.8.8")

    assert result.ip == "8.8.8.8"
    assert result.country == "United States"
    assert result.country_code == "US"
    assert result.region == "Virginia"
    assert result.city == "Ashburn"
    assert result.postal_code == "20149"
    assert result.coordinates.latitude == 39.03
    assert result.coordinates.longitude == -77.5
    assert result.timezone == "America/New_York"
    assert result.isp == ""
    assert result.organization == ""
    mock_reader.city.assert_called_once_with("8.8.8.8")


async def test_get_by_ip_missing_fields_default_to_empty(
    provider: GeoLite2Provider, mock_reader: MagicMock
) -> None:
    mock_reader.city.return_value = _make_city_record(
        country_name="", country_code="", region_name="", city_name="", postal_code=""
    )

    result = await provider.get_by_ip("1.1.1.1")

    assert result.country == ""
    assert result.country_code == ""
    assert result.region == ""
    assert result.city == ""
    assert result.postal_code == ""


async def test_get_by_ip_none_fields_default_to_empty(
    provider: GeoLite2Provider, mock_reader: MagicMock
) -> None:
    record = MagicMock()
    record.country.name = None
    record.country.iso_code = None
    record.subdivisions.most_specific.name = None
    record.city.name = None
    record.postal.code = None
    record.location.latitude = None
    record.location.longitude = None
    record.location.time_zone = None
    mock_reader.city.return_value = record

    result = await provider.get_by_ip("1.1.1.1")

    assert result.country == ""
    assert result.coordinates.latitude == 0.0
    assert result.coordinates.longitude == 0.0
    assert result.timezone == ""


async def test_get_by_ip_not_in_database_raises_not_found(
    provider: GeoLite2Provider, mock_reader: MagicMock
) -> None:
    mock_reader.city.side_effect = geoip2.errors.AddressNotFoundError("not found")

    with pytest.raises(GeolocationNotFoundError):
        await provider.get_by_ip("1.2.3.4")


@pytest.mark.parametrize("ip", ["not-an-ip", "999.999.999.999", "abc", ""])
async def test_invalid_ip_raises_invalid_ip_error(provider: GeoLite2Provider, ip: str) -> None:
    with pytest.raises(InvalidIPAddressError):
        await provider.get_by_ip(ip)


@pytest.mark.parametrize(
    "ip",
    [
        "192.168.1.1",  # private
        "10.0.0.1",  # private
        "172.16.0.1",  # private
        "127.0.0.1",  # loopback
        "169.254.0.1",  # link-local
        "240.0.0.1",  # reserved
    ],
)
async def test_reserved_ip_raises_reserved_error(provider: GeoLite2Provider, ip: str) -> None:
    with pytest.raises(ReservedIPAddressError):
        await provider.get_by_ip(ip)
