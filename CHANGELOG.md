# Changelog

All notable changes to FraudLens will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added
- Circuit breaker integration for LLM API calls in explain endpoint
- Retry logic with exponential backoff for LLM calls
- Structured logging with request IDs
- Rate limiting on all API endpoints
- API key authentication
- OpenAPI/Swagger documentation

### Changed
- Narrowed bare `except Exception` blocks across API layer
- Improved error handling with typed exceptions

### Fixed
- CORS configuration tightened
- SQL injection prevention via parameterized queries

## [1.0.0] - 2024-01-01

### Added
- Initial release
- Fraud prediction with XGBoost/Random Forest models
- SHAP-based explainability
- LLM-powered case narratives
- Analyst copilot chat interface
- RAG-based similar case retrieval
- Real-time monitoring dashboard
- Model retraining triggers
