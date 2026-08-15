# FraudLens — File Move Ledger

## This pass (2026-08-11)

| Old path | New path | Category | Reason | Risk | Verified |
|---|---|---|---|---|---|
| `docs/migration_summary.md` | `docs/migration/migration_summary.md` | Meta/docs | Consolidate migration records under `docs/migration/` per enterprise standard | Low (docs only) | ✅ `git mv` preserved history; no inbound refs found |

## Prior pass (v5.0 modernization, commit `174b8d5`)

The v5.0 pass moved application code into the current layout. Its complete
file-move log is preserved at `docs/migration/migration_summary.md`
(§ File move log, § Import/reference update summary, § Verification report).

## Non-moves (documented decisions)

| Path | Decision | Reason |
|---|---|---|
| `src/fraudlens/**` | keep | src-layout core package (`PYTHONPATH=src` in Docker/CI) |
| `api/**`, `app/**` | keep | Framework interface layers; Docker/Compose/Makefile entry contract |
| `run_pipeline.py`, `train_and_compare.py` (root) | keep | Entry scripts referenced by path in Docker/CI/README |
| `notebooks/**`, `models/**`, `reports/**`, `infra/**`, `alembic/**`, `scripts/**`, `.dvc/` | keep | Canonical artifact/infra locations |
| `Dataset/` | keep (not tracked) | DVC-managed dataset |
| `fraudlens.db`, `.hypothesis/`, caches, `*.egg-info/` | leave (untracked) | Runtime/build artifacts, correctly gitignored |
