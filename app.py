import streamlit as st
import streamlit.components.v1 as components

# Must be the first Streamlit command
st.set_page_config(page_title="HeartVigil AI", layout="wide")

# --- DEBUG: show query params on all pages (you can remove this later) ---
st.write("🔍 Query params:", dict(st.query_params))

# --- Convert URL hash (#) to query parameters (for password reset links) ---
components.html("""
<script>
const hash = window.location.hash.substring(1);
if (hash && !window.location.search.includes("access_token")) {
    const url = new URL(window.location);
    const params = new URLSearchParams(hash);
    params.forEach((value, key) => {
        url.searchParams.set(key, value);
    });
    window.location.replace(url.toString());
}
</script>
""", height=0)

# Now import the rest of your modules
from supabase_client import supabase
from data_agent import save_health_data
from risk_agent import doctor_ai_agent
from reco_agent import generate_recommendations
import monitor_agent
import pandas as pd
import plotly.graph_objects as go

# ---------- CUSTOM STYLE ----------
st.set_page_config(page_title="HeartVigil AI", layout="wide")

st.markdown("""
<style>
.stButton > button {
    background-color: #6B46C1 !important;
    color: white !important;
    border: none !important;
}
.stButton > button:hover {
    background-color: #553C9A !important;
}
</style>
""", unsafe_allow_html=True)

# ---------- SESSION STATE ----------
if "page" not in st.session_state:
    st.session_state.page = "dashboard"
if "auth_session" not in st.session_state:
    st.session_state.auth_session = None
if "result" not in st.session_state:
    st.session_state.result = None
if "latest_data" not in st.session_state:
    st.session_state.latest_data = None
if "extracted" not in st.session_state:
    st.session_state.extracted = {}
if "show_reset_popover" not in st.session_state:
    st.session_state.show_reset_popover = False

# ---------- AUTHENTICATION ----------
def check_session():
    return st.session_state.auth_session is not None

def login_signup():
    st.title("HeartVigil AI")
    tab1, tab2 = st.tabs(["Login", "Sign Up"])

    with tab1:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")

        if st.button("Forgot password?"):
            st.session_state.show_reset_popover = True

        if st.button("Login"):
            try:
                res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                if res.session:
                    st.session_state.auth_session = res.session
                    supabase.auth.set_session(res.session.access_token, res.session.refresh_token)
                    st.rerun()
                else:
                    st.error("Login failed")
            except Exception as e:
                st.error(f"Login failed: {e}")

        if st.session_state.show_reset_popover:
            with st.popover("Reset password"):
                reset_email = st.text_input("Enter your email")
                if st.button("Send reset link"):
                    try:
                        # ✅ Force query parameters by adding a dummy query string
                        supabase.auth.reset_password_for_email(
                            reset_email,
                            {"redirect_to": "https://heartvigil-15.streamlit.app?reset=true"}
                        )
                        st.success("✅ Reset email sent! Check your inbox.")
                        st.session_state.show_reset_popover = False
                    except Exception as e:
                        st.error(f"Error: {e}")
                if st.button("Cancel"):
                    st.session_state.show_reset_popover = False

    with tab2:
        email = st.text_input("Email", key="signup_email")
        password = st.text_input("Password", type="password", key="signup_password")
        if st.button("Sign Up"):
            try:
                res = supabase.auth.sign_up({"email": email, "password": password})
                if res.session:
                    st.session_state.auth_session = res.session
                    st.success("Account created! You are now logged in.")
                    st.rerun()
                else:
                    st.error("Signup failed")
            except Exception as e:
                st.error(f"Signup failed: {e}")

