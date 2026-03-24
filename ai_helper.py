import os
from groq import Groq

# Initialize Groq client
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def get_ai_response(prompt, model_name="llama-3.3-70b-versatile"):
    """
    Generate AI response using Groq's free tier.
    1000 requests/day, 30 req/min limit.
    """
    try:
        completion = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=500
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        print(f"AI error: {e}")
        return "AI insights are currently unavailable. Please try again later."