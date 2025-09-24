# app/app.py - FastAPI backend for car price prediction
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any
import joblib, os, json, csv, datetime
import pandas as pd
import numpy as np
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"msg": "API running"}


# ----------------------------
# CONFIG
# ----------------------------
MODEL_PATH = r"C:\Users\goutham\model_artifact\car_price_pipeline_lgbm_20250924_210822.joblib"
FEATURES_PATH = os.path.join("..", "model_artifact", "feature_names.json")
REQUEST_LOG = os.path.join("..", "data", "requests_log.csv")
OOR_LOG = os.path.join("..", "data", "oor_log.csv")
os.makedirs(os.path.join("..", "data"), exist_ok=True)

# Training ranges (from your dataset)
FEATURE_RANGES = {
    "Present_Price": (0.32, 92.6),
    "Kms_Driven": (500.0, 500000.0),
    "Car_Age": (2.0, 17.0)
}
KMS_PER_YEAR_RANGE = (0.0, 50000.0)

# ----------------------------
# Load model & feature names
# ----------------------------
if not os.path.exists(MODEL_PATH):
    raise RuntimeError(f"Model not found at {MODEL_PATH}")

try:
    model = joblib.load(MODEL_PATH)
except Exception as e:
    raise RuntimeError(f"Failed to load model: {e}")

if os.path.exists(FEATURES_PATH):
    with open(FEATURES_PATH) as f:
        FEATURE_NAMES = json.load(f)
else:
    FEATURE_NAMES = [
        "Present_Price", "Kms_Driven", "Car_Age", "Kms_per_Year",
        "Fuel_Type", "Seller_Type", "Transmission", "Owner"
    ]

# ----------------------------
# FastAPI setup
# ----------------------------
app = FastAPI(title="Car Price Predictor API")

# Allow frontend (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # change to your frontend URL in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------
# Schema
# ----------------------------
class Record(BaseModel):
    data: Dict[str, Any]

# ----------------------------
# Utility functions
# ----------------------------
def clamp_and_flag(row: Dict[str, Any]):
    """Clamp values to training ranges and return flags if out-of-range"""
    flags = {}
    for k, (mn, mx) in FEATURE_RANGES.items():
        if k in row:
            v = float(row[k])
            if v < mn:
                flags[k] = ("low", v, mn)
                row[k] = mn
            elif v > mx:
                flags[k] = ("high", v, mx)
                row[k] = mx
    if "Kms_per_Year" in row:
        v = float(row["Kms_per_Year"])
        mn, mx = KMS_PER_YEAR_RANGE
        if v < mn:
            flags["Kms_per_Year"] = ("low", v, mn)
            row["Kms_per_Year"] = mn
        elif v > mx:
            flags["Kms_per_Year"] = ("high", v, mx)
            row["Kms_per_Year"] = mx
    return row, flags


def log_request(filename, row, pred, flags):
    """Log each request and prediction into a CSV file"""
    header = list(row.keys()) + ["prediction", "timestamp", "flags"]
    exists = os.path.exists(filename)
    with open(filename, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not exists:
            writer.writerow(header)
        writer.writerow(
            [row.get(c, "") for c in row.keys()] +
            [pred, datetime.datetime.utcnow().isoformat(), json.dumps(flags)]
        )

# ----------------------------
# Routes
# ----------------------------
@app.get("/health")
def health():
    """Check service health"""
    return {"status": "ok", "model": os.path.basename(MODEL_PATH)}

@app.post("/predict")
def predict(record: Record):
    rec = record.data

    # Derived feature if missing
    if ("Kms_per_Year" not in rec) or (rec["Kms_per_Year"] in [0, None, ""]):
        kms = float(rec.get("Kms_Driven", 0))
        age = float(rec.get("Car_Age", 1))
        rec["Kms_per_Year"] = kms / max(1.0, age)

    # Clamp values and flag OOR
    rec_clamped, flags = clamp_and_flag(rec.copy())

    # Prepare dataframe for pipeline
    df = pd.DataFrame([{c: rec_clamped.get(c, np.nan) for c in FEATURE_NAMES}])

    # Predict
    try:
        pred = float(model.predict(df)[0])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {e}")

    # Log requests
    log_request(REQUEST_LOG, rec_clamped, pred, flags)
    if flags:
        log_request(OOR_LOG, rec_clamped, pred, flags)

    return {"prediction": pred, "reliability": "good" if not flags else "low", "flags": flags}
