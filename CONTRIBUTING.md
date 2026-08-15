# Contributing to FraudLens

Thanks for your interest in FraudLens! Bug reports, documentation, and pull requests are welcome.

## Getting started

1. Fork the repository and clone your fork.
2. Create a feature branch: `git checkout -b feature/amazing`.
3. Install dependencies: `pip install -r requirements.txt`.

## Development workflow

- Add or update tests for every change.
- Run the test suite:
  - `make test` — all tests
  - `make test-cov` — with coverage
  - `make test-integration` — integration tests only
- Verify the API boots with `make api` and the dashboard with `make dashboard`.

## Commit conventions

Keep commits small and focused. Prefix messages with a type, e.g. `feat:`, `fix:`, `docs:`, `test:`.

## Opening a pull request

1. Push your branch and open a PR against `main`.
2. Describe what you changed and why.
3. Link any related issue.

By contributing, you agree that your contributions are licensed under the MIT License.