def show_reset_password():
    st.title("Reset Password")
    params = st.query_params

    access_token = params.get("access_token")
    refresh_token = params.get("refresh_token")
    token = params.get("token")
    type_param = params.get("type")

    if type_param == "recovery" or access_token or token:
        try:
            if access_token and refresh_token:
                supabase.auth.set_session(access_token, refresh_token)
            elif token:
                supabase.auth.verify_otp({"token": token, "type": "recovery"})
            else:
                st.error("Invalid link")
                return
        except Exception as e:
            st.error(f"Session error: {e}")
            return

        with st.form("reset_form"):
            new_password = st.text_input("New password", type="password")
            confirm_password = st.text_input("Confirm password", type="password")
            if st.form_submit_button("Update password"):
                if new_password != confirm_password:
                    st.error("Passwords do not match")
                elif len(new_password) < 6:
                    st.error("Minimum 6 characters required")
                else:
                    try:
                        supabase.auth.update_user({"password": new_password})
                        st.success("✅ Password updated successfully!")
                        st.query_params.clear()
                        st.session_state.auth_session = None
                        st.rerun()
                    except Exception as e:
                        st.error(f"Update failed: {e}")
    else:
        st.error("Invalid or expired reset link")

def logout():
    supabase.auth.sign_out()
    st.session_state.auth_session = None
    st.rerun()

# ---------- ROUTING ----------
params = st.query_params
if (
    params.get("access_token")
    or params.get("refresh_token")
    or params.get("type") == "recovery"
    or params.get("token")
):
    show_reset_password()
    st.stop()

if not check_session():
    login_signup()
    st.stop()

# ---------- LOGGED IN – FULL APP ----------
user_id = st.session_state.auth_session.user.id
user_email = st.session_state.auth_session.user.email
user_created_at = st.session_state.auth_session.user.created_at

# ---------- TOP BAR (Profile) ----------
top_col1, top_col2, top_col3 = st.columns([1, 4, 1])
with top_col1:
    pass
with top_col2:
    st.title("HeartVigil AI")
with top_col3:
    with st.popover("👤 Profile", width='stretch'):
        st.write(f"**Email:** {user_email}")
        if user_created_at:
            st.write(f"**Joined:** {user_created_at.strftime('%Y-%m-%d')}")
        if st.button("Logout"):
            logout()

# ---------- SIDEBAR (Navigation) ----------
with st.sidebar:
    st.markdown("## Navigation")
    if st.button("Dashboard"):
        st.session_state.page = "dashboard"
    if st.button("Assessment"):
        st.session_state.page = "assessment"
    if st.button("Risk Analysis"):
        st.session_state.page = "risk_analysis"
    if st.button("Data Agent"):
        st.session_state.page = "data_agent"
    if st.button("Monitoring"):
        st.session_state.page = "monitoring"
    if st.button("Recommendations"):
        st.session_state.page = "recommendations"
    st.markdown("---")
    st.caption("⚠️ Educational demo. Not for medical use.")

# ---------- VALIDATION RANGES ----------
VALID_RANGES = {
    "age": (1, 100),
    "sex": (0, 1),
    "cp": (0, 3),
    "trestbps": (80, 200),
    "chol": (100, 600),
    "fbs": (0, 1),
    "restecg": (0, 2),
    "thalach": (60, 220),
    "exang": (0, 1),
    "oldpeak": (0.0, 6.2),
    "slope": (0, 2),
    "ca": (0, 3),
    "thal": (1, 3)
}

# ---------- HELPER: validate and clean extracted values ----------
def validate_and_clean_extracted(extracted):
    cleaned = {}
    invalid = []
    for field, (low, high) in VALID_RANGES.items():
        val = extracted.get(field)
        if val is None:
            cleaned[field] = None
            continue
        if field == "sex" and isinstance(val, str):
            lower_val = val.lower()
            if lower_val in ["male", "m"]:
                val = 1
            elif lower_val in ["female", "f"]:
                val = 0
            else:
                invalid.append(field)
                cleaned[field] = None
                continue
        try:
            if isinstance(val, str):
                if '.' in val:
                    val = float(val)
                else:
                    val = int(val)
        except:
            invalid.append(field)
            cleaned[field] = None
            continue
        if isinstance(val, (int, float)):
            if low <= val <= high:
                cleaned[field] = val
            else:
                invalid.append(field)
                cleaned[field] = None
        else:
            invalid.append(field)
            cleaned[field] = None
    return cleaned, invalid

def validate_all_fields(data):
    errors = []
    for field, (low, high) in VALID_RANGES.items():
        if field in data:
            val = data[field]
            if val is None:
                continue
            if isinstance(val, (int, float)):
                if val < low or val > high:
                    errors.append(f"{field} value {val} is outside the allowed range ({low}–{high})")
            else:
                errors.append(f"{field} must be a number")
    return len(errors) == 0, errors

