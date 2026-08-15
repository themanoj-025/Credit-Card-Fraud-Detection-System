# ADR 0001 — Remove AutoencoderDetector in Favor of Isolation Forest

**Date:** 2026-07-22
**Status:** Accepted

## Context

The codebase contained an `AutoencoderDetector` class in `src/fraudlens/models/anomaly.py`
that was never trained, never integrated into the serving pipeline, and dragged in
TensorFlow + Keras (~600MB of dependencies). The class existed in a half-built state:
present, untrained, dependency cost paid, no benefit realized.

Meanwhile, `IsolationForestDetector` in the same module was fully functional, trained
on legitimate transactions, integrated into the API serving path, and contributed
a real second anomaly signal alongside the supervised model.

## Decision

**Remove `AutoencoderDetector` entirely.** Keep `IsolationForestDetector` as the
sole unsupervised anomaly detector.

### Rationale

1. **Dependency cost:** TensorFlow + Keras add ~600MB to every Docker image and slow
   down `pip install` significantly. The serving Docker image (Phase 9) targets ~400MB;
   TensorFlow alone would blow that budget.

2. **No realized benefit:** The autoencoder was never trained on real data, never
   integrated into the prediction path, and had no evaluated performance metrics.
   Shipping unused code with heavy dependencies is technical debt, not a feature.

3. **Isolation Forest meets requirements:** Isolation Forest provides a strong
   unsupervised anomaly signal with:
   - No deep learning dependencies
   - Fast training (seconds vs minutes)
   - Fast inference (microseconds vs milliseconds)
   - Interpretable scores (distance from decision boundary)

4. **Simplicity wins:** One well-understood anomaly detector is better than two
   where one is untrained and untested. If deep learning anomaly detection is
   needed in the future, it can be added with a proper evaluation cycle.

5. **Portfolio signal:** "I evaluated two approaches, chose the simpler one that
   met requirements, and cut the unnecessary complexity" is a stronger signal than
   "I left both in the codebase hoping someone would finish the autoencoder later."

## Consequences

- `AutoencoderDetector` class removed from `src/fraudlens/models/anomaly.py`
- TensorFlow and Keras removed from `requirements.txt`
- Autoencoder-related config settings (`AUTOENCODER_ENCODING_DIM`, `AUTOENCODER_EPOCHS`,
  `AUTOENCODER_BATCH_SIZE`) removed from `src/fraudlens/config.py`
- Serving Docker image stays under 400MB target
- Any future deep learning anomaly detector can be added as a separate opt-in module
