# FraudLens — Old Tree → New Tree

## This pass (2026-08-11)

```
Before                                After
──────                                ─────
docs/migration_summary.md      →      docs/migration/migration_summary.md
—                                     docs/module_dependency.md        (new)
—                                     docs/startup_flow.md             (new)
—                                     docs/package_overview.md         (new)
—                                     docs/migration/old_tree_to_new_tree.md (new)
—                                     docs/migration/file_move_ledger.md     (new)
```

## Prior pass (v5.0 modernization, commit `174b8d5`)

FraudLens was restructured by the v5.0 pass into the current layout; its
record (scope, changes, file-move log, import updates, verification, risk,
needs-human-review) lives at `docs/migration/migration_summary.md`.
Tree-level view:

```
Before (flat)                         After (canonical)
──────                                ─────
*.py flat modules            →        src/fraudlens/ package
                                       ├── data/ · features/ · models/ · evaluation/
                                       ├── explainability/ · llm/ · monitoring/
                                       ├── retraining/ · prediction/ · persistence/
                                       ├── analysis/ · common/ · config.py
*.py API modules             →        api/ (main, providers, routers/, schemas, …)
*.py Streamlit modules       →        app/ (streamlit_app, pages/, components/)
*.py tests                   →        tests/ (27 modules)
*.ipynb                      →        notebooks/
*.pkl                        →        models/ (+ sha256 checksums)
k8s/grafana/prometheus       →        infra/
migrations                   →        alembic/versions/
dataset                      →        Dataset/ (DVC-managed)
```

## No-code-move rationale (this pass)

The layout already conforms (src-layout core, interface packages, canonical
artifact/infra dirs, root entries only). This pass only consolidates the
migration record and completes the Phase-6 doc suite — zero code changed.
