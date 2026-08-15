# 🔄 FraudLens — Resilience & Error Handling

## Overview

FraudLens implements a layered resilience strategy to ensure the API
degrades gracefully when dependencies fail. The goal is never to return
a 500 error that could have been a 503 with partial functionality.

## Resilience Layers

```
┌──────────────────────────────────────────────────────────────────┐
│                    RESILIENCE STRATEGY                           │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Layer 1: Circuit Breaker (LLM calls)                            │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │  Prevents cascading failures when Anthropic API is down   │    │
│  │  States: CLOSED → OPEN (3 failures) → HALF_OPEN (30s)    │    │
│  │  Cooldown multiplier: 2x on repeated open events          │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Layer 2: Retries with Backoff (LLM calls)                       │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │  Tenacity retry: 3 attempts                              │    │
│  │  Exponential backoff: 2s → 4s → 8s                      │    │
│  │  Applied to: Case Narrator, Chat Copilot                 │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Layer 3: Graceful Fallbacks                                     │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │  LLM down → template-based narrative (honest prefix)     │    │
│  │  Model not loaded → 503 with clear message               │    │
│  │  RAG index missing → 503 with setup instructions         │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Layer 4: Typed Exceptions                                       │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │  ModelNotLoadedError → 503                               │    │
│  │  LLMServiceUnavailable → 503                             │    │
│  │  PredictionError → 500 with original exception           │    │
│  │  RetrieverUnavailable → 503                              │    │
│  │  InvalidInputError → 422                                 │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Layer 5: RFC 7807 Error Format                                  │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │  All errors return consistent Problem Details format      │    │
│  │  Includes type, title, status, detail, errors             │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

## Circuit Breaker Details

The `LLMCircuitBreaker` in `api/exceptions.py` protects against cascading
LLM failures:

| Parameter | Default | Description |
| ----------- | --------- | ------------- |
| `failure_threshold` | 3 | Consecutive failures before opening |
| `recovery_timeout` | 30s | Wait time before half-open trial |
| `cooldown_multiplier` | 2.0 | Multiplier for timeout on repeated opens |
| `name` | "llm" | Identifier for logging |

**State Machine:**

```
CLOSED ──(3 failures)──→ OPEN ──(30s elapsed)──→ HALF_OPEN
  ↑                                                  │
  └──────────(success)───────────────────────────────┘
```

When the circuit is OPEN, LLM calls are blocked entirely — the case
narrator returns a template narrative and the chat endpoint returns
503 immediately.

## Retry Logic (Tenacity)

LLM API calls use tenacity for retry with exponential backoff:

| Parameter | Value |
| ----------- | ------- |
| Max attempts | 3 |
| Wait strategy | Exponential (2s, 4s, 8s) |
| Reraise | True (retries exhausted → exception propagates) |

**Affected code paths:**
- `CaseNarrator.narrate()` → Anthropic messages.create
- `Chat router /v1/chat` → Anthropic messages.create

## Typed Exceptions

| Exception | Status | When Raised |
| ----------- | -------- | ------------- |
| `ModelNotLoadedError` | 503 | Model not loaded at startup |
| `LLMServiceUnavailable` | 503 | LLM unreachable or circuit breaker open |
| `PredictionError` | 500 | Model prediction failure |
| `RetrieverUnavailable` | 503 | RAG index not built |
| `InvalidInputError` | 422 | Business rule validation failure |

All exceptions inherit from FastAPI's `HTTPException`, ensuring correct
status codes are returned without requiring custom exception handlers.

## Graceful Degradation Scenarios

### Scenario 1: LLM (Anthropic) is down

| Feature | Behavior |
| --------- | ---------- |
| `/v1/explain` | Returns SHAP values without narrative (narrative=null) |
| `/v1/chat` | Returns 503 with clear message |
| Case Narrator | Returns template-based narrative with "[Automated summary]" prefix |
| Everything else | Unaffected |

### Scenario 2: Model not loaded (no model artifact found)

| Feature | Behavior |
| --------- | ---------- |
| `/v1/predict` | Returns 503 "Model not loaded" |
| `/v1/explain` | Returns 503 "Model not loaded" |
| `/v1/chat` | Unaffected |
| `/v1/similar-cases` | Unaffected |
| `/health` | Returns 200 with model status: "degraded" |

### Scenario 3: Database unavailable

| Feature | Behavior |
| --------- | ---------- |
| `/health` | Returns 200 with database status: "degraded" |
| Prediction features | Still work (predictions are mostly stateless) |
| Feedback endpoints | Fail with 503 |

### Scenario 4: Circuit breaker opens (repeated LLM failures)

| Feature | Behavior |
| --------- | ---------- |
| `/v1/explain` | Template narrative (no LLM) |
| `/v1/chat` | Returns 503 "LLM temporarily unavailable" |
| Circuit breaker | Recovers after 30s + cooldown (CLOSED → OPEN → HALF_OPEN → CLOSED) |

## Honest Fallback Narratives

When the LLM is unavailable, the `CaseNarrator` produces a template-based
summary that clearly states it's not an LLM-generated narrative:

```
[Automated summary — narrative generation unavailable]
Transaction flagged as potentially fraudulent (92.3% confidence).
Top indicators: V14 (-5.23, increases), V4 (4.12, increases).
Recommended action: manual review by a fraud analyst.
```

The `[Automated summary — narrative generation unavailable]` prefix
ensures analysts are not misled by a confident-sounding but generic
fraud story.

## Testing Resilience

To manually test graceful degradation:

```bash
# Kill the LLM dependency (if running in Docker)
docker compose stop api  # Simulate API restart without model

# Check health reflects degraded state
curl http://localhost:8000/v1/health

# Verify 503 on prediction
curl -X POST http://localhost:8000/v1/predict -H "Content-Type: application/json" \
  -d '{"Time": 0, "Amount": 100}'  # Returns 503 with no model

# Verify 503 on chat
curl -X POST http://localhost:8000/v1/chat -H "Content-Type: application/json" \
  -d '{"message": "test"}'  # Returns 503 without ANTHROPIC_API_KEY
```

## Related Code

| File | Purpose |
| ------ | --------- |
| `api/exceptions.py` | Typed exceptions + circuit breaker |
| `api/errors.py` | RFC 7807 error handlers |
| `api/routers/chat.py` | Chat with retry + circuit breaker |
| `api/routers/explain.py` | Explain with typed exceptions |
| `src/fraudlens/llm/case_narrator.py` | LLM narrator with retry + circuit breaker |
