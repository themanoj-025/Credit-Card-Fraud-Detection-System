# Security Policy

## Supported Versions

| Version | Supported |
| --------- | ----------- |
| 2.0.x | ✅ Active development |
| < 2.0 | ❌ Not supported |

## Reporting a Vulnerability

If you discover a security vulnerability in FraudLens, please:

1. **Do NOT** open a public GitHub issue.
2. Email details to the project maintainers (see GitHub profile).
3. Include a description of the vulnerability, steps to reproduce, and potential impact.

You can expect:
- Acknowledgment within 48 hours
- A timeline for the fix within 5 business days
- Credit in the release notes (if desired)

## Security Audit Checklist

The following items have been addressed in the project's security hardening:

### Authentication & Authorization
- [x] API key authentication via `X-API-Key` header (FastAPI `Depends()`)
- [x] Two key tiers: `admin` and `readonly`
- [x] Keys stored as SHA-256 hashes, never in plaintext
- [x] Keys generated with `secrets.token_hex(24)` (cryptographically random)
- [x] Admin-only endpoints for key management (`POST/GET /v1/auth/keys`)
- [x] Admin key guarded by required `ADMIN_API_KEY` env var
- [ ] OAuth2/JWT upgrade path documented in ADR

### Rate Limiting
- [x] `slowapi` middleware on all endpoints
- [x] Per-endpoint configurable limits:
  - `/v1/predict`: 100/minute
  - `/v1/predict/batch`: 30/minute
  - `/v1/chat`: 20/minute (LLM cost protection)
  - `/v1/explain`: 60/minute
  - `/v1/auth/keys` POST: 10/hour (admin security)
- [x] Redis-backed in production; in-memory fallback for dev
- [x] Configurable via `REDIS_URL` environment variable
- [x] **Multi-worker safety proven:** `tests/test_rate_limit_shared.py` contains
  integration tests verifying that two separate `Limiter` instances sharing the
  same Redis backend correctly share counter state. The test also includes a
  negative check proving that separate in-memory limiters diverge (confirming
  the positive test is not a false positive). Run with:
  ```bash
  REDIS_URL=redis://localhost:6379/0 pytest tests/test_rate_limit_shared.py -v
  ```

### Input Validation
- [x] All endpoints use Pydantic models for request bodies
- [x] Field-level validation: `Amount >= 0`, `Time` ranges
- [x] NaN/Inf explicitly rejected with 422 via custom Pydantic validators
- [x] `min_length`/`max_length` constraints on batch inputs (1–1000)
- [x] Batch prediction validates column ordering against model expectations
- [x] Query parameter bounds checked (`top_k`, `limit`, `cursor`)

### Secrets Management
- [x] Secrets loaded from environment variables / `.env` file
- [x] `.env.example` documents all required secrets
- [x] `python-dotenv` for local development
- [ ] AWS Secrets Manager / Docker secrets documented for production

### Transport & Headers
- [x] CORS restricted to explicit origins (no `*`):
  - `http://localhost:8000`, `http://127.0.0.1:8000`
  - `http://localhost:8501`, `http://127.0.0.1:8501`
- [x] `X-Content-Type-Options: nosniff`
- [x] `X-Frame-Options: DENY`
- [x] `X-XSS-Protection: 0` (modern CSP supersedes)
- [x] `Strict-Transport-Security: max-age=31536000; includeSubDomains`
- [x] `Cache-Control: no-store, no-cache, must-revalidate` on all responses
- [x] `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'`
- [x] `Permissions-Policy: camera=(), microphone=(), geolocation=()`
- [x] `Referrer-Policy: strict-origin-when-cross-origin`
- [ ] TLS termination via reverse proxy (Caddy/Nginx) in docker-compose

### Model Security
- [x] SHA-256 checksum verification on model files (`ModelLoader._verify_checksum`)
- [x] Checksums auto-generated on first load (`.pkl.sha256` file)
- [x] ModelLoadError raised on checksum mismatch (tamper detection)
- [x] Models loaded from a trusted, write-protected volume (`models/`)
- [ ] ONNX export for safer serving path (future)

### Infrastructure
- [x] MLflow as opt-in `--profile training` (not exposed by default)
- [x] Container image scanning (Trivy) in CI (fails on CRITICAL/HIGH)
- [x] Secrets never baked into Docker images (passed via env vars)
- [x] K8s Secret manifest templated (never committed with real values)
- [x] K8s ingress TLS termination configured
- [x] Multi-stage Docker: train stage excluded from serve image
- [x] Docker HEALTHCHECK with reasonable intervals/timeouts

### CI/CD Security
- [x] Lint runs before tests (catches issues early)
- [x] Tests run before build (fails fast)
- [x] Trivy scan runs before deploy (prevents vulnerable images)
- [x] Deploy only on main/master branch (not on PRs)
- [x] GHCR as private registry with GITHUB_TOKEN auth

## Disclosure Policy

We follow coordinated disclosure: vulnerabilities are reported privately,
fixed in a patch release, and publicly disclosed 30 days after the fix
is released.
