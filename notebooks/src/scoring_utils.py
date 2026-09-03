"""Stable scoring wrappers used by the final transaction-fraud handoff.

The base estimator is already trained in Notebook 04.  Notebook 05 may fit a
one-dimensional calibrator on validation scores, but it must never refit the
base preprocessing or classifier.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np


def probability_to_logit(probability: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    """Convert probabilities to a finite, two-dimensional logit array."""
    probability = np.asarray(probability, dtype=float)
    clipped = np.clip(probability, eps, 1.0 - eps)
    return np.log(clipped / (1.0 - clipped)).reshape(-1, 1)


@dataclass
class CalibratedFraudPipeline:
    """Frozen preprocessing/model pipeline followed by an optional calibrator.

    ``calibrator`` must expose ``predict_proba`` (Platt/logistic) or ``predict``
    (isotonic).  ``None`` keeps the original model probability unchanged.
    """

    base_pipeline: Any
    calibrator: Any
    feature_names: Sequence[str]
    model_version: str
    calibration_method: str = "raw"

    def _raw_probability(self, X: Any) -> np.ndarray:
        return np.asarray(
            self.base_pipeline.predict_proba(X[list(self.feature_names)])[:, 1],
            dtype=float,
        )

    def predict_fraud_probability(self, X: Any) -> np.ndarray:
        raw = self._raw_probability(X)
        if self.calibrator is None or self.calibration_method == "raw":
            return raw

        logits = probability_to_logit(raw)
        if hasattr(self.calibrator, "predict_proba"):
            calibrated = self.calibrator.predict_proba(logits)[:, 1]
        else:
            calibrated = self.calibrator.predict(logits.ravel())
        return np.clip(np.asarray(calibrated, dtype=float), 0.0, 1.0)

    def predict_proba(self, X: Any) -> np.ndarray:
        fraud_probability = self.predict_fraud_probability(X)
        return np.column_stack([1.0 - fraud_probability, fraud_probability])

    def risk_score(self, X: Any) -> np.ndarray:
        return 100.0 * self.predict_fraud_probability(X)

    def predict(self, X: Any, threshold: float = 0.5) -> np.ndarray:
        return (self.predict_fraud_probability(X) >= threshold).astype(int)