# ---------- DASHBOARD ----------
def show_dashboard():
    st.title("Your Heart Health Dashboard")

    if st.session_state.result:
        result = st.session_state.result
        col1, col2 = st.columns(2)
        with col1:
            risk_label = result["risk_label"]
            if risk_label == "LOW":
                color = "#10B981"
            elif risk_label == "MEDIUM":
                color = "#F59E0B"
            else:
                color = "#EF4444"
            st.markdown(f"<h2 style='color:{color};'>Risk: {risk_label}</h2>", unsafe_allow_html=True)
            st.metric("Probability", f"{result['probability']:.1f}%")
        with col2:
            st.subheader("Why this risk?")
            for r in result["reasons"]:
                st.write(f"• {r}")

        if st.session_state.latest_data:
            st.subheader("Your Values vs Safe Ranges")
            safe_limits = {
                "trestbps": ("Resting BP (mmHg)", 120, "lower"),
                "chol": ("Cholesterol (mg/dL)", 200, "lower"),
                "thalach": ("Max Heart Rate (bpm)", 150, "higher"),
                "oldpeak": ("ST Depression", 1.0, "lower")
            }
            chart_data = []
            for field, (label, limit, direction) in safe_limits.items():
                val = st.session_state.latest_data.get(field)
                if val is not None:
                    if direction == "lower":
                        if val <= limit:
                            color = "#10B981"
                        elif val <= limit * 1.1:
                            color = "#F59E0B"
                        else:
                            color = "#EF4444"
                    else:
                        if val >= limit:
                            color = "#10B981"
                        elif val >= limit * 0.9:
                            color = "#F59E0B"
                        else:
                            color = "#EF4444"
                    chart_data.append({
                        "Field": label,
                        "Your Value": val,
                        "Safe Limit": limit,
                        "Color": color
                    })
            if chart_data:
                df_chart = pd.DataFrame(chart_data)
                fig = go.Figure()
                for _, row in df_chart.iterrows():
                    fig.add_trace(go.Bar(
                        name=row["Field"],
                        x=[row["Field"]],
                        y=[row["Your Value"]],
                        marker_color=row["Color"],
                        text=f"{row['Your Value']} (limit {row['Safe Limit']})",
                        textposition="outside"
                    ))
                fig.update_layout(barmode="group", yaxis_title="Value", showlegend=False)
                st.plotly_chart(fig, width='stretch')
            else:
                st.info("No numeric fields available for chart.")
        else:
            st.info("No data for chart. Submit a new assessment.")

        if st.button("Take New Assessment"):
            st.session_state.page = "assessment"
            st.rerun()
    else:
        st.markdown("## Welcome to HeartVigil AI")
        st.write("Get a personalized heart health assessment in minutes.")
        if st.button("Start Your Assessment", type="primary"):
            st.session_state.page = "assessment"
            st.rerun()

