"""
Recommendation Agent (Phase 2)
--------------------------------
Generates personalised health recommendations using Groq's Llama 3.1 API.
"""

import os
import logging
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    logger.warning("Groq not installed. AI recommendations will use fallback.")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")


def rule_based_recommendations(data):
    """Phase 1 rule-based recommendations (fallback)."""
    recs = []
    
    chol = data.get("chol", 0)
    if chol > 240:
        recs.append("⚠️ High cholesterol: Avoid oily & fried food. Eat oats, fruits, vegetables.")
    elif chol > 200:
        recs.append("🥗 Borderline cholesterol: Reduce saturated fats, add more fibre to your diet.")
    
    bp = data.get("trestbps", 0)
    if bp > 140:
        recs.append("⚠️ High BP: Reduce salt intake, manage stress, do meditation daily.")
    elif bp > 120:
        recs.append("🧘 Elevated BP: Monitor regularly, try deep breathing exercises.")
    
    hr = data.get("thalach", 0)
    if hr < 100:
        recs.append("🏃 Low heart fitness: Start with 30 mins walking daily, gradually increase intensity.")
    elif hr < 120:
        recs.append("🚶 Improve cardiovascular fitness: Aim for 150 mins of moderate exercise weekly.")
    
    if data.get("fbs", 0) == 1:
        recs.append("🍬 High fasting blood sugar: Limit sugary drinks, choose whole grains over refined carbs.")
    
    if data.get("exang", 0) == 1:
        recs.append("⚠️ Chest pain during exercise: Consult your doctor before starting any exercise programme.")
    
    oldpeak = data.get("oldpeak", 0)
    if oldpeak > 2:
        recs.append("⚠️ Heart stress detected: Avoid heavy physical exertion until cleared by a doctor.")
    elif oldpeak > 1:
        recs.append("💓 Monitor your heart: Avoid strenuous activity and take regular breaks.")
    
    age = data.get("age", 0)
    if age > 50:
        recs.append("🩺 Regular health checkups recommended: Annual heart screening is important after 50.")
    elif age > 40:
        recs.append("📊 Consider yearly health checkups to track your heart health.")
    
    if not recs:
        recs = [
            "✅ You're doing well! Maintain your healthy lifestyle with balanced diet and regular exercise.",
            "❤️ Keep your heart healthy: Stay active, eat mindfully, and manage stress.",
            "📝 Track your health regularly to catch any changes early.",
            "💪 Consistency is key: Small daily habits lead to long-term heart health."
        ]
    
    while len(recs) < 3:
        recs.append("💙 Keep monitoring your health and consult your doctor for personalised advice.")
    
    return recs[:5]


def build_prompt(current_values, risk_output=None, progress_summary=None):
    """Build a structured prompt for Groq based on all available health data."""
    
    age = current_values.get('age', 'Not specified')
    sex = "Male" if current_values.get('sex') == 1 else "Female"
    chol = current_values.get('chol', 'Not specified')
    trestbps = current_values.get('trestbps', 'Not specified')
    thalach = current_values.get('thalach', 'Not specified')
    cp = current_values.get('cp', 'Not specified')
    exang = "Yes" if current_values.get('exang') == 1 else "No"
    oldpeak = current_values.get('oldpeak', 'Not specified')
    fbs = "Yes" if current_values.get('fbs') == 1 else "No"
    
    cp_map = {0: "Typical angina", 1: "Atypical angina", 2: "Non-anginal pain", 3: "Asymptomatic"}
    cp_text = cp_map.get(cp, "Not specified")
    
    system_prompt = """You are a friendly, warm health assistant for HeartVigil AI, a heart disease risk monitoring app.
Your role is to provide clear, simple, and actionable health tips based on the user's health data.

Guidelines:
- Write in plain English. No medical jargon or complex terms.
- Keep each tip to 2 sentences maximum.
- Address the user directly as 'you'.
- Be warm, encouraging, and supportive — not alarming or scary.
- Base your tips on the specific health values provided.
- If the user is improving, celebrate their progress.
- If things are worsening, offer gentle, actionable suggestions.
- Always end with a reminder that this is not a medical diagnosis.
- Return exactly 5 tips as a numbered list (1., 2., 3., etc.).
- Nothing else — just the numbered tips."""
    
    user_prompt = f"""Please generate 5 personalised heart health tips for this person:

HEALTH PROFILE:
- Age: {age} | Sex: {sex}
- Cholesterol: {chol} mg/dL (healthy range: below 200)
- Blood pressure: {trestbps} mmHg (healthy range: below 140)
- Max heart rate: {thalach} bpm (healthy range: 100-170 depending on age)
- Chest pain type: {cp_text}
- Exercise angina: {exang}
- ST depression: {oldpeak} mm (healthy range: below 1.0)
- Fasting blood sugar >120 mg/dL: {fbs}
"""
    
    if risk_output and risk_output.get('risk_label'):
        risk_label = risk_output['risk_label']
        probability = risk_output.get('probability', 0)
        user_prompt += f"""
RISK ANALYSIS:
- Current risk level: {risk_label} ({probability:.1f}% probability)
"""
        
        risk_direction = risk_output.get('risk_direction', 'first_submission')
        if risk_direction == 'improved':
            user_prompt += f"- Your risk has IMPROVED since your last assessment! 🎉\n"
        elif risk_direction == 'worsened':
            user_prompt += f"- Your risk has INCREASED since your last assessment. Let's work on this.\n"
        elif risk_direction == 'stable':
            user_prompt += f"- Your risk is stable compared to last time. Consistency is key!\n"
        
        if risk_output.get('change_driver'):
            user_prompt += f"- Key change: {risk_output['change_driver']}\n"
    
    if progress_summary and progress_summary.get('summary_text'):
        user_prompt += f"""
PROGRESS SINCE LAST VISIT:
{progress_summary['summary_text']}
"""
        if progress_summary.get('improved_fields'):
            user_prompt += f"- Improved: {', '.join(progress_summary['improved_fields'])}\n"
        if progress_summary.get('worsened_fields'):
            user_prompt += f"- Could improve: {', '.join(progress_summary['worsened_fields'])}\n"
        if progress_summary.get('most_improved'):
            user_prompt += f"- Biggest improvement: {progress_summary['most_improved']}\n"
        if progress_summary.get('most_concerning'):
            user_prompt += f"- Most concerning area: {progress_summary['most_concerning']}\n"
    
    if progress_summary and progress_summary.get('overall_trend'):
        trend = progress_summary['overall_trend']
        if trend == 'improving':
            user_prompt += f"\nOverall trend: IMPROVING! Keep up the good work! 🌟\n"
        elif trend == 'declining':
            user_prompt += f"\nOverall trend: DECLINING. Let's focus on making positive changes.\n"
        elif trend == 'mixed':
            user_prompt += f"\nOverall trend: MIXED. Some areas improved, some need attention.\n"
    
    user_prompt += """
Generate 5 specific, actionable tips based on this person's health profile.
Focus on the areas that need the most attention, and celebrate improvements where you see them."""
    
    return system_prompt, user_prompt


