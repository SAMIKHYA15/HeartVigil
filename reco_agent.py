from ai_helper import get_ai_response

def rule_based_recommendations(data):
    recs = []
    if data.get("chol", 0) > 240:
        recs.append("⚠️ High cholesterol: Avoid oily & fried food. Eat oats, fruits, vegetables.")
    if data.get("trestbps", 0) > 140:
        recs.append("⚠️ High BP: Reduce salt intake, manage stress, do meditation.")
    if data.get("thalach", 0) < 100:
        recs.append("🏃 Low heart fitness: Do 30 mins cardio daily.")
    if data.get("fbs", 0) == 1:
        recs.append("🍬 High sugar level: Avoid sweets & sugary drinks.")
    if data.get("exang", 0) == 1:
        recs.append("⚠️ Chest pain during exercise: Consult a doctor before workouts.")
    if data.get("oldpeak", 0) > 2:
        recs.append("⚠️ Heart stress detected: Avoid heavy physical exertion.")
    if data.get("age", 0) > 50:
        recs.append("🩺 Regular health checkups recommended (age > 50).")
    if not recs:
        recs.append("✅ You are doing well! Maintain healthy lifestyle and regular exercise.")
    return recs

def generate_recommendations(data):
    # Try AI first
    prompt = f"""
    You are a heart health assistant. Based on these values, give 3-5 short, actionable recommendations.
    - Age: {data.get('age')}
    - Sex: {'Male' if data.get('sex')==1 else 'Female'}
    - Resting BP: {data.get('trestbps')} mmHg
    - Cholesterol: {data.get('chol')} mg/dL
    - Max Heart Rate: {data.get('thalach')} bpm
    - Exercise angina: {'Yes' if data.get('exang')==1 else 'No'}
    - ST depression: {data.get('oldpeak')}
    - Fasting blood sugar >120: {'Yes' if data.get('fbs')==1 else 'No'}
    
    Format each recommendation as a bullet point starting with •.
    Keep them friendly, concise, and specific.
    """
    ai_response = get_ai_response(prompt)
    if ai_response:
        # Extract lines that start with •
        lines = ai_response.strip().split('\n')
        recommendations = [line.strip() for line in lines if line.strip().startswith('•')]
        if recommendations:
            return recommendations
    # Fallback to rule-based
    return rule_based_recommendations(data)