# ---------- ASSESSMENT ----------
def show_assessment():
    st.title("Heart Health Assessment")
    st.markdown("Fields marked with * are required.")

    # PDF Upload Section
    uploaded_file = st.file_uploader("Upload a digital medical report (PDF)", type=["pdf"], key="pdf_uploader")
    if uploaded_file is not None:
        with st.spinner("Reading and extracting data from PDF..."):
            from pdf_extractor import parse_pdf_health_data
            extracted = parse_pdf_health_data(uploaded_file)
            if extracted:
                cleaned, invalid_fields = validate_and_clean_extracted(extracted)
                if invalid_fields:
                    st.warning(f"The following extracted values are outside valid ranges and have been discarded: {', '.join(invalid_fields)}. Please fill them manually.")
                compulsory_fields = ["age", "sex", "cp", "trestbps", "chol", "thalach", "exang"]
                missing = [f for f in compulsory_fields if cleaned.get(f) is None]
                if missing:
                    st.warning(f"PDF is missing compulsory fields: {', '.join(missing)}. Please fill the form manually.")
                    st.session_state.extracted = {}
                else:
                    st.session_state.extracted = cleaned
                    st.success("Extraction complete! Review the values below and edit if needed.")
            else:
                st.warning("No data could be extracted. Please fill the form manually.")
                st.session_state.extracted = {}

    if st.session_state.extracted:
        st.subheader("Extracted Values (review and edit)")
        display_dict = {k: (v if v is not None else "N/A") for k, v in st.session_state.extracted.items()}
        df = pd.DataFrame([display_dict]).T.reset_index()
        df.columns = ["Field", "Value"]
        st.table(df)
        st.info("If any value is missing or incorrect, please fill it in the form below.")

    with st.form("health_form"):
        def safe_get(field, default, min_val=None, max_val=None, is_float=False):
            val = st.session_state.extracted.get(field, default)
            if val is None:
                return default
            if is_float:
                try:
                    val = float(val)
                except:
                    return default
            else:
                try:
                    val = int(val)
                except:
                    return default
            return val

        col1, col2 = st.columns(2)

        with col1:
            age = st.number_input("Age *", min_value=1, max_value=100,
                                  value=safe_get("age", 50, min_val=1, max_val=100))
            sex_options = ["Female", "Male"]
            sex_index = safe_get("sex", 0, min_val=0, max_val=1)
            sex_label = st.selectbox("Sex *", options=sex_options, index=sex_index)
            sex = 1 if sex_label == "Male" else 0

            cp_options = ["Typical angina", "Atypical angina", "Non-anginal pain", "Asymptomatic"]
            cp_index = safe_get("cp", 0, min_val=0, max_val=3)
            cp_label = st.selectbox("Chest pain type *", options=cp_options, index=cp_index)
            cp = cp_index

            trestbps = st.number_input("Resting blood pressure (mm Hg) *", min_value=80, max_value=200,
                                       value=safe_get("trestbps", 120, min_val=80, max_val=200))
            chol = st.number_input("Cholesterol (mg/dl) *", min_value=100, max_value=600,
                                   value=safe_get("chol", 200, min_val=100, max_val=600))

            fbs_options = ["No", "Yes"]
            fbs_index = safe_get("fbs", 0, min_val=0, max_val=1)
            fbs_label = st.selectbox("Fasting blood sugar > 120 mg/dl", options=fbs_options, index=fbs_index)
            fbs = fbs_index

            restecg_options = ["Normal", "ST-T abnormality", "Left ventricular hypertrophy"]
            restecg_index = safe_get("restecg", 0, min_val=0, max_val=2)
            restecg_label = st.selectbox("Resting ECG results", options=restecg_options, index=restecg_index)
            restecg = restecg_index

        with col2:
            thalach = st.number_input("Max heart rate achieved *", min_value=60, max_value=220,
                                      value=safe_get("thalach", 150, min_val=60, max_val=220))
            exang_options = ["No", "Yes"]
            exang_index = safe_get("exang", 0, min_val=0, max_val=1)
            exang_label = st.selectbox("Exercise induced angina *", options=exang_options, index=exang_index)
            exang = exang_index

            oldpeak = st.number_input("ST depression induced by exercise", min_value=0.0, max_value=6.2,
                                      value=float(safe_get("oldpeak", 1.0, min_val=0, max_val=6.2, is_float=True)),
                                      step=0.1)

            slope_options = ["Upsloping", "Flat", "Downsloping"]
            slope_index = safe_get("slope", 0, min_val=0, max_val=2)
            slope_label = st.selectbox("Slope of peak exercise ST segment", options=slope_options, index=slope_index)
            slope = slope_index

            ca = st.number_input("Number of major vessels (0-3)", min_value=0, max_value=3,
                                 value=safe_get("ca", 0, min_val=0, max_val=3))

            thal_options = ["Normal", "Fixed defect", "Reversible defect"]
            thal_index = safe_get("thal", 1, min_val=1, max_val=3) - 1
            thal_label = st.selectbox("Thalassemia", options=thal_options, index=thal_index)
            thal = thal_index + 1

        submitted = st.form_submit_button("Analyse My Heart Health")

    if submitted:
        compulsory = [age, sex, cp, trestbps, chol, thalach, exang]
        if any(v is None for v in compulsory):
            st.error("All compulsory fields (marked with *) must be filled.")
            st.stop()

        data = {
            "age": age,
            "sex": sex,
            "cp": cp,
            "trestbps": trestbps,
            "chol": chol,
            "fbs": fbs,
            "restecg": restecg,
            "thalach": thalach,
            "exang": exang,
            "oldpeak": oldpeak,
            "slope": slope,
            "ca": ca,
            "thal": thal
        }

        valid, errors = validate_all_fields(data)
        if not valid:
            for err in errors:
                st.error(err)
            st.stop()

        success, result = save_health_data(data, user_id)
        if not success:
            st.error(f"Failed to save: {result}")
            st.stop()

        doctor_result = doctor_ai_agent(data)
        st.session_state.result = doctor_result
        st.session_state.latest_data = data
        st.session_state.extracted = {}

        st.success("Assessment complete!")
        st.session_state.page = "dashboard"
        st.rerun()

