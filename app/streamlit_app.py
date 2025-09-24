# app/streamlit_app.py
import streamlit as st
import pandas as pd
import joblib, os, json, datetime, csv
import numpy as np
from pathlib import Path

# ------------------------
# Path setup
# ------------------------
THIS_DIR = Path(__file__).resolve().parent       # -> app/
PROJECT_ROOT = THIS_DIR.parent                   # -> project root
MODEL_PATH = Path(r"C:\Users\goutham\model_artifact\car_price_pipeline_lgbm_20250924_210822.joblib")

FEATURES_PATH = PROJECT_ROOT / "model_artifact" / "feature_names.json"
OOR_LOG = PROJECT_ROOT / "data" / "oor_log.csv"

# ------------------------
# Feature ranges (from training data)
# ------------------------
FEATURE_RANGES = {
    "Present_Price": (0.32, 92.6),
    "Kms_Driven": (500.0, 500000.0),
    "Car_Age": (2.0, 17.0)
}
KMS_PER_YEAR_RANGE = (0.0, 50000.0)

# ------------------------
# Streamlit UI
# ------------------------
st.set_page_config(page_title="Car Price Prediction", layout="centered")
st.title("🚗 Car Price Prediction (local model)")

# ------------------------
# Load model
# ------------------------
if not MODEL_PATH.exists():
    st.error(f"Could not load model: {MODEL_PATH}")
    st.stop()

try:
    model = joblib.load(MODEL_PATH)
except Exception as e:
    st.error(f"Model load failed: {e}")
    st.stop()

# Load feature names
if FEATURES_PATH.exists():
    with open(FEATURES_PATH) as f:
        FEATURE_NAMES = json.load(f)
else:
    FEATURE_NAMES = [
        "Present_Price", "Kms_Driven", "Car_Age", "Kms_per_Year",
        "Fuel_Type", "Seller_Type", "Transmission", "Owner"
    ]

# ------------------------
# Sidebar inputs
# ------------------------
st.sidebar.header("Inputs")
present_price = st.sidebar.number_input("Present Price (lakhs)", value=5.0, min_value=0.0, step=0.1)
kms_driven = st.sidebar.number_input("Kms Driven", value=45000, min_value=0, step=1000)
car_age = st.sidebar.number_input("Car Age (years)", value=5, min_value=0, step=1)
fuel_type = st.sidebar.selectbox("Fuel Type", ["Petrol", "Diesel", "CNG"])
seller_type = st.sidebar.selectbox("Seller Type", ["Individual", "Dealer"])
transmission = st.sidebar.selectbox("Transmission", ["Manual", "Automatic"])
owner = st.sidebar.selectbox("Owner", [0, 1, 2, 3])

# ------------------------
# Prediction logic
# ------------------------
if st.button("Predict"):
    # Derived feature
    kms_per_year = kms_driven / max(1.0, car_age) if car_age > 0 else 0.0

    # Build row
    row = {
        "Present_Price": float(present_price),
        "Kms_Driven": int(kms_driven),
        "Car_Age": int(car_age),
        "Kms_per_Year": float(kms_per_year),
        "Fuel_Type": fuel_type,
        "Seller_Type": seller_type,
        "Transmission": transmission,
        "Owner": int(owner)
    }

    # Clamp to training ranges + flags
    flags = {}
    for k, (mn, mx) in FEATURE_RANGES.items():
        v = float(row[k])
        if v < mn:
            flags[k] = ("low", v, mn); row[k] = mn
        elif v > mx:
            flags[k] = ("high", v, mx); row[k] = mx

    if not (KMS_PER_YEAR_RANGE[0] <= row["Kms_per_Year"] <= KMS_PER_YEAR_RANGE[1]):
        flags["Kms_per_Year"] = ("oor", row["Kms_per_Year"], KMS_PER_YEAR_RANGE)

    # Predict
    df = pd.DataFrame([{c: row.get(c, np.nan) for c in FEATURE_NAMES}])
    pred = float(model.predict(df)[0])

    # Display
    st.success(f"Predicted Selling Price: {pred:.2f} lakhs")
    st.write("Reliability:", "✅ Good" if not flags else "⚠️ Low (OOR)")

    if flags:
        st.warning("⚠️ Flags: " + str(flags))

        # Log out-of-range inputs
        os.makedirs(OOR_LOG.parent, exist_ok=True)
        header = list(row.keys()) + ["prediction", "timestamp", "flags"]
        exists = OOR_LOG.exists()
        with open(OOR_LOG, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if not exists:
                w.writerow(header)
            w.writerow([
                row[k] for k in row.keys()
            ] + [pred, datetime.datetime.utcnow().isoformat(), json.dumps(flags)])
