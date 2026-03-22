import streamlit as st
from supabase_client import supabase
from data_agent import save_health_data
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="HeartVigil AI", layout="wide")

import os

# Debug: show secrets on the page (remove after testing)
st.sidebar.write(f"URL: {os.environ.get('SUPABASE_URL', 'NOT SET')}")
st.sidebar.write(f"KEY (first 10 chars): {os.environ.get('SUPABASE_KEY', 'NOT SET')[:10]}")
# Session state
if "page" not in st.session_state:
    st.session_state.page = "dashboard"
if "auth_session" not in st.session_state:
    st.session_state.auth_session = None

# ---------- Authentication ----------
def check_session():
    return st.session_state.auth_session is not None

def login_signup():
    st.title("HeartVigil AI")
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    with tab1:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        if st.button("Login"):
            try:
                res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                if hasattr(res, 'session') and res.session:
                    st.session_state.auth_session = res.session
                    supabase.auth.set_session(res.session.access_token, res.session.refresh_token)
                    st.rerun()
                else:
                    st.error("Login failed: no session returned")
            except Exception as e:
                st.error(f"Login failed: {e}")
    with tab2:
        email = st.text_input("Email", key="signup_email")
        password = st.text_input("Password", type="password", key="signup_password")
        if st.button("Sign Up"):
            try:
                res = supabase.auth.sign_up({"email": email, "password": password})
                if hasattr(res, 'session') and res.session:
                    st.session_state.auth_session = res.session
                    supabase.auth.set_session(res.session.access_token, res.session.refresh_token)
                    st.success("Account created! You are now logged in.")
                    st.rerun()
                else:
                    st.error("Sign up failed: no session returned. Email may already exist.")
            except Exception as e:
                st.error(f"Sign up failed: {e}")

def logout():
    supabase.auth.sign_out()
    st.session_state.auth_session = None
    st.rerun()

# ---------- Main app ----------
if not check_session():
    login_signup()
    st.stop()

user_id = st.session_state.auth_session.user.id
user_email = st.session_state.auth_session.user.email

# Sidebar navigation
st.sidebar.write(f"Logged in as: {user_email}")
if st.sidebar.button("Logout"):
    logout()

if st.sidebar.button("Dashboard"):
    st.session_state.page = "dashboard"
if st.sidebar.button("New Assessment"):
    st.session_state.page = "assessment"
if st.sidebar.button("History"):
    st.session_state.page = "history"

# ---------- Dashboard page ----------
def show_dashboard():
    st.title("Your Heart Health Dashboard")
    # Always show welcome screen
    st.markdown("## Welcome to HeartVigil AI")
    st.write("Get a personalized heart health assessment in minutes.")
    if st.button("Start Your Assessment", type="primary"):
        st.session_state.page = "assessment"
        st.rerun()

# ---------- Assessment page ----------
def show_assessment():
    st.title("Heart Health Assessment")
    st.markdown("Fill in your health details. All fields are optional for now.")
    with st.form("health_form"):
        col1, col2 = st.columns(2)
        with col1:
            age = st.number_input("Age", min_value=1, max_value=100, value=50)
            sex = st.selectbox("Sex", options=[(0,"Female"), (1,"Male")], format_func=lambda x: x[1])[0]
            cp = st.selectbox("Chest pain type", options=[(0,"Typical angina"), (1,"Atypical angina"), (2,"Non-anginal pain"), (3,"Asymptomatic")], format_func=lambda x: x[1])[0]
            trestbps = st.number_input("Resting blood pressure (mm Hg)", min_value=80, max_value=200, value=120)
            chol = st.number_input("Cholesterol (mg/dl)", min_value=100, max_value=600, value=200)
            fbs = st.selectbox("Fasting blood sugar > 120 mg/dl", options=[(0,"No"), (1,"Yes")], format_func=lambda x: x[1])[0]
            restecg = st.selectbox("Resting ECG results", options=[(0,"Normal"), (1,"ST-T abnormality"), (2,"Left ventricular hypertrophy")], format_func=lambda x: x[1])[0]
        with col2:
            thalach = st.number_input("Max heart rate achieved", min_value=60, max_value=220, value=150)
            exang = st.selectbox("Exercise induced angina", options=[(0,"No"), (1,"Yes")], format_func=lambda x: x[1])[0]
            oldpeak = st.number_input("ST depression induced by exercise", min_value=0.0, max_value=6.2, value=1.0, step=0.1)
            slope = st.selectbox("Slope of peak exercise ST segment", options=[(0,"Upsloping"), (1,"Flat"), (2,"Downsloping")], format_func=lambda x: x[1])[0]
            ca = st.number_input("Number of major vessels (0-3)", min_value=0, max_value=3, value=0)
            thal = st.selectbox("Thalassemia", options=[(1,"Normal"), (2,"Fixed defect"), (3,"Reversible defect")], format_func=lambda x: x[1])[0]
        submitted = st.form_submit_button("Save Assessment")
    if submitted:
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
        success, result = save_health_data(data, user_id)
        if success:
            st.success("Assessment saved!")
            st.session_state.page = "dashboard"
            st.rerun()
        else:
            st.error(f"Error: {result}")

# ---------- History page ----------
def show_history():
    st.title("Your Assessment History")
    # Fetch all submissions for this user, sorted by newest first
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

    # Show last 5 in a table
    st.subheader("Recent Assessments (last 5)")
    # Prepare a readable table
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

    # Comparison chart for the latest submission
    st.subheader("Comparison Chart (Latest Assessment)")
    latest = records[0]
    safe_limits = {
        "trestbps": 120,   # systolic BP <120 ideal
        "chol": 200,       # cholesterol <200
        "thalach": 150,    # max heart rate >150 good
        "oldpeak": 1.0     # ST depression <1.0 normal
    }
    chart_data = []
    for field, limit in safe_limits.items():
        val = latest.get(field)
        if val is not None:
            if field in ["trestbps", "chol", "oldpeak"]:
                color = "green" if val <= limit else "red"
            else:  # thalach – higher is better
                color = "green" if val >= limit else "red"
            chart_data.append({
                "Field": field,
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
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.write("No numeric fields available for comparison.")

# ---------- Page routing ----------
if st.session_state.page == "dashboard":
    show_dashboard()
elif st.session_state.page == "assessment":
    show_assessment()
else:
    show_history()

st.sidebar.markdown("---")
st.sidebar.caption("⚠️ Educational demo. Not for medical use.")