# ---------- DATA AGENT (HISTORY) ----------
def show_data_agent():
    st.title("Data Agent – Your Health Records")
    response = supabase.table("health_records")\
        .select("*")\
        .eq("user_id", user_id)\
        .order("created_at", desc=True)\
        .limit(5)\
        .execute()
    records = response.data

    if not records:
        st.info("No assessments yet. Start your first assessment!")
        if st.button("Start Your Assessment"):
            st.session_state.page = "assessment"
            st.rerun()
        return

    if len(records) >= 2:
        from ai_helper import get_ai_response
        prompt = f"Summarize the health trends of a user from these records: {records}"
        summary = get_ai_response(prompt)
        if summary:
            st.subheader("AI Summary")
            st.info(summary)

    st.subheader("Recent Assessments (last 5)")
    history_data = []
    for rec in records:
        history_data.append({
            "Date": rec["created_at"][:10] if rec["created_at"] else "N/A",
            "Age": rec.get("age"),
            "Sex": "Male" if rec.get("sex") == 1 else "Female",
            "BP": rec.get("trestbps"),
            "Chol": rec.get("chol"),
            "HR": rec.get("thalach"),
            "Chest Pain": rec.get("cp")
        })
    df = pd.DataFrame(history_data)
    st.table(df)

    st.subheader("Comparison Chart (Latest Assessment)")
    latest = records[0]
    safe_limits = {
        "trestbps": ("Resting BP (mmHg)", 120, "lower"),
        "chol": ("Cholesterol (mg/dL)", 200, "lower"),
        "thalach": ("Max Heart Rate (bpm)", 150, "higher"),
        "oldpeak": ("ST Depression", 1.0, "lower")
    }
    chart_data = []
    for field, (label, limit, direction) in safe_limits.items():
        val = latest.get(field)
        if val is not None:
            if direction == "lower":
                if val <= limit:
                    color = "#10B981"
                elif val <= limit * 1.1:
                    color = "#F59E0B"
                else:
                    color = "#EF4444"
            else:
                if val >= limit:
                    color = "#10B981"
                elif val >= limit * 0.9:
                    color = "#F59E0B"
                else:
                    color = "#EF4444"
            chart_data.append({
                "Field": label,
                "Your Value": val,
                "Safe Limit": limit,
                "Color": color
            })
    if chart_data:
        df_chart = pd.DataFrame(chart_data)
        fig = go.Figure()
        for _, row in df_chart.iterrows():
            fig.add_trace(go.Bar(
                name=row["Field"],
                x=[row["Field"]],
                y=[row["Your Value"]],
                marker_color=row["Color"],
                text=f"{row['Your Value']} (limit {row['Safe Limit']})",
                textposition="outside"
            ))
        fig.update_layout(barmode="group", yaxis_title="Value", showlegend=False)
        st.plotly_chart(fig, width='stretch')
    else:
        st.write("No numeric fields available for comparison.")

