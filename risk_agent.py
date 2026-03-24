import joblib
import pandas as pd
from ai_helper import get_ai_response

# Load model and scaler
model = joblib.load("model.joblib")
scaler = joblib.load("scaler.joblib")

FEATURE_ORDER = [
    "age", "sex", "cp", "trestbps", "chol",
    "fbs", "restecg", "thalach", "exang",
    "oldpeak", "slope", "ca", "thal"
]

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
    # Original ML explanation (top 3 features)
    features = FEATURE_ORDER
    pairs = list(zip(features, importances))
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
    # ML prediction
    df = pd.DataFrame([data])[FEATURE_ORDER]
    scaled = scaler.transform(df)
    prob = model.predict_proba(scaled)[0][1]
    label = get_risk_label(prob)
    importances = model.feature_importances_
    reasons = generate_explanations(data, importances)

    # AI enhancement: generate a friendly explanation
    prompt = f"""
    Patient data: age={data['age']}, BP={data['trestbps']}, cholesterol={data['chol']}, max HR={data['thalach']}, exercise angina={data['exang']}.
    ML model predicts {label} risk with {prob*100:.1f}% probability.
    Top reasons: {', '.join(reasons)}.
    Write a short, empathetic explanation of why the patient might be at this risk level and what they should do next.
    """
    ai_explanation = get_ai_response(prompt)

    return {
        "risk_label": label,
        "probability": round(prob * 100, 2),   # as percentage
        "reasons": reasons,
        "ai_explanation": ai_explanation or "No AI explanation available."
    }