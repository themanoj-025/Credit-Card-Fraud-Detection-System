# DEAD-WEIGHT PURGE v2.0 AUDIT REPORT

**Repository**: `Credit Card Fraud Detection`  
**Mode**: `AUDIT_ONLY` (Zero repository modifications performed)  
**Baseline Commit SHA**: `738c88413ca347edb4c51defc6b545456759132a`  
**Audit Date**: 2026-10-11  
**Verdict**: **YELLOW** (Dead weight detected; review recommended)

---

## 1. Executive Summary

- **Tracked Files in Git**: 238
- **Untracked Local Files**: 0
- **Total LOC**: 33,006
- **Analyzed Size**: 1.14 MB
- **Total Dead-Weight Candidates Identified**: 103
  - **Tier 0 (Provable Junk/Empty)**: 63
  - **Tier 1 (High Confidence)**: 0
  - **Tier 2 (Medium / Needs Verification)**: 38
  - **Tier 3 (Protected / Hard Vetoed)**: 2

## 2. Findings by Category

| Category | Description | Count |
|---|---|---|
| **A** | Empty & Near-Empty Files | 5 |
| **C** | Junk / Caches / Build Artifacts | 60 |
| **D** | Potential Orphan Modules | 38 |
| **H** | Exact Hash Duplicates | 0 |

### Top Tier-0 Items (Provable Deletion Candidates if EXECUTE_SAFE were used):
- [`A`] `app/py.typed`: 0-byte file with no content
- [`A`] `py.typed`: 0-byte file with no content
- [`A`] `src/py.typed`: 0-byte file with no content
- [`C`] `.cleanup-audit/`: Untracked build/dependency/cache artifact directory in workspace
- [`C`] `.cleanup-audit/.claude/`: Untracked build/dependency/cache artifact directory in workspace
- [`C`] `.coverage`: Untracked build/dependency/cache artifact directory in workspace
- [`C`] `.dvc/cache/`: Untracked build/dependency/cache artifact directory in workspace
- [`C`] `.dvc/config.local`: Untracked build/dependency/cache artifact directory in workspace
- [`C`] `.dvc/tmp/`: Untracked build/dependency/cache artifact directory in workspace
- [`C`] `.github/scripts/__pycache__/`: Untracked build/dependency/cache artifact directory in workspace
- [`C`] `.hypothesis/`: Untracked build/dependency/cache artifact directory in workspace
- [`C`] `.mypy_cache/`: Untracked build/dependency/cache artifact directory in workspace
- [`C`] `.pytest_cache/`: Untracked build/dependency/cache artifact directory in workspace
- [`C`] `.ruff_cache/`: Untracked build/dependency/cache artifact directory in workspace
- [`C`] `AGENTS.md`: Untracked build/dependency/cache artifact directory in workspace
_...and 48 more listed in `manifest.csv`._

## 3. Next Steps & Recommended Actions

1. Review `.purge-reports/manifest.csv` and `.purge-reports/FLAGGED.md`.
2. If safe cleanup is desired, configure `MODE: EXECUTE_SAFE` or generate an approval `PLAN.yaml`.
3. Verify that all untracked artifacts (`__pycache__`, `.venv`, `.pytest_cache`) are properly covered in `.gitignore`.
