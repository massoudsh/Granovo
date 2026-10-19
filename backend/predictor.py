import hashlib
import json
import math

from fastapi import HTTPException

OUTPUTS = ("temperature_c", "screw_rpm", "pressure_bar")


def predict(rows, material):
    ordered = sorted(rows, key=lambda row: (row["produced_on"], row["id"]))
    if len(ordered) < 8:
        raise HTTPException(409, "At least 8 quality-verified, sub-5% reject batches for this machine/polymer are required")
    for key in ("purity_pct", "moisture_pct"):
        if not min(r[key] for r in ordered) <= material[key] <= max(r[key] for r in ordered):
            raise HTTPException(409, "Material is outside the recorded training range; no recommendation generated")

    def estimate(training, target):
        nearest = sorted(training, key=lambda row: math.hypot(
            (row["purity_pct"] - target["purity_pct"]) / 100,
            (row["moisture_pct"] - target["moisture_pct"]) / 100,
        ))[:3]
        return {key: round(sum(r[key] for r in nearest) / len(nearest), 2) for key in OUTPUTS}

    split = max(6, int(len(ordered) * 0.8))
    training, holdout = ordered[:split], ordered[split:]
    errors = [estimate(training, row) for row in holdout]
    mae = {key: round(sum(abs(row[key] - error[key]) for row, error in zip(holdout, errors)) / len(holdout), 2) for key in OUTPUTS}
    digest = hashlib.sha256(json.dumps([
        {key: row[key] for key in ("id", "purity_pct", "moisture_pct", *OUTPUTS)}
        for row in ordered
    ], sort_keys=True).encode()).hexdigest()[:16]
    return {
        "model_version": "knn3-v1-" + digest,
        "training_count": len(ordered),
        "holdout_count": len(holdout),
        "holdout_mae": mae,
        "settings": estimate(ordered, material),
        "warning": "Experimental historical-neighbor estimate, not a validated process model. Operator approval is mandatory; no machine control.",
    }
