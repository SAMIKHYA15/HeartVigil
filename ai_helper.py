import os

# Try to import Groq, but if it fails, set a flag
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

def get_ai_response(prompt, model="llama-3.3-70b-versatile"):
    """
    Generate AI response using Groq if available; otherwise return a friendly message.
    """
    if not GROQ_AVAILABLE:
        return "✨ (Demo) AI package not installed. In production, this would provide personalised health insights. ✨"
    
    if not GROQ_API_KEY:
        return "✨ (Demo) Groq API key not configured. Please add it to your environment variables. ✨"
    
    try:
        client = Groq(api_key=GROQ_API_KEY)
        completion = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=500,
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"Groq API error: {e}")
        return "AI insights are temporarily unavailable. Please try again later."