# ---------- RISK ANALYSIS ----------
def show_risk_analysis():
    st.title("Risk Analysis")

    result = st.session_state.result
    if not result:
        response = supabase.table("health_records")\
            .select("*")\
            .eq("user_id", user_id)\
            .order("created_at", desc=True)\
            .limit(1)\
            .execute()
        if response.data:
            latest = response.data[0]
            data = {k: latest.get(k) for k in ["age","sex","cp","trestbps","chol","fbs","restecg",
                                                "thalach","exang","oldpeak","slope","ca","thal"]}
            result = doctor_ai_agent(data)
            st.session_state.result = result
        else:
            result = None

    if not result:
        st.info("No health assessment found. Please submit your first assessment.")
        if st.button("Go to Assessment"):
            st.session_state.page = "assessment"
            st.rerun()
        return

    risk_label = result["risk_label"]
    probability = result["probability"]
    reasons = result.get("reasons", [])
    ai_explanation = result.get("ai_explanation", None)

    if risk_label == "LOW":
        label_color = "#10B981"
    elif risk_label == "MEDIUM":
        label_color = "#F59E0B"
    else:
        label_color = "#EF4444"

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=probability,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': "Risk Probability"},
        gauge={
            'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "darkblue"},
            'bar': {'color': label_color},
            'steps': [
                {'range': [0, 40], 'color': "#10B981"},
                {'range': [40, 65], 'color': "#F59E0B"},
                {'range': [65, 100], 'color': "#EF4444"}
            ],
            'threshold': {
                'line': {'color': "black", 'width': 4},
                'thickness': 0.75,
                'value': probability
            }
        }
    ))
    fig.update_layout(height=300, margin=dict(l=20, r=20, t=50, b=20))
    st.plotly_chart(fig, width='stretch')

    st.markdown(f"<h2 style='text-align: center; color:{label_color};'>Risk Level: {risk_label}</h2>",
                unsafe_allow_html=True)

    if reasons:
        st.subheader("Why this risk?")
        for r in reasons:
            st.write(f"• {r}")

    if ai_explanation:
        st.subheader("AI Insights")
        st.write(ai_explanation)

    if st.button("Take New Assessment"):
        st.session_state.page = "assessment"
        st.rerun()

