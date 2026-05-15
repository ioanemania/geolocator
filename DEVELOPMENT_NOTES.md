# Development Notes

## Implementation Walkthrough

I approached this build in layers, starting from the contract outward:

1. **Project scaffolding** — `pyproject.toml` with all dependencies, ruff, mypy, and pytest configuration settled upfront so the toolchain was consistent from the first line of code.
2. **Data models** — Pydantic models for `GeolocationResponse`, `Coordinates`, and `ErrorResponse` came next, since these define the API contract and everything downstream depends on them.
3. **Service layer** — `GeolocationService` encapsulates all ip-api.com communication and error mapping. I defined a typed exception hierarchy here so the HTTP status mapping is co-located with the business logic.
4. **Routing layer** — `FastAPI` router wired to the service via dependency injection. The `/me` route is registered before `/{ip}` to ensure FastAPI's exact-match routing resolves it correctly.
5. **App assembly** — `main.py` uses a `lifespan` context manager to create and close a shared `httpx.AsyncClient`, and registers a global exception handler that converts `GeolocationError` subclasses into the consistent JSON error format.
6. **Tests** — unit tests (via `respx` mock transport) and integration tests (TestClient + `respx`) were written last.

---

## Total Time Spent

Approximately 2.5 hours.

---

## Challenges & Solutions

**Route conflict between `/me` and `/{ip}`**
FastAPI evaluates routes in registration order. Registering `/me` before `/{ip}` in the same router ensures the literal path wins. This is a common gotcha with parameterised routes.

**Client IP extraction for `/me`**
The raw `request.client.host` is often a load balancer address in production. I implemented a three-step fallback: `X-Forwarded-For` → `X-Real-IP` → `request.client.host`. This is a pragmatic heuristic; a stricter production approach would involve configuring trusted proxy IPs (e.g., with `ProxyHeadersMiddleware`).

**Consistent error shape across all failure modes**
I defined a typed exception hierarchy (`GeolocationError` and subclasses), each carrying `http_status` and `error_code` as class attributes. The single global exception handler in `main.py` converts any of these to the same `{"error": {"code": ..., "message": ...}}` envelope. This keeps error formatting logic in one place.

---

## GenAI Usage

Claude Code was used throughout this project — primarily for:
- Scaffolding boilerplate (pyproject.toml fields, `__init__.py` stubs)
- Generating the initial test cases, which I then reviewed and adjusted
- Drafting documentation text

The architecture, API design decisions, and exception hierarchy were designed by me; Claude accelerated execution of those decisions. I reviewed every generated file before keeping it.

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

**Chosen approach:** Option A — ip-api.com third-party API.

**Reasoning:**
- Zero setup: no account, no API key, no local files to download.
- 45 req/min on the free tier is sufficient for development and demo purposes.
- The response payload is rich and well-documented.

**Trade-offs vs. a local database (e.g., MaxMind GeoLite2):**

| | Third-party API | Local database |
|--|--|--|
| Setup | Zero | Requires download + periodic refresh |
| Latency | Network round-trip (20–100 ms) | Sub-millisecond |
| Rate limits | Yes (free tier) | None |
| Offline operation | No | Yes |
| Data freshness | Provider-managed | Manual updates required |
| Cost at scale | Paid tier or self-hosted | Free (GeoLite2) |

**Production recommendation:** For a high-throughput or latency-sensitive service, I would use a local database (MaxMind GeoLite2) bundled with an automated weekly refresh job. For a low-volume internal tool or MVP, a third-party API with a paid tier and circuit-breaker protection is quicker to operate.

---

## Production Readiness — What I Would Implement Next

1. **Caching** — Redis-backed cache keyed on IP address with a TTL of a few hours. Geolocation data rarely changes; caching would eliminate most upstream calls and eliminate rate-limit risk.

2. **Rate limiting** — A per-client rate limiter (e.g., `slowapi`) to protect the service itself, independent of the upstream provider's limits.

3. **Structured logging** — Replace implicit FastAPI access logs with structured JSON logs (using `structlog` or `python-json-logger`) that include request ID, IP, response time, and upstream status.

4. **Request ID propagation** — Generate a `X-Request-ID` header on every request and thread it through logs and error responses to make distributed tracing possible.

5. **Health check endpoint** — `GET /health` returning service version and upstream reachability, suitable for use as a Kubernetes liveness/readiness probe.

6. **Circuit breaker** — Wrap upstream calls with a circuit breaker (e.g., `circuitbreaker` library) to fail fast when ip-api.com is degraded, rather than queuing up timeouts.

7. **Input validation** — Validate the `{ip}` path parameter against an IPv4/IPv6 regex or `ipaddress.ip_address()` before hitting the upstream, returning a 400 immediately without a network call.

8. **Docker / container packaging** — A minimal `Dockerfile` (multi-stage, non-root user) and a `docker-compose.yml` for local development.

9. **CI pipeline** — GitHub Actions workflow running `ruff`, `mypy`, and `pytest` on every pull request with required status checks before merge.

10. **Observability** — Prometheus metrics endpoint (`/metrics`) exposing request counts, error rates, and upstream latency histograms. Paired with a Grafana dashboard for on-call visibility.
