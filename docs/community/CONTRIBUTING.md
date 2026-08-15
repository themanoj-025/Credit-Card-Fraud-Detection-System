# Contributing to FraudLens

First off, thank you for considering contributing to FraudLens! 🎉

This document provides guidelines and instructions for contributing. Following these helps maintain a high-quality, production-grade project that the whole community can benefit from.

## Code of Conduct

This project adheres to the [Contributor Covenant](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

## Quick Start for Contributors

```bash
# 1. Fork & clone
git clone https://github.com/yourusername/credit-card-fraud-detection.git
cd credit-card-fraud-detection

# 2. Set up environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
make install
make install-dev

# 4. Set up pre-commit hooks
pre-commit install

# 5. Run tests to verify everything works
make test
```

## Development Workflow

### 1. Create a Branch

```bash
git checkout -b feat/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

Use conventional branch naming:
- `feat/` — new features
- `fix/` — bug fixes
- `refactor/` — code refactoring
- `docs/` — documentation only
- `test/` — adding or fixing tests
- `chore/` — maintenance tasks

### 2. Make Changes

- Write clean, typed Python (we use `mypy --strict` on core packages)
- Follow existing patterns and conventions in the codebase
- Add or update tests for your changes
- Update documentation as needed (README, ADRs, model card)

### 3. Run Checks Locally

```bash
# Format code
make format

# Lint (must pass)
make lint

# Run tests (must pass, coverage ≥ 85%)
make test-cov

# Type-check (mypy on core packages)
mypy src/fraudlens/prediction src/fraudlens/explainability api/
```

### 4. Commit

Write clear, conventional commit messages:

```bash
git commit -m "feat: add batch prediction with progress tracking"
git commit -m "fix: handle NaN values in prediction input"
git commit -m "docs: update API reference with new endpoints"
```

### 5. Push and Open a PR

```bash
git push origin feat/your-feature-name
```

Then open a pull request against `main`. Fill out the [PR template](../../.github/PULL_REQUEST_TEMPLATE.md) completely.

## Coding Standards

### Python Style

- **Formatter:** `black` with default settings (88 char line length)
- **Imports:** `isort` with black-compatible settings
- **Linter:** `ruff` with the rules defined in `pyproject.toml`
- **Types:** `mypy --strict` on core packages (`prediction/`, `explainability/`, `api/`)

### Naming Conventions

| Element | Convention | Example |
| --------- | ----------- | --------- |
| Packages | `lowercase` | `fraudlens.models` |
| Modules | `lowercase_with_underscores` | `case_narrator.py` |
| Classes | `PascalCase` | `FraudPredictor` |
| Functions | `snake_case` | `predict_transaction()` |
| Constants | `UPPER_CASE` | `AVG_FRAUD_LOSS` |
| Private | `_leading_underscore` | `_verify_checksum()` |

### Imports Ordering

1. Standard library (e.g., `os`, `json`)
2. Third-party (e.g., `fastapi`, `xgboost`)
3. First-party (e.g., `src.fraudlens.config`)

Within each group, sort alphabetically.

### Error Handling

- Use typed exceptions from `api/exceptions.py`
- Never use bare `except:` — always catch specific exceptions
- Log errors with correlation IDs via `structlog`
- Return RFC 7807 Problem Details for API errors

### Testing

- Write tests for every new function or class
- Aim for ≥ 85% coverage
- Use fixtures from `conftest.py` where possible
- Mock external services (Anthropic) with `respx`/`httpx`
- Test edge cases: empty inputs, boundary values, NaN/Inf, auth failures

## Adding New Endpoints

1. Create a new router in `api/routers/`
2. Add Pydantic models in `api/schemas.py`
3. Wire the router in `api/main.py`
4. Add rate limiting configuration
5. Add tests (unit + integration + contract)
6. Add examples in `README.md` / `api-map.md`
7. Consider adding ADR if the change is architecturally significant

## Architecture Decision Records (ADRs)

Significant architectural decisions should be documented as ADRs in `docs/adr/`:

```markdown
# ADR NNNN — Title

**Date:** YYYY-MM-DD
**Status:** Proposed | Accepted | Deprecated | Superseded

## Context
What is the issue motivating this decision?

## Decision
What is the change being made?

## Consequences
Why is this a good/bad idea? What trade-offs exist?
```

## Pull Request Review Criteria

Your PR will be reviewed against these criteria:

1. **Correctness** — Does it work? Are tests passing?
2. **Type safety** — Does `mypy` pass on affected packages?
3. **Coverage** — Are new features tested? Coverage ≥ 85%?
4. **Documentation** — Are ADRs, README, and API docs updated?
5. **Performance** — Are there any obvious performance concerns?
6. **Security** — Are inputs validated? Are secrets handled correctly?
7. **Consistency** — Does it follow existing patterns and conventions?

## Questions or Problems?

- Open a [GitHub Issue](https://github.com/yourusername/credit-card-fraud-detection/issues)
- Tag with appropriate labels (bug, enhancement, question, etc.)
