class GeolocationError(Exception):
    http_status: int
    error_code: str

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InvalidIPAddressError(GeolocationError):
    http_status = 400
    error_code = "INVALID_IP_ADDRESS"


class ReservedIPAddressError(GeolocationError):
    http_status = 400
    error_code = "RESERVED_IP_ADDRESS"


class GeolocationNotFoundError(GeolocationError):
    http_status = 404
    error_code = "GEOLOCATION_NOT_FOUND"


class RateLimitError(GeolocationError):
    http_status = 429
    error_code = "RATE_LIMIT_EXCEEDED"


class UpstreamError(GeolocationError):
    http_status = 502
    error_code = "UPSTREAM_ERROR"


class UpstreamTimeoutError(GeolocationError):
    http_status = 504
    error_code = "UPSTREAM_TIMEOUT"
