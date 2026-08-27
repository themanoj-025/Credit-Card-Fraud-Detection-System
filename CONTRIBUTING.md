# Contributing to FraudLens

Thank you for your interest in contributing to FraudLens!

## Getting Started

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run the test suite (`pytest`)
5. Submit a pull request

## Development Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
pytest

# Run with coverage
pytest --cov=src/fraudlens --cov-report=html

# Run linting
ruff check .
mypy src/
```

## Code Standards

- **Python**: Follow PEP 8, enforced by `ruff`
- **Type Hints**: All functions must have return type annotations
- **Tests**: New features must include tests
- **Commit Messages**: Use conventional commits (`feat:`, `fix:`, `docs:`, etc.)

## Pull Request Process

1. Update documentation if needed
2. Add tests for new functionality
3. Ensure all CI checks pass
4. Request review from maintainers

## Reporting Issues

- Use GitHub Issues for bug reports
- Include reproduction steps
- Include environment details (Python version, OS)
