from supabase_client import supabase
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Tuple
from ai_helper import get_ai_response

def get_user_history(user_id: str, start_date: str = None, end_date: str = None) -> List[Dict]:
    query = supabase.table("health_records")\
        .select("*")\
        .eq("user_id", user_id)\
        .order("created_at", desc=False)
    if start_date:
        query = query.gte("created_at", start_date)
    if end_date:
        query = query.lte("created_at", end_date)
    response = query.execute()
    return response.data

def compute_trends(records: List[Dict], field: str) -> Tuple[float, float, str]:
    if len(records) < 2:
        return None, 0, "→"
    values = [rec.get(field) for rec in records if rec.get(field) is not None]
    if len(values) < 2:
        return None, 0, "→"
    latest = values[-1]
    first = values[0]
    if first == 0:
        percent_change = 0
    else:
        percent_change = ((latest - first) / first) * 100
    symbol = "↑" if percent_change > 0 else "↓" if percent_change < 0 else "→"
    return latest, percent_change, symbol

def generate_comparison_data(record: Dict) -> List[Dict]:
    safe_limits = {
        "trestbps": ("Resting BP (mmHg)", 120, "lower"),
        "chol": ("Cholesterol (mg/dL)", 200, "lower"),
        "thalach": ("Max Heart Rate (bpm)", 150, "higher"),
        "oldpeak": ("ST Depression", 1.0, "lower")
    }
    chart_data = []
    for field, (label, limit, direction) in safe_limits.items():
        val = record.get(field)
        if val is not None:
            chart_data.append({
                "Field": label,
                "Your Value": val,
                "Safe Limit": limit,
                "Direction": direction
            })
    return chart_data

def generate_trend_data(records: List[Dict], fields: List[str] = None) -> pd.DataFrame:
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records)
    df["created_at"] = pd.to_datetime(df["created_at"])
    if fields is None:
        fields = ["trestbps", "chol", "thalach", "oldpeak"]
    for f in fields:
        if f not in df.columns:
            df[f] = None
    return df[["created_at"] + fields]

def detect_trends(records: List[Dict], window: int = 3, threshold: float = 0.05) -> List[str]:
    alerts = []
    if len(records) < window:
        return alerts
    recent = records[-window:]
    fields = ["trestbps", "chol", "thalach", "oldpeak"]
    for field in fields:
        values = [rec.get(field) for rec in recent if rec.get(field) is not None]
        if len(values) < window:
            continue
        diff = np.diff(values)
        if field in ["trestbps", "chol", "oldpeak"]:
            if all(d > threshold for d in diff):
                alerts.append(f"⚠️ Your {field} has been increasing over the last {window} assessments. Consult a doctor.")
            elif all(d < -threshold for d in diff):
                alerts.append(f"✅ Your {field} has been decreasing – good trend.")
        elif field == "thalach":
            if all(d < -threshold for d in diff):
                alerts.append(f"⚠️ Your max heart rate has been decreasing over the last {window} assessments. Discuss with a doctor.")
            elif all(d > threshold for d in diff):
                alerts.append(f"✅ Your max heart rate is increasing – good trend.")
    return alerts

def enhance_alerts(alerts: List[str], data: Dict = None) -> List[str]:
    enhanced = []
    for alert in alerts:
        prompt = f"The following health alert was detected: {alert}\nProvide a short, encouraging, and actionable advice for the user."
        ai_advice = get_ai_response(prompt)
        if ai_advice:
            enhanced.append(ai_advice)
        else:
            enhanced.append(alert)
    return enhanced

def generate_ai_summary(records: List[Dict]) -> str:
    if len(records) < 2:
        return "Not enough data to generate a summary yet."
    prompt = "Summarize the health trends of a user based on these records:\n"
    for rec in records[-5:]:
        prompt += f"- Date: {rec['created_at'][:10]}, Age: {rec.get('age')}, BP: {rec.get('trestbps')}, Chol: {rec.get('chol')}, HR: {rec.get('thalach')}, ExAng: {rec.get('exang')}\n"
    prompt += "\nWrite a short, encouraging summary highlighting positive changes and areas to watch."
    return get_ai_response(prompt) or "AI summary currently unavailable."