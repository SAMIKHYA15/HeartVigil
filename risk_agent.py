import joblib
import pandas as pd

# Load model and scaler
model = joblib.load("model.joblib")
scaler = joblib.load("scaler.joblib")

# Must match training dataset EXACTLY
FEATURE_ORDER = [
    "age", "sex", "cp", "trestbps", "chol",
    "fbs", "restecg", "thalach", "exang",
    "oldpeak", "slope", "ca", "thal"
]

# Safe ranges (used for explanations)
SAFE_RANGES = {
    "trestbps": (90, 120),
    "chol": (125, 200),
    "thalach": (100, 170),
    "oldpeak": (0.0, 2.0)
}


def get_risk_label(prob):
    if prob < 0.4:
        return "LOW"
    elif prob < 0.65:
        return "MEDIUM"
    else:
        return "HIGH"


def generate_explanations(data, importances):
    features = FEATURE_ORDER

    # Pair features with importance
    pairs = list(zip(features, importances))

    # Top 3 features
    top_features = sorted(pairs, key=lambda x: x[1], reverse=True)[:3]

    reasons = []

    for feature, _ in top_features:
        value = data[feature]

        if feature in SAFE_RANGES:
            low, high = SAFE_RANGES[feature]

            if value > high:
                reasons.append(f"{feature} is above safe range ({value})")
            elif value < low:
                reasons.append(f"{feature} is below safe range ({value})")
            else:
                reasons.append(f"{feature} is within normal range")
        else:
            reasons.append(f"{feature} significantly influences prediction")

    return reasons


def doctor_ai_agent(data):
    """
    Main Doctor AI function:
    - Takes user input
    - Returns risk label, probability, and explanations
    """

    # Convert to DataFrame with correct feature order
    df = pd.DataFrame([data])[FEATURE_ORDER]

    # Scale input
    scaled = scaler.transform(df)

    # Predict probability
    prob = model.predict_proba(scaled)[0][1]

    # Get risk label
    label = get_risk_label(prob)

    # Get feature importance
    importances = model.feature_importances_

    # Generate explanations
    reasons = generate_explanations(data, importances)

    return {
        "risk_label": label,
        "probability": round(prob * 100, 2),
        "reasons": reasons
    }