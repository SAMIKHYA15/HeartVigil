import pdfplumber
import json
from ai_helper import get_ai_response

def extract_text_from_pdf(uploaded_file):
    """Extract plain text from a typed PDF."""
    try:
        with pdfplumber.open(uploaded_file) as pdf:
            text = ""
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text.strip()
    except Exception as e:
        print(f"PDF extraction error: {e}")
        return ""

def parse_health_data_from_text(text):
    """Use AI to extract health parameters from the report text."""
    if not text:
        return {}

    prompt = f"""
You are a medical data extraction assistant. Extract the following health parameters from the provided medical report text.
Return ONLY a JSON object with the extracted values. If a value is not found, use null.

Parameters to extract:
- age: patient's age (number)
- sex: 0 for female, 1 for male
- cp: chest pain type (0=typical angina, 1=atypical angina, 2=non-anginal pain, 3=asymptomatic)
- trestbps: resting blood pressure in mmHg (number)
- chol: cholesterol in mg/dl (number)
- fbs: fasting blood sugar >120 mg/dl (0=no, 1=yes)
- restecg: resting ECG results (0=normal, 1=ST-T abnormality, 2=left ventricular hypertrophy)
- thalach: maximum heart rate achieved (number)
- exang: exercise induced angina (0=no, 1=yes)
- oldpeak: ST depression induced by exercise (number)
- slope: slope of peak exercise ST segment (0=upslope, 1=flat, 2=downslope)
- ca: number of major vessels colored by fluoroscopy (0-3)
- thal: thalassemia (1=normal, 2=fixed defect, 3=reversible defect)

Medical report text:
{text}

Return format: {{"age": 45, "sex": 1, "cp": 2, ...}} or {{"age": null, "sex": null, ...}} if no data found.
"""

    response = get_ai_response(prompt)

    # Try to extract JSON from the response
    try:
        # Find first '{' and last '}'
        start = response.find('{')
        end = response.rfind('}') + 1
        if start != -1 and end > start:
            json_str = response[start:end]
            data = json.loads(json_str)
            return data
    except Exception as e:
        print(f"Error parsing AI response: {e}")

    return {}

def parse_pdf_health_data(uploaded_file):
    """Main entry point: extract text from PDF and parse it into health data."""
    text = extract_text_from_pdf(uploaded_file)
    if not text:
        return {}
    return parse_health_data_from_text(text)