# ---------- MONITORING ----------
def show_monitoring():
    st.title("📈 Health Monitoring & Trends")
    st.markdown("Track your health metrics over time and receive early warnings.")

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start date", value=None, key="start_date")
    with col2:
        end_date = st.date_input("End date", value=None, key="end_date")
    start_date_str = start_date.isoformat() if start_date else None
    end_date_str = end_date.isoformat() if end_date else None

    records = monitor_agent.get_user_history(user_id, start_date_str, end_date_str)
    if len(records) == 0:
        st.info("No assessments found for the selected period.")
        if st.button("Go to Assessment"):
            st.session_state.page = "assessment"
            st.rerun()
        return

    st.subheader("Key Metrics")
    metrics = ["trestbps", "chol", "thalach", "oldpeak"]
    metric_labels = {
        "trestbps": "Resting BP (mmHg)",
        "chol": "Cholesterol (mg/dL)",
        "thalach": "Max Heart Rate (bpm)",
        "oldpeak": "ST Depression"
    }
    cols = st.columns(4)
    for i, metric in enumerate(metrics):
        latest, percent, symbol = monitor_agent.compute_trends(records, metric)
        if latest is not None:
            if metric in ["trestbps", "chol", "oldpeak"]:
                if percent > 0:
                    color = "#EF4444"
                elif percent < 0:
                    color = "#10B981"
                else:
                    color = "#F59E0B"
            else:
                if percent > 0:
                    color = "#10B981"
                elif percent < 0:
                    color = "#EF4444"
                else:
                    color = "#F59E0B"
            delta = f"{symbol} {abs(percent):.1f}%" if percent != 0 else "No change"
            with cols[i]:
                st.metric(
                    label=metric_labels[metric],
                    value=f"{latest:.1f}" if isinstance(latest, float) else f"{latest}",
                    delta=delta,
                    delta_color="normal"
                )
        else:
            with cols[i]:
                st.metric(label=metric_labels[metric], value="N/A")

    st.subheader("📊 Latest Values vs Safe Ranges")
    latest = records[-1]
    chart_data = monitor_agent.generate_comparison_data(latest)
    if chart_data:
        df_chart = pd.DataFrame(chart_data)
        fig = go.Figure()
        for _, row in df_chart.iterrows():
            if row["Direction"] == "lower":
                if row["Your Value"] <= row["Safe Limit"]:
                    color = "#10B981"
                elif row["Your Value"] <= row["Safe Limit"] * 1.1:
                    color = "#F59E0B"
                else:
                    color = "#EF4444"
            else:
                if row["Your Value"] >= row["Safe Limit"]:
                    color = "#10B981"
                elif row["Your Value"] >= row["Safe Limit"] * 0.9:
                    color = "#F59E0B"
                else:
                    color = "#EF4444"
            fig.add_trace(go.Bar(
                name=row["Field"],
                x=[row["Field"]],
                y=[row["Your Value"]],
                marker_color=color,
                text=f"{row['Your Value']} (limit {row['Safe Limit']})",
                textposition="outside"
            ))
        fig.update_layout(barmode="group", yaxis_title="Value", showlegend=False, height=400)
        st.plotly_chart(fig, width='stretch')
    else:
        st.info("No numeric fields available for comparison.")

    if len(records) > 1:
        st.subheader("📈 Trends Over Time")
        metric = st.selectbox("Select a metric", metrics, format_func=lambda x: metric_labels[x])
        df_trend = monitor_agent.generate_trend_data(records, [metric])
        if metric in df_trend.columns:
            df_sel = df_trend[["created_at", metric]].dropna()
            if not df_sel.empty:
                rolling_avg = df_sel[metric].rolling(window=3, min_periods=1).mean()
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=df_sel["created_at"], y=df_sel[metric],
                    mode='lines+markers', name='Actual',
                    line=dict(color='#6B46C1'), marker=dict(size=8)
                ))
                fig.add_trace(go.Scatter(
                    x=df_sel["created_at"], y=rolling_avg,
                    mode='lines', name='3‑point Rolling Average',
                    line=dict(color='#F59E0B', dash='dash')
                ))
                fig.update_layout(
                    title=f"{metric_labels[metric]} Over Time",
                    xaxis_title="Date",
                    yaxis_title=metric_labels[metric],
                    hovermode='x unified',
                    height=450
                )
                st.plotly_chart(fig, width='stretch')
            else:
                st.warning(f"No data available for {metric_labels[metric]}")
        else:
            st.warning(f"Field {metric} not found in data.")
    else:
        st.info("You have only one assessment. After your second assessment, you'll see trend charts here.")

    alerts = monitor_agent.detect_trends(records)
    if alerts:
        st.subheader("🔔 Alerts & Insights")
        enhanced_alerts = monitor_agent.enhance_alerts(alerts)
        for alert in enhanced_alerts:
            if "⚠️" in alert:
                st.warning(alert)
            else:
                st.success(alert)
    else:
        st.success("No concerning trends detected. Keep up the good work!")

    if len(records) >= 2:
        st.subheader("🤖 AI Summary")
        with st.spinner("Generating insights..."):
            summary = monitor_agent.generate_ai_summary(records)
        if summary:
            st.info(summary)
        else:
            st.write("AI summary currently unavailable.")

# ---------- RECOMMENDATIONS ----------
def show_recommendations():
    st.title("Recommendations")
    st.markdown("Personalised health advice based on your latest assessment.")

    data = st.session_state.latest_data
    if not data:
        response = supabase.table("health_records")\
            .select("*")\
            .eq("user_id", user_id)\
            .order("created_at", desc=True)\
            .limit(1)\
            .execute()
        if response.data:
            latest = response.data[0]
            data = {k: latest.get(k) for k in ["age","sex","cp","trestbps","chol","fbs","restecg",
                                                "thalach","exang","oldpeak","slope","ca","thal"]}
            st.session_state.latest_data = data

    if not data:
        st.info("No health data available. Please submit an assessment first.")
        if st.button("Go to Assessment"):
            st.session_state.page = "assessment"
            st.rerun()
        return

    recs = generate_recommendations(data)
    for rec in recs:
        st.write(f"• {rec}")

# ---------- ROUTING ----------
if st.session_state.page == "dashboard":
    show_dashboard()
elif st.session_state.page == "assessment":
    show_assessment()
elif st.session_state.page == "risk_analysis":
    show_risk_analysis()
elif st.session_state.page == "data_agent":
    show_data_agent()
elif st.session_state.page == "monitoring":
    show_monitoring()
elif st.session_state.page == "recommendations":
    show_recommendations()
else:
    show_dashboard()