# FraudLens (Credit Card Fraud Detection) — Documentation Index

Single home for all FraudLens documentation. FraudLens is a credit card fraud
detection platform with an ML pipeline (FeatureEngineer, Optuna-tuned models,
audited training/inference), a REST API, and graceful-degradation resilience.

**Start here:** [architecture.md](architecture.md) (system map) →
[folder_structure.md](folder_structure.md) (repo tree) →
[technical/TechSpec.md](technical/TechSpec.md) (build details).

## Structure

```
docs/
├── README.md                      ← this index
├── architecture.md                system architecture
├── folder_structure.md            repository + docs tree
├── module_dependency.md           dependency graph
├── package_overview.md            module inventory
├── startup_flow.md                boot + pipeline flow
├── community/
│   ├── CHANGELOG.md               changelog
│   ├── CODE_OF_CONDUCT.md         code of conduct
│   ├── CONTRIBUTING.md            contribution guide
│   └── SECURITY.md                security policy
├── decisions/
│   ├── 0000-baseline.md           baseline audit snapshot
│   └── 0001-remove-autoencoder.md ADR: remove autoencoder path
├── design/
│   ├── AppFlow.md                 app screens / states / flows
│   └── Design.md                  design decisions
├── product/
│   └── PRD.md                     product requirements
├── project/
│   ├── analysis_report.md         repo inventory & classification
│   ├── ImplementationPlan.md      implementation plan
│   ├── RiskRegister.md            risks & mitigations
│   ├── Rules.md                   engineering rules
│   └── Tracker.md                 status tracker
├── reference/
│   ├── Glossary.md                terminology
│   ├── MODEL_CARD.md              model card (features, training, limits)
│   └── RESILIENCE.md              graceful-degradation scenarios
├── technical/
│   ├── API.md                     endpoint reference
│   ├── Deployment.md              deployment guide
│   ├── Schema.md                  data model
│   ├── SecurityAndCompliance.md   security baseline
│   ├── TechSpec.md                technical spec
│   └── Testing.md                 test strategy
├── migration/
│   ├── migration_summary.md       modernization record
│   ├── old_tree_to_new_tree.md    restructure before/after
│   └── file_move_ledger.md        file-move ledger
└── audit/
    ├── cleanup-audit-2026-08-13.md  previous cleanup audit
    └── cleanup-audit-2026-08-15.md  docs de-LLM-ification audit
```

## Guidance

| You want... | Read |
|---|---|
| How the platform works end-to-end | [architecture.md](architecture.md) |
| Model details & limits | [reference/MODEL_CARD.md](reference/MODEL_CARD.md) |
| Degradation behavior | [reference/RESILIENCE.md](reference/RESILIENCE.md) |
| API surface | [technical/API.md](technical/API.md) |
| Deployment | [technical/Deployment.md](technical/Deployment.md) |
| Audit history & decisions | [decisions/0000-baseline.md](decisions/0000-baseline.md) |
| What's shipped / next | [project/Tracker.md](project/Tracker.md) |
| Risks & follow-ups | [project/RiskRegister.md](project/RiskRegister.md) |
