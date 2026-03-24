import streamlit as st
from supabase_client import supabase
from data_agent import save_health_data
from risk_agent import doctor_ai_agent
from reco_agent import generate_recommendations
import monitor_agent
from ai_helper import get_ai_response
import pandas as pd
import plotly.graph_objects as go

# Inject custom CSS for purple buttons
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

st.set_page_config(page_title="HeartVigil AI", layout="wide")

# ---------- SESSION STATE ----------
if "page" not in st.session_state:
    st.session_state.page = "dashboard"
if "auth_session" not in st.session_state:
    st.session_state.auth_session = None
if "result" not in st.session_state:
    st.session_state.result = None
if "latest_data" not in st.session_state:
    st.session_state.latest_data = None

# ---------- AUTHENTICATION ----------
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
    st.session_state.result = None
    st.session_state.latest_data = None
    st.rerun()

# ---------- MAIN ----------
if not check_session():
    login_signup()
    st.stop()

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
    with st.popover("👤 Profile", use_container_width=True):
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

# ---------- DASHBOARD ----------
def show_dashboard():
    st.title("Your Heart Health Dashboard")

    if st.session_state.result:
        result = st.session_state.result
        col1, col2 = st.columns(2)
        with col1:
            risk_label = result["risk_label"]
            if risk_label == "LOW":
                color = "#10B981"      # green
            elif risk_label == "MEDIUM":
                color = "#F59E0B"      # yellow
            else:
                color = "#EF4444"      # red
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
                    else:  # higher is better
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
                st.plotly_chart(fig, use_container_width=True)
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

    # Optional PDF upload placeholder
    st.markdown("### Upload Medical Report (PDF)")
    uploaded_file = st.file_uploader("Typed/digital PDF only. Values will be pre-filled below.", type=["pdf"])
    if uploaded_file is not None:
        st.info("PDF upload is a placeholder – extraction not yet implemented.")

    with st.form("health_form"):
        col1, col2 = st.columns(2)
        with col1:
            age = st.number_input("Age *", min_value=1, max_value=100, value=50)
            sex = st.selectbox("Sex *", options=[(0,"Female"), (1,"Male")], format_func=lambda x: x[1])[0]
            cp = st.selectbox("Chest pain type *", options=[(0,"Typical angina"), (1,"Atypical angina"), (2,"Non-anginal pain"), (3,"Asymptomatic")], format_func=lambda x: x[1])[0]
            trestbps = st.number_input("Resting blood pressure (mm Hg) *", min_value=80, max_value=200, value=120)
            chol = st.number_input("Cholesterol (mg/dl) *", min_value=100, max_value=600, value=200)
            fbs = st.selectbox("Fasting blood sugar > 120 mg/dl", options=[(0,"No"), (1,"Yes")], format_func=lambda x: x[1])[0]
            restecg = st.selectbox("Resting ECG results", options=[(0,"Normal"), (1,"ST-T abnormality"), (2,"Left ventricular hypertrophy")], format_func=lambda x: x[1])[0]
        with col2:
            thalach = st.number_input("Max heart rate achieved *", min_value=60, max_value=220, value=150)
            exang = st.selectbox("Exercise induced angina *", options=[(0,"No"), (1,"Yes")], format_func=lambda x: x[1])[0]
            oldpeak = st.number_input("ST depression induced by exercise", min_value=0.0, max_value=6.2, value=1.0, step=0.1)
            slope = st.selectbox("Slope of peak exercise ST segment", options=[(0,"Upsloping"), (1,"Flat"), (2,"Downsloping")], format_func=lambda x: x[1])[0]
            ca = st.number_input("Number of major vessels (0-3)", min_value=0, max_value=3, value=0)
            thal = st.selectbox("Thalassemia", options=[(1,"Normal"), (2,"Fixed defect"), (3,"Reversible defect")], format_func=lambda x: x[1])[0]
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

        success, result = save_health_data(data, user_id)
        if not success:
            st.error(f"Failed to save: {result}")
            st.stop()

        doctor_result = doctor_ai_agent(data)
        st.session_state.result = doctor_result
        st.session_state.latest_data = data

        st.success("Assessment complete!")
        st.session_state.page = "dashboard"
        st.rerun()

# ---------- DATA AGENT (HISTORY + AI SUMMARY) ----------
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

    # AI summary of trends
    if len(records) >= 2:
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
                    color = "#10B981"        # green
                elif val <= limit * 1.1:
                    color = "#F59E0B"        # yellow
                else:
                    color = "#EF4444"        # red
            else:
                if val >= limit:
                    color = "#10B981"        # green
                elif val >= limit * 0.9:
                    color = "#F59E0B"        # yellow
                else:
                    color = "#EF4444"        # red
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
        st.plotly_chart(fig, use_container_width=True)
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
    st.plotly_chart(fig, use_container_width=True)

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

# ---------- MONITORING (ENHANCED) ----------
def show_monitoring():
    st.title("📈 Health Monitoring & Trends")
    st.markdown("Track your health metrics over time and receive early warnings.")

    # Date range picker
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

    # Key Metrics Cards
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
            # Determine colour
            if metric in ["trestbps", "chol", "oldpeak"]:
                # lower is better
                if percent > 0:
                    color = "#EF4444"
                elif percent < 0:
                    color = "#10B981"
                else:
                    color = "#F59E0B"
            else:  # thalach – higher is better
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

    # Comparison Chart (latest vs safe ranges)
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
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No numeric fields available for comparison.")

    # Trend Chart
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
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning(f"No data available for {metric_labels[metric]}")
        else:
            st.warning(f"Field {metric} not found in data.")
    else:
        st.info("You have only one assessment. After your second assessment, you'll see trend charts here.")

    # Alerts
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

    # AI Summary
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