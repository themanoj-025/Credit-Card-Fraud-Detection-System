# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

1. **Do NOT** open a public GitHub issue for security vulnerabilities.
2. Email the maintainers with details of the vulnerability.
3. Include steps to reproduce the issue.
4. Allow reasonable time for a fix before public disclosure.

## Security Measures

- **API Key Authentication**: All API endpoints require Bearer token authentication.
- **Rate Limiting**: All endpoints are rate-limited per IP to prevent abuse.
- **Input Validation**: Pydantic models validate all inputs before processing.
- **Circuit Breakers**: LLM API calls use circuit breakers to prevent cascading failures.
- **Structured Logging**: All security events are logged with request IDs for audit trails.
- **No Hardcoded Secrets**: All secrets are loaded from environment variables.
- **SQL Injection Prevention**: All database queries use parameterized statements.
