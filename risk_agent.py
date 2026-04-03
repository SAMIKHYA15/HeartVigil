import joblib
import numpy as np
import streamlit as st
import os
import pandas as pd
from typing import Dict, Tuple, List, Optional
from dotenv import load_dotenv

load_dotenv()

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

FEATURE_NAMES = [
    'age', 'sex', 'cp', 'trestbps', 'chol', 'fbs', 
    'restecg', 'thalach', 'exang', 'oldpeak', 'slope', 
    'ca', 'thal'
]

RISK_THRESHOLDS = {
    'low': 0.4,
    'medium': 0.65,
    'high': 1.0
}

FEATURE_DISPLAY_NAMES = {
    'age': 'Age',
    'sex': 'Sex',
    'cp': 'Chest Pain Type',
    'trestbps': 'Resting Blood Pressure',
    'chol': 'Cholesterol',
    'fbs': 'Fasting Blood Sugar',
    'restecg': 'Resting ECG',
    'thalach': 'Max Heart Rate',
    'exang': 'Exercise Angina',
    'oldpeak': 'ST Depression',
    'slope': 'ST Slope',
    'ca': 'Major Vessels',
    'thal': 'Thalassemia'
}

@st.cache_resource
def load_risk_model():
    try:
        if not os.path.exists('model.joblib') or not os.path.exists('scaler.joblib'):
            return None, None
        model = joblib.load('model.joblib')
        scaler = joblib.load('scaler.joblib')
        return model, scaler
    except Exception as e:
        print(f"Error loading model: {e}")
        return None, None

def prepare_features(form_data: Dict) -> np.ndarray:
    features = []
    for field in FEATURE_NAMES:
        value = form_data.get(field)
        if value is None or value == 'N/A' or value == '':
            value = 0.0
        try:
            features.append(float(value))
        except (ValueError, TypeError):
            features.append(0.0)
    return np.array(features).reshape(1, -1)

def scale_features(raw_features: np.ndarray, scaler) -> np.ndarray:
    try:
        return scaler.transform(raw_features)
    except Exception:
        return raw_features

def predict_risk_probability(scaled_features: np.ndarray, model) -> float:
    try:
        probabilities = model.predict_proba(scaled_features)
        return probabilities[0][1]
    except Exception:
        return 0.5

def get_risk_label(probability: float) -> Tuple[str, str]:
    if probability < RISK_THRESHOLDS['low']:
        return "LOW", "#10B981"
    elif probability < RISK_THRESHOLDS['medium']:
        return "MEDIUM", "#F59E0B"
    else:
        return "HIGH", "#EF4444"

def get_top_features(user_values: np.ndarray, model, scaler) -> List[int]:
    try:
        feature_importance = model.feature_importances_
        scaled_input = scaler.transform(user_values.reshape(1, -1))
        deviations = abs(scaled_input[0])
        weighted_scores = feature_importance * deviations
        top_indices = np.argsort(weighted_scores)[-3:][::-1]
        return top_indices.tolist()
    except Exception:
        return [0, 1, 2]

def explain_feature_traditional(field_name: str, value: float) -> str:
    explanations = {
        'age': f"Your age ({int(value)}) is a significant risk factor.",
        'sex': f"{'Male' if value == 1 else 'Female'} sex has baseline risk.",
        'cp': {0: "No chest pain detected — healthy sign.", 1: "Typical angina is a strong risk indicator.", 2: "Atypical angina suggests potential issues.", 3: "Non-cardiac pain warrants attention."},
        'trestbps': f"Blood pressure at {int(value)} mmHg.",
        'chol': f"Cholesterol at {int(value)} mg/dL.",
        'fbs': f"{'Fasting blood sugar is high' if value == 1 else 'Fasting blood sugar is normal'}.",
        'restecg': {0: "ECG appears normal.", 1: "Minor ECG abnormalities.", 2: "Significant ECG abnormalities."},
        'thalach': f"Max heart rate at {int(value)} bpm.",
        'exang': f"{'Chest pain during exercise' if value == 1 else 'No chest pain during exercise'}.",
        'oldpeak': f"ST depression of {value}.",
        'slope': {0: "Upsloping ST slope — healthy.", 1: "Flat ST slope.", 2: "Downsloping ST slope — concerning."},
        'ca': f"{int(value)} major vessels with blockages.",
        'thal': {1: "Normal thalassemia.", 2: "Fixed defect.", 3: "Reversible defect."}
    }
    
    if field_name in ['cp', 'restecg', 'slope', 'thal']:
        mapping = explanations.get(field_name, {})
        try:
            return mapping.get(int(value), f"Your {field_name} value: {value}")
        except (ValueError, TypeError):
            return f"Your {field_name} value: {value}"
    
    return explanations.get(field_name, f"Your {field_name} value: {value}")