def parse_groq_response(response_text):
    """Parse Groq's response to extract numbered recommendations."""
    recommendations = []
    lines = response_text.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if line and (line[0].isdigit() and (line[1] in ['.', ')', ':'] or len(line) > 1 and line[1] == '.')):
            tip = line.split('.', 1)[-1].strip() if '.' in line else line
            tip = tip.split(')', 1)[-1].strip() if ')' in tip else tip
            tip = tip.split(':', 1)[-1].strip() if ':' in tip else tip
            tip = tip.replace('•', '').replace('-', '').strip()
            if tip and len(tip) > 5:
                recommendations.append(tip)
        elif line.startswith('•') or line.startswith('-'):
            tip = line.lstrip('•- ').strip()
            if tip and len(tip) > 5:
                recommendations.append(tip)
    
    seen = set()
    unique_recs = []
    for rec in recommendations:
        if rec not in seen:
            seen.add(rec)
            unique_recs.append(rec)
    
    return unique_recs if unique_recs else None


def get_recommendations(data, risk_output=None, progress_summary=None):
    """Main function to generate recommendations with Groq API."""
    
    if not data:
        logger.warning("No health data provided for recommendations")
        return ["Please complete a health assessment to get personalised recommendations."]
    
    if GROQ_AVAILABLE and GROQ_API_KEY:
        try:
            system_prompt, user_prompt = build_prompt(data, risk_output, progress_summary)
            client = Groq(api_key=GROQ_API_KEY)
            
            logger.info("Calling Groq API for recommendations...")
            completion = client.chat.completions.create(
                model="llama-3.1-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.4,
                max_tokens=600,
                top_p=0.9
            )
            
            response_text = completion.choices[0].message.content
            logger.info(f"Groq response received ({len(response_text)} chars)")
            
            recommendations = parse_groq_response(response_text)
            
            if recommendations and len(recommendations) >= 3:
                if len(recommendations) > 5:
                    recommendations = recommendations[:5]
                elif len(recommendations) < 5:
                    fallback = rule_based_recommendations(data)
                    while len(recommendations) < 5 and fallback:
                        recommendations.append(fallback.pop(0))
                logger.info(f"Generated {len(recommendations)} recommendations via Groq")
                return recommendations
            else:
                logger.warning("Groq response parsing failed, using fallback")
                
        except Exception as e:
            logger.error(f"Groq API error: {e}", exc_info=True)
    else:
        if not GROQ_AVAILABLE:
            logger.warning("Groq not installed - using fallback recommendations")
        elif not GROQ_API_KEY:
            logger.warning("GROQ_API_KEY not configured - using fallback recommendations")
    
    logger.info("Using rule-based fallback recommendations")
    return rule_based_recommendations(data)


# ========== MAIN FUNCTION (Called by app.py) ==========
def generate_recommendations(data, risk_output=None, progress_summary=None):
    """
    Main entry point for the recommendation agent.
    Accepts 3 parameters for Phase 2, but maintains backward compatibility.
    
    Args:
        data (dict): Current health parameters
        risk_output (dict, optional): Output from risk_agent
        progress_summary (dict, optional): Output from monitor_agent
    
    Returns:
        list: List of recommendation strings (5 items)
    """
    return get_recommendations(data, risk_output, progress_summary)