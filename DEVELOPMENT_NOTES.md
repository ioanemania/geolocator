# Development Notes

## Implementation Walkthrough

I approached this build in layers, starting from the contract outward:

1. **Project scaffolding** — `pyproject.toml` with all dependencies, ruff, mypy, and pytest configuration settled upfront so the toolchain was consistent from the first line of code.
2. **Data models** — Pydantic models for `GeolocationResponse`, `Coordinates`, and `ErrorResponse` came next, since these define the API contract and everything downstream depends on them.
3. **Provider abstraction** — `GeolocationProvider` ABC defines a single `get_by_ip` contract. Two concrete implementations exist: `IPApiProvider` (HTTP, zero-setup) and `GeoLite2Provider` (local MaxMind database, sub-millisecond). This separation means the service layer is entirely decoupled from transport details.
4. **Service layer** — `GeolocationService` accepts a prioritised list of providers and implements ordered fallback: it tries each provider in turn, skipping to the next on any recoverable error, but propagates `InvalidIPAddressError` and `ReservedIPAddressError` immediately (no point retrying those). The typed exception hierarchy (`GeolocationError` subclasses) carries `http_status` and `error_code` as class attributes so error mapping is co-located with business logic.
5. **Routing layer** — `FastAPI` router wired to the service via dependency injection. The `/me` route is registered before `/{ip}` to ensure FastAPI's exact-match routing resolves it correctly.
6. **App assembly** — `main.py` uses a `lifespan` context manager to create and close a shared `httpx.AsyncClient`, and registers a global exception handler that converts any `GeolocationError` subclass into the consistent JSON error envelope.
7. **Toolchain hardening** — pre-commit hooks run `ruff-format`, `ruff --fix`, and `mypy` before every commit, so style and type errors are caught locally before they reach CI.
8. **Container packaging** — multi-stage `Dockerfile` (builder stage with `uv`, lean runtime stage on `python:3.11-slim-bookworm`, non-root path, `EXPOSE 8000`) and a `docker-compose.yml` for local development.
9. **Tests** — unit tests for both providers and the service fallback logic (via mocks), plus integration tests (TestClient + `respx`). Coverage reporting added via `pytest-cov`.

---

## Total Time Spent

Approximately 4 hours.

---

## Challenges & Solutions

**Route conflict between `/me` and `/{ip}`**
FastAPI evaluates routes in registration order. Registering `/me` before `/{ip}` in the same router ensures the literal path wins. This is a common gotcha with parameterised routes.

**Client IP extraction for `/me`**
The raw `request.client.host` is often a load balancer address in production. I implemented a three-step fallback: `X-Forwarded-For` → `X-Real-IP` → `request.client.host`. This is a pragmatic heuristic; a stricter production approach would involve configuring trusted proxy IPs (e.g., with `ProxyHeadersMiddleware`).

**Consistent error shape across all failure modes**
I defined a typed exception hierarchy (`GeolocationError` and subclasses), each carrying `http_status` and `error_code` as class attributes. The single global exception handler in `main.py` converts any of these to the same `{"error": {"code": ..., "message": ...}}` envelope. This keeps error formatting logic in one place.

**Reserved/invalid IP short-circuit in fallback**
The fallback loop in `GeolocationService` must not retry `InvalidIPAddressError` or `ReservedIPAddressError` — no provider can succeed on a malformed or private IP. These are re-raised immediately; only upstream errors (timeouts, rate limits, 5xx) trigger the next provider.

**GeoLite2Provider reserved-IP validation**
Unlike ip-api.com, geoip2 does not return a structured error for reserved IPs — it just raises `AddressNotFoundError`. A shared `_check_reserved()` helper runs an `ipaddress.ip_address()` check before the database lookup, producing a consistent `ReservedIPAddressError` regardless of provider.

---

## GenAI Usage

Claude Code was used throughout this project — primarily for:
- Scaffolding boilerplate (pyproject.toml fields, `__init__.py` stubs)
- Generating the initial test cases, which I then reviewed and adjusted
- Drafting documentation text

The architecture, API design decisions, provider abstraction, and fallback strategy were designed by me; Claude accelerated execution of those decisions. I reviewed every generated file before keeping it.

---

## API Design Decisions

### Versioning (`/v1/...`)
All endpoints are prefixed with `/v1`. This costs nothing now and avoids a painful retrofit later if a v2 is ever needed.

### Two endpoints, not one with an optional parameter
`/v1/geolocation/me` and `/v1/geolocation/{ip}` are separate routes rather than a single route with an optional IP. This keeps each endpoint's semantics unambiguous in the OpenAPI spec and avoids conditional logic in the handler.

### `coordinates` as a nested object
Latitude and longitude are grouped into a `Coordinates` sub-object rather than flat `latitude`/`longitude` fields. This is more idiomatic for geospatial data and signals to clients that these fields travel together.

### snake_case field names
Python convention, consistent with FastAPI/Pydantic defaults, and friendlier for JavaScript clients (where `country_code` is immediately destructurable) than camelCase.

### Error codes as SCREAMING_SNAKE_CASE strings
Machine-readable error codes let clients branch on `error.code` without parsing `error.message`. Using a string constant rather than an integer code makes the spec self-documenting.

---

## Third-Party API / Database Selection

**Chosen approach:** Both — with ordered fallback.