def generate_explanations_traditional(user_values: np.ndarray, model, scaler) -> List[str]:
    top_indices = get_top_features(user_values, model, scaler)
    explanations = []
    for idx in top_indices:
        if idx < len(FEATURE_NAMES):
            field_name = FEATURE_NAMES[idx]
            value = user_values[0][idx] if idx < len(user_values[0]) else 0
            explanations.append(explain_feature_traditional(field_name, value))
    while len(explanations) < 3:
        explanations.append("Your health values suggest monitoring is recommended.")
    return explanations[:3]

def doctor_ai_agent(form_data: Dict) -> Dict:
    model, scaler = load_risk_model()
    
    if model is None or scaler is None:
        return {
            "probability": 50.0,
            "risk_label": "MEDIUM",
            "risk_color": "#F59E0B",
            "reasons": ["Model not loaded. Run train.py to generate model.joblib"],
            "ai_explanation": "Model training required.",
            "risk_direction": "first_submission",
            "prev_probability": None,
            "probability_change": None,
            "change_driver": None
        }
    
    raw_features = prepare_features(form_data)
    scaled_features = scale_features(raw_features, scaler)
    probability = predict_risk_probability(scaled_features, model)
    label, color = get_risk_label(probability)
    probability_percentage = probability * 100
    explanations = generate_explanations_traditional(raw_features, model, scaler)
    
    result = {
        "probability": probability_percentage,
        "risk_label": label,
        "risk_color": color,
        "reasons": explanations,
        "ai_explanation": f"Based on your health data, your heart disease risk is {probability_percentage:.1f}% ({label} risk).\n\n{explanations[0] if len(explanations) > 0 else ''}\n\n{explanations[1] if len(explanations) > 1 else ''}\n\n{explanations[2] if len(explanations) > 2 else ''}",
        "risk_direction": "first_submission",
        "prev_probability": None,
        "probability_change": None,
        "change_driver": None
    }
    
    return result


# ========== PHASE 2 ADDITION ==========
def explain_risk_change(current_result: Dict, delta: Dict) -> Dict:
    """
    Add risk direction and change explanation to the risk output.
    Called after doctor_ai_agent when delta has previous submission.
    """
    if not delta.get("has_previous", False):
        current_result["risk_direction"] = "first_submission"
        current_result["prev_probability"] = None
        current_result["probability_change"] = None
        current_result["change_driver"] = None
        return current_result
    
    # Get previous probability from stored risk_score in delta (needs to be fetched)
    # For now, we'll derive from fields or set to None
    prev_probability = delta.get("prev_risk_score", None)
    current_prob = current_result["probability"]
    
    if prev_probability is not None:
        change = current_prob - prev_probability
        current_result["prev_probability"] = prev_probability
        current_result["probability_change"] = change
        
        if change < -3:
            current_result["risk_direction"] = "improved"
        elif change > 3:
            current_result["risk_direction"] = "worsened"
        else:
            current_result["risk_direction"] = "stable"
        
        # Find change driver (biggest improvement or worsening)
        driver_field = None
        driver_change = 0
        driver_direction = None
        
        for field, field_data in delta.items():
            if field not in ["has_previous", "prev_risk_score"] and isinstance(field_data, dict):
                direction = field_data.get("direction")
                if direction in ["improved", "worsened"]:
                    change_amount = abs(field_data.get("change", 0)) if field_data.get("change") else 0
                    if change_amount > driver_change:
                        driver_change = change_amount
                        driver_field = field
                        driver_direction = direction
        
        if driver_field and driver_direction:
            display_name = FEATURE_DISPLAY_NAMES.get(driver_field, driver_field)
            if driver_direction == "improved":
                current_result["change_driver"] = f"Your {display_name} improved, contributing to your lower risk."
            else:
                current_result["change_driver"] = f"Your {display_name} worsened, increasing your risk."
    else:
        current_result["risk_direction"] = "first_submission"
        current_result["prev_probability"] = None
        current_result["probability_change"] = None
        current_result["change_driver"] = None
    
    return current_result