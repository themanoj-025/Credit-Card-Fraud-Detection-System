# SecurityAndCompliance — FraudLens: Security & Compliance

| Field | Value |
| --- | --- |
| Version | v0.1 |
| Last Updated | 2026-08-06 |
| Owner | Security Engineer |
| Status | In Review |

---

## 1. Threat Model (STRIDE)

| Threat | Surface | Impact | Mitigation |
| --- | --- | --- | --- |
| Spoofing | API key forgery | Model abuse | API key auth + rate limits |
| Tampering | Request features | Wrong scores | Pydantic validation |
| Repudiation | Model promotion | Ungoverned changes | Governance + audit trail |
| Info disclosure | Card data | PCI breach | Masking, data minimization |
| DoS | Predict flood | Cost/outage | Rate limiting |
| Elevation | Admin actions | Governance bypass | Role separation (dashboard) |

## 2. Auth / Authorization

- API: static API key (`SPAM_API_KEY`-style) with dev-mode fallback.
- Dashboard: per-page access (governance = admin).
- Human-in-the-loop for promotions (cannot be automated).

## 3. Data Classification

| Data | Class | Handling |
| --- | --- | --- |
| Card number | PCI | mask `****1234`; never log full |
| Transaction amounts | financial | access-controlled |
| SHAP values | internal | — |
| LLM chat | case data | redacted PII before send |
| Model artifacts | internal | MLflow access-controlled |

## 4. Encryption Standards

- In transit: TLS.
- At rest: DB encryption via hosting (PostgreSQL); keys in env/secret manager.

## 5. Compliance Checklist

- [ ] Card data masked everywhere
- [ ] PII minimized in LLM inputs
- [ ] Model governance audit trail
- [ ] Dependency scans (Dependabot)
- [ ] Rate limits on all endpoints
- [ ] GDPR: no unnecessary PII collection

## 6. Incident Response Plan (outline)

1. Detect: metrics/alert spike.
2. Triage: data leak vs availability.
3. Contain: revoke API key / disable endpoint.
4. Remediate: patch + tests.
5. Recover: re-enable + rotate keys.
6. Postmortem: blameless writeup.

## 7. Related Documents

| Document | Relationship |
| --- | --- |
| [Rules.md](../project/Rules.md) | Security baseline |
| [API.md](API.md) | Auth + limits |
| [Schema.md](Schema.md) | Sensitive map |
| [TechSpec.md](TechSpec.md) | Security NFRs |
| [PRD.md](../product/PRD.md) | Goals |
| [AppFlow.md](../design/AppFlow.md) | Flows |
| [Design.md](../design/Design.md) | Design |
| [ImplementationPlan.md](../project/ImplementationPlan.md) | Tasks |
| [Tracker.md](../project/Tracker.md) | Status |
| [Testing.md](Testing.md) | Security tests |
| [Deployment.md](Deployment.md) | Secret mgmt |
| [Glossary.md](../reference/Glossary.md) | Vocabulary |
| [RiskRegister.md](../project/RiskRegister.md) | Risks |