The service ships with two providers wired in priority order:

1. **ip-api.com** (`IPApiProvider`) — tried first. Zero setup, no API key, rich payload. 45 req/min on the free tier is sufficient for development and demo purposes.
2. **MaxMind GeoLite2** (`GeoLite2Provider`) — tried if ip-api.com fails. Sub-millisecond, no network round-trip, no rate limits. Requires the `.mmdb` database file at `data/GeoLite2-City.mmdb` (configured via `APP_GEOLITE2_DB_PATH`).

**Trade-offs:**

| | ip-api.com | GeoLite2 |
|--|--|--|
| Setup | Zero | Requires download + periodic refresh |
| Latency | Network round-trip (20–100 ms) | Sub-millisecond |
| Rate limits | Yes (free tier) | None |
| Offline operation | No | Yes |
| ISP / org data | Yes | No |
| Data freshness | Provider-managed | Manual updates required |
| Cost at scale | Paid tier or self-hosted | Free |

---

## Production Readiness

### Already shipped

- **Multi-provider fallback** — ip-api.com primary with GeoLite2 as a local fallback; upstream errors silently cascade to the next provider.
- **Input validation** — `_check_reserved()` validates the IP against `ipaddress.ip_address()` and rejects private/loopback/reserved addresses before any network call or database lookup, returning a 400 immediately.
- **Docker / container packaging** — multi-stage `Dockerfile` (uv builder + `python:3.11-slim-bookworm` runtime, `EXPOSE 8000`) and `docker-compose.yml` for local development.
- **Pre-commit hooks** — `ruff-format`, `ruff --fix`, and `mypy` gate every commit; code style and type errors are caught locally.
- **Coverage reporting** — `pytest-cov` integrated; run `uv run pytest --cov=app` for an HTML/terminal report.

### What I Would Implement Next

1. **Caching** — Redis-backed cache keyed on IP with a TTL of a few hours. Geolocation data rarely changes; caching would eliminate most upstream calls and eliminate rate-limit risk entirely.

2. **Rate limiting** — A per-client rate limiter (e.g., `slowapi`) to protect the service itself, independent of the upstream provider's limits.

3. **Structured logging** — Replace implicit FastAPI access logs with structured JSON logs (using `structlog` or `python-json-logger`) that include request ID, IP, response time, and which provider served the request.

4. **Request ID propagation** — Generate a `X-Request-ID` header on every request and thread it through logs and error responses to make distributed tracing possible.

5. **Health check endpoint** — `GET /health` returning service version, provider availability, and (for GeoLite2) database file age — suitable as a Kubernetes liveness/readiness probe.

6. **Circuit breaker** — Wrap upstream calls with a circuit breaker (e.g., `circuitbreaker` library) to fail fast when ip-api.com is degraded, rather than queuing up timeouts before the fallback triggers.

7. **GeoLite2 refresh automation** — Weekly cron job (or GitHub Actions workflow) to download a fresh `.mmdb` from MaxMind and hot-reload without restarting the process.

8. **CI pipeline** — GitHub Actions workflow running `ruff`, `mypy`, and `pytest --cov` on every pull request with required status checks before merge.

9. **CD pipeline** — On merge to `main`, a GitHub Actions workflow builds and pushes the Docker image to a container registry (e.g., GitHub Container Registry or AWS ECR), then deploys to a managed container service. The natural target would be AWS ECS (Fargate) or Google Cloud Run — both accept a Docker image directly, handle TLS termination and autoscaling, and require no cluster management. Cloud Run is the lowest-friction option for a stateless HTTP service like this: push an image, set `APP_*` env vars as secrets, and the platform handles everything else. A production deployment would also pin the image digest (not `:latest`) and require a passing CI run before the deploy job is unlocked.

10. **Commercial database provider** — Add a third `GeolocationProvider` backed by a private database such as MaxMind GeoIP2 Precision (the paid, hosted counterpart to the free GeoLite2) or ipinfo.io's API. Unlike GeoLite2, these services are continuously updated by the vendor and offer higher accuracy for city-level lookups, ASN data, and proxy/VPN/Tor detection. Unlike ip-api.com, they have no hard rate limits on paid tiers and offer SLA-backed uptime. The existing provider abstraction means adding this is a single new class implementing `GeolocationProvider`.

11. **Trusted proxy configuration for `/me`** — The current `_extract_client_ip()` implementation blindly trusts `X-Forwarded-For` and `X-Real-IP`, which means any client can spoof those headers and get geolocation data for an arbitrary IP (Which they can already do anyways through the API because of the way its simplistic design. but it is still good security measurement to prevent this). In production, only headers injected by a known load balancer or reverse proxy should be trusted. The fix is to add an `APP_TRUSTED_PROXIES` config setting (a list of CIDR ranges), then in `_extract_client_ip()` check whether `request.client.host` falls within that list before honouring the forwarded headers — discarding them entirely if the immediate sender is not a trusted proxy. Alternatively, Uvicorn's `--proxy-headers` flag combined with `--forwarded-allow-ips` delegates this to the ASGI server, which is the lower-effort approach for a Cloud Run or ECS deployment where the proxy IPs are predictable.

12. **Observability** — Prometheus metrics endpoint (`/metrics`) exposing request counts, error rates, per-provider latency histograms, and fallback frequency. Paired with a Grafana dashboard for on-call visibility.
