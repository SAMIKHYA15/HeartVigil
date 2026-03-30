import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.graph_objects as go
import random
import string
import time
import re
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ========== PAGE CONFIG (MUST BE FIRST) ==========
st.set_page_config(
    page_title="HeartVigil AI",
    page_icon="❤️",
    layout="wide"
)

st.markdown("""
<style>
.block-container {
    padding-top: 1rem;
}
.sidebar-logo {
    text-align: center;
    padding: 20px 0;
    border-bottom: 1px solid #e0e0e0;
    margin-bottom: 20px;
}
.sidebar-logo img {
    max-width: 200px;
    width: 100%;
    height: auto;
}
</style>
""", unsafe_allow_html=True)

def show_sidebar_logo():
    """Display logo only in sidebar"""
    try:
        if os.path.exists("logo.png"):
            st.markdown("<div class='sidebar-logo'>", unsafe_allow_html=True)
            st.image("logo.png", width=180)
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='sidebar-logo'><h3>❤️ HeartVigil</h3></div>", unsafe_allow_html=True)
    except Exception:
        st.markdown("<div class='sidebar-logo'><h3>❤️ HeartVigil</h3></div>", unsafe_allow_html=True)

def show_login_logo():
    """Display logo only on login page"""
    try:
        if os.path.exists("logo.png"):
            st.image("logo.png", width=250)
            st.markdown("---")
        else:
            st.markdown("<h1 style='text-align: center;'>❤️ HeartVigil AI</h1>", unsafe_allow_html=True)
    except Exception:
        st.markdown("<h1 style='text-align: center;'>❤️ HeartVigil AI</h1>", unsafe_allow_html=True)

# ========== SESSION STATE INITIALIZATION ==========
def init_session_state():
    """Initialize all session state variables with defaults."""
    defaults = {
        "page": "dashboard",
        "auth_session": None,
        "result": None,
        "latest_data": None,
        "extracted": {},
        "otp_sent": False,
        "otp_code": None,
        "otp_timestamp": None,
        "otp_email": None,
        "otp_resend_count": 0,
        "otp_verified": False,
        "otp_error": None,
        "form_initialized": False,
        "show_reset_popover": False,
    }
    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

init_session_state()

# ========== JS HASH CONVERTER ==========
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

# ========== IMPORTS ==========
from supabase_client import supabase
from data_agent import save_health_data
from risk_agent import doctor_ai_agent
from reco_agent import generate_recommendations
import monitor_agent

# ========== AI HELPER ==========
def get_ai_response(prompt, model_name="gemini-2.0-flash"):
    return "✨ AI insights are currently being generated."

# ========== PDF EXTRACTOR ==========
def parse_pdf_health_data(uploaded_file):
    return {}

# ========== LOAD ENV ==========
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def get_secret(key: str, default=""):
    val = os.environ.get(key)
    if val is not None:
        return str(val)
    try:
        val = st.secrets.get(key, default)
        return str(val) if val is not None else str(default)
    except Exception:
        return str(default)

# ========== CUSTOM STYLE ==========
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

OTP_EXPIRY_SECONDS = 600
MAX_RESEND_ATTEMPTS = 2

# ========== EMAIL OTP FUNCTION ==========
def send_otp_email(email, otp):
    """Send 4-digit OTP via email using SMTP."""
    try:
        smtp_server = get_secret("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(get_secret("SMTP_PORT", "587"))
        sender_email = get_secret("SENDER_EMAIL", "")
        sender_password = get_secret("SENDER_PASSWORD", "")
        
        if not sender_email or not sender_password:
            print(f"[DEV] OTP for {email}: {otp}")
            return True
        
        msg = MIMEMultipart()
        msg["From"] = sender_email
        msg["To"] = email
        msg["Subject"] = "Your HeartVigil OTP Code"
        
        body = f"""
        <html>
        <body>
            <h2>HeartVigil AI - Login OTP</h2>
            <p>Your 4-digit OTP is: <b style="font-size: 24px; color: #6B46C1;">{otp}</b></p>
            <p>This OTP is valid for 10 minutes.</p>
            <p>If you didn't request this, please ignore this email.</p>
            <br>
            <p>Stay heart healthy! ❤️</p>
            <p><i>HeartVigil AI Team</i></p>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(body, "html"))
        
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
        
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")
        print(f"[DEV] OTP for {email}: {otp}")
        return True

# ========== OTP HELPERS ==========
def generate_otp(length=4):
    return "".join(random.choices(string.digits, k=length))

def is_valid_email(email):
    return bool(re.match(r"^[\w\.\+\-]+@[\w\-]+\.[a-zA-Z]{2,}$", email.strip()))

def otp_is_expired():
    if st.session_state.otp_timestamp is None:
        return True
    return (time.time() - st.session_state.otp_timestamp) > OTP_EXPIRY_SECONDS

def seconds_remaining():
    if st.session_state.otp_timestamp is None:
        return 0
    elapsed = time.time() - st.session_state.otp_timestamp
    remaining = OTP_EXPIRY_SECONDS - elapsed
    return max(0, int(remaining))

def dispatch_otp(email):
    otp = generate_otp()
    st.session_state.otp_code = otp
    st.session_state.otp_timestamp = time.time()
    st.session_state.otp_email = email
    st.session_state.otp_error = None
    return send_otp_email(email, otp)

def reset_otp_state():
    st.session_state.otp_sent = False
    st.session_state.otp_code = None
    st.session_state.otp_timestamp = None
    st.session_state.otp_email = None
    st.session_state.otp_resend_count = 0
    st.session_state.otp_verified = False
    st.session_state.otp_error = None

def create_or_get_user(email):
    """Create or retrieve user from Supabase 'users' table."""
    try:
        response = supabase.table("users").select("*").eq("email", email).execute()
        
        if response.data:
            user = response.data[0]
            return True, user, None
        else:
            new_user = supabase.table("users").insert({"email": email}).execute()
            if new_user.data:
                return True, new_user.data[0], None
            else:
                return False, None, "Failed to create user"
                
    except Exception as e:
        fallback_user = {
            "id": f"fallback_{email.replace('@', '_').replace('.', '_')}",
            "email": email,
        }
        return True, fallback_user, None

def create_pseudo_session(user_info, email):
    class _User:
        def __init__(self, uid, email):
            self.id = uid
            self.email = email
            self.phone = None
            self.created_at = None
    
    class _Session:
        def __init__(self, user):
            self.user = user
    
    uid = user_info.get("id") if isinstance(user_info, dict) else str(user_info)
    return _Session(_User(uid, email))

# ========== AUTHENTICATION ==========
def check_session():
    return st.session_state.auth_session is not None

def login_signup():
    # Show logo only on login page
    show_login_logo()
    st.markdown("### Login / Sign Up")
    st.markdown("Enter your email address to receive a 4-digit OTP.")
    
    email = st.text_input("Email Address", placeholder="you@example.com", key="auth_email")
    email_ready = is_valid_email(email)
    
    if email and not email_ready:
        st.caption("⚠️ Please enter a valid email address.")
    
    if not st.session_state.otp_sent or st.session_state.otp_email != email:
        send_btn = st.button("Send OTP", disabled=not email_ready, use_container_width=True)
        if send_btn and email_ready:
            ok = dispatch_otp(email)
            if ok:
                st.session_state.otp_sent = True
                st.session_state.otp_resend_count = 0
                st.success(f"✅ OTP sent to {email}. Valid for 10 minutes.")
                st.rerun()
            else:
                st.error("Failed to send OTP. Please try again.")
    else:
        remaining = seconds_remaining()
        if remaining > 0:
            components.html(f"""
<div style="background:#1e3a5f; border:1px solid #2d6a9f; border-radius:6px; padding:10px 16px; margin-bottom:4px;">
  OTP sent to <b>{st.session_state.otp_email}</b>.
  Expires in <b style="color:#facc15;" id="countdown">{remaining // 60:02d}:{remaining % 60:02d}</b>
</div>
<script>
  var remaining = {remaining};
  function tick() {{
    if (remaining <= 0) {{
      document.getElementById('countdown').innerHTML = 'Expired';
      return;
    }}
    var m = Math.floor(remaining / 60);
    var s = remaining % 60;
    document.getElementById('countdown').textContent = (m<10?'0':'')+m+':'+(s<10?'0':'')+s;
    remaining--;
    setTimeout(tick, 1000);
  }}
  tick();
</script>
""", height=80)
        else:
            st.warning("⏰ OTP has expired. Click **Resend OTP** to get a new one.")
        
        otp_input = st.text_input("Enter 4-digit OTP", max_chars=4, placeholder="••••", key="otp_input")
        
        if st.session_state.otp_error:
            st.error(st.session_state.otp_error)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("Verify", use_container_width=True):
                if otp_is_expired():
                    st.session_state.otp_error = "OTP has expired. Please request a new one."
                    st.rerun()
                elif otp_input.strip() != st.session_state.otp_code:
                    st.session_state.otp_error = "❌ Incorrect OTP. Please try again."
                    st.rerun()
                else:
                    success, user_info, err = create_or_get_user(st.session_state.otp_email)
                    if success:
                        st.session_state.auth_session = create_pseudo_session(user_info, st.session_state.otp_email)
                        reset_otp_state()
                        st.success("✅ Login successful!")
                        st.rerun()
                    else:
                        st.session_state.otp_error = f"Authentication error: {err}"
                        st.rerun()
        
        with col2:
            resends_left = MAX_RESEND_ATTEMPTS - st.session_state.otp_resend_count
            disabled = resends_left <= 0
            if st.button(f"Resend OTP ({resends_left} left)", disabled=disabled, use_container_width=True):
                ok = dispatch_otp(st.session_state.otp_email)
                if ok:
                    st.session_state.otp_resend_count += 1
                    st.success("OTP resent successfully!")
                    st.rerun()
                else:
                    st.error("Failed to resend OTP.")
        
        with col3:
            if st.button("Change Email", use_container_width=True):
                reset_otp_state()
                st.rerun()

def show_reset_password():
    st.title("🔐 Reset Your Password")
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
                st.error("Invalid or expired reset link")
                return
        except Exception as e:
            st.error(f"Session error: {e}")
            return

        with st.form("reset_form"):
            new_password = st.text_input("New Password", type="password")
            confirm_password = st.text_input("Confirm Password", type="password")
            submitted = st.form_submit_button("Update Password")

        if submitted:
            if new_password != confirm_password:
                st.error("Passwords do not match")
            elif len(new_password) < 6:
                st.error("Password must be at least 6 characters")
            else:
                try:
                    supabase.auth.update_user({"password": new_password})
                    st.success("✅ Password updated successfully!")
                    st.query_params.clear()
                    if st.button("🔙 Return to Login"):
                        st.session_state.auth_session = None
                        st.rerun()
                except Exception as e:
                    st.error(f"Update failed: {e}")
    else:
        st.error("Invalid or expired reset link")

def logout():
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    init_session_state()
    st.rerun()

# ========== ROUTING ==========
params = st.query_params
is_reset_flow = (params.get("access_token") or params.get("refresh_token") or
                 params.get("type") == "recovery" or params.get("token"))

if is_reset_flow:
    show_reset_password()
    st.stop()

if not check_session():
    login_signup()
    st.stop()

# ========== LOGGED IN – FULL APP ==========
user_id = st.session_state.auth_session.user.id
user_email = st.session_state.auth_session.user.email
user_created_at = getattr(st.session_state.auth_session.user, "created_at", None)

# ========== SIDEBAR WITH LOGO ==========
with st.sidebar:
    show_sidebar_logo()  # Logo only in sidebar
    st.markdown("## Navigation")
    if st.button("Dashboard", use_container_width=True):
        st.session_state.page = "dashboard"
    if st.button("Assessment", use_container_width=True):
        st.session_state.page = "assessment"
    if st.button("Risk Analysis", use_container_width=True):
        st.session_state.page = "risk_analysis"
    if st.button("Data Agent", use_container_width=True):
        st.session_state.page = "data_agent"
    if st.button("Monitoring", use_container_width=True):
        st.session_state.page = "monitoring"
    if st.button("Recommendations", use_container_width=True):
        st.session_state.page = "recommendations"
    st.markdown("---")
    st.caption("⚠️ Educational demo. Not for medical use.")

# Profile button in top right
top_col1, top_col2, top_col3 = st.columns([1, 6, 1])
with top_col3:
    with st.popover("👤 Profile", use_container_width=True):
        if user_email:
            st.write(f"**Email:** {user_email}")
        if user_created_at:
            st.write(f"**Joined:** {str(user_created_at)[:10]}")
        st.markdown("---")
        if st.button("Logout", use_container_width=True):
            logout()

# ========== VALIDATION RANGES ==========
VALID_RANGES = {
    "age": (1, 100), "sex": (0, 1), "cp": (0, 3),
    "trestbps": (80, 200), "chol": (100, 600),
    "fbs": (0, 1), "restecg": (0, 2), "thalach": (60, 220),
    "exang": (0, 1), "oldpeak": (0.0, 6.2),
    "slope": (0, 2), "ca": (0, 3), "thal": (1, 3)
}

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
                val = float(val) if '.' in val else int(val)
        except Exception:
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
        if field in data and data[field] is not None:
            if isinstance(data[field], (int, float)):
                if data[field] < low or data[field] > high:
                    errors.append(f"{field} value {data[field]} is outside the allowed range ({low}–{high})")
    return len(errors) == 0, errors

# ========== DASHBOARD (No center logo) ==========
def show_dashboard():
    st.title("Your Heart Health Dashboard")
    
    if st.session_state.result:
        result = st.session_state.result
        col1, col2 = st.columns(2)
        with col1:
            risk_label = result["risk_label"]
            color = {"LOW": "#10B981", "MEDIUM": "#F59E0B"}.get(risk_label, "#EF4444")
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
                        color = "#10B981" if val <= limit else ("#F59E0B" if val <= limit * 1.1 else "#EF4444")
                    else:
                        color = "#10B981" if val >= limit else ("#F59E0B" if val >= limit * 0.9 else "#EF4444")
                    chart_data.append({"Field": label, "Your Value": val, "Safe Limit": limit, "Color": color})
            if chart_data:
                df_chart = pd.DataFrame(chart_data)
                fig = go.Figure()
                for _, row in df_chart.iterrows():
                    fig.add_trace(go.Bar(name=row["Field"], x=[row["Field"]], y=[row["Your Value"]],
                                         marker_color=row["Color"],
                                         text=f"{row['Your Value']} (limit {row['Safe Limit']})", textposition="outside"))
                fig.update_layout(barmode="group", yaxis_title="Value", showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
        
        if st.button("Take New Assessment", use_container_width=True):
            st.session_state.page = "assessment"
            st.rerun()
    else:
        st.markdown("## Welcome to HeartVigil AI")
        st.write("Get a personalised heart health assessment in minutes.")
        st.markdown("""
        ### Features:
        - 📊 **Health Assessment**: Get your heart health risk score
        - 📈 **Monitoring**: Track your health metrics over time
        - 🤖 **AI Insights**: Personalised health recommendations
        - 📱 **Data Agent**: View your health history
        
        Start your journey to better heart health today!
        """)
        if st.button("Start Your Assessment", type="primary", use_container_width=True):
            st.session_state.page = "assessment"
            st.rerun()

# ========== ASSESSMENT (No center logo) ==========
def show_assessment():
    st.title("Heart Health Assessment")
    st.markdown("Fields marked with * are required.")

    if not st.session_state.form_initialized:
        st.session_state.form_initialized = True
        for f in ["age", "trestbps", "chol", "thalach", "oldpeak", "ca"]:
            if f not in st.session_state:
                st.session_state[f] = ""
        for s in ["sex", "cp", "fbs", "restecg", "exang", "slope", "thal"]:
            if s not in st.session_state:
                st.session_state[s] = "Select"

    def is_empty(val):
        return val == "" or val == "Select"

    with st.form("health_form"):
        col1, col2 = st.columns(2)
        missing_fields = []

        with col1:
            age = st.text_input("Age *", key="age")
            if is_empty(age): missing_fields.append("Age")
            sex_label = st.selectbox("Sex *", ["Select", "Female", "Male"], key="sex")
            if is_empty(sex_label): missing_fields.append("Sex")
            cp_options = ["Select", "Typical angina", "Atypical angina", "Non-anginal pain", "Asymptomatic"]
            cp_label = st.selectbox("Chest pain type *", cp_options, key="cp")
            if is_empty(cp_label): missing_fields.append("Chest Pain")
            trestbps = st.text_input("Resting blood pressure * (mmHg)", key="trestbps")
            if is_empty(trestbps): missing_fields.append("Blood Pressure")
            chol = st.text_input("Cholesterol * (mg/dL)", key="chol")
            if is_empty(chol): missing_fields.append("Cholesterol")
            fbs_label = st.selectbox("Fasting blood sugar > 120 mg/dL", ["Select", "No", "Yes"], key="fbs")
            restecg_label = st.selectbox("Resting ECG", ["Select", "Normal", "ST-T abnormality", "LV hypertrophy"], key="restecg")

        with col2:
            thalach = st.text_input("Max heart rate * (bpm)", key="thalach")
            if is_empty(thalach): missing_fields.append("Max Heart Rate")
            exang_label = st.selectbox("Exercise induced angina *", ["Select", "No", "Yes"], key="exang")
            if is_empty(exang_label): missing_fields.append("Exercise Angina")
            oldpeak = st.text_input("ST depression (mm)", key="oldpeak")
            slope_label = st.selectbox("Slope", ["Select", "Upsloping", "Flat", "Downsloping"], key="slope")
            ca = st.text_input("Major vessels (0-3)", key="ca")
            thal_label = st.selectbox("Thalassemia", ["Select", "Normal", "Fixed defect", "Reversible defect"], key="thal")

        all_filled = len(missing_fields) == 0
        submitted = st.form_submit_button("Analyse My Heart Health", use_container_width=True)

    if submitted:
        if not all_filled:
            st.error(f"⚠️ Mandatory fields missing: {', '.join(missing_fields)}")
            st.stop()

        try:
            data = {
                "age": int(age),
                "sex": 1 if sex_label == "Male" else 0,
                "cp": cp_options.index(cp_label) - 1,
                "trestbps": int(trestbps),
                "chol": int(chol),
                "fbs": 1 if fbs_label == "Yes" else 0,
                "restecg": ["Select", "Normal", "ST-T abnormality", "LV hypertrophy"].index(restecg_label) - 1,
                "thalach": int(thalach),
                "exang": 1 if exang_label == "Yes" else 0,
                "oldpeak": float(oldpeak) if oldpeak else 0.0,
                "slope": ["Select", "Upsloping", "Flat", "Downsloping"].index(slope_label) - 1,
                "ca": int(ca) if ca else 0,
                "thal": ["Select", "Normal", "Fixed defect", "Reversible defect"].index(thal_label)
            }
        except Exception as e:
            st.error(f"⚠️ Invalid input format: {e}")
            st.stop()

        valid, errors = validate_all_fields(data)
        if not valid:
            for err in errors:
                st.error(err)
            st.stop()

        with st.spinner("Analysing your health data..."):
            success, result = save_health_data(data, user_id)
            if not success:
                st.error(f"Failed to save data: {result}")
                st.stop()

            doctor_result = doctor_ai_agent(data)
            st.session_state.result = doctor_result
            st.session_state.latest_data = data
            st.session_state.form_initialized = False
            st.success("✅ Assessment complete!")
            st.balloons()
            st.session_state.page = "dashboard"
            st.rerun()

# ========== DATA AGENT (No center logo) ==========
def show_data_agent():
    st.title("Data Agent – Your Health Records")
    
    with st.spinner("Loading your health records..."):
        response = supabase.table("health_records").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(5).execute()
        records = response.data

    if not records:
        st.info("No assessments yet. Start your first assessment!")
        if st.button("Start Your Assessment", use_container_width=True):
            st.session_state.page = "assessment"
            st.rerun()
        return

    if len(records) >= 2:
        with st.spinner("Generating AI summary..."):
            summary = get_ai_response(f"Summarize health trends from: {records}")
            if summary:
                st.subheader("🤖 AI Summary")
                st.info(summary)

    st.subheader("Recent Assessments (last 5)")
    history_data = [{"Date": rec["created_at"][:10], "Age": rec.get("age"),
                     "Sex": "Male" if rec.get("sex") == 1 else "Female",
                     "BP": rec.get("trestbps"), "Chol": rec.get("chol"),
                     "HR": rec.get("thalach"), "Chest Pain": rec.get("cp")}
                    for rec in records]
    st.dataframe(pd.DataFrame(history_data), use_container_width=True)

    st.subheader("Comparison Chart (Latest Assessment)")
    latest = records[0]
    safe_limits = {"trestbps": ("Resting BP (mmHg)", 120, "lower"), "chol": ("Cholesterol (mg/dL)", 200, "lower"),
                   "thalach": ("Max Heart Rate (bpm)", 150, "higher"), "oldpeak": ("ST Depression", 1.0, "lower")}
    chart_data = []
    for field, (label, limit, direction) in safe_limits.items():
        val = latest.get(field)
        if val is not None:
            if direction == "lower":
                color = "#10B981" if val <= limit else ("#F59E0B" if val <= limit * 1.1 else "#EF4444")
            else:
                color = "#10B981" if val >= limit else ("#F59E0B" if val >= limit * 0.9 else "#EF4444")
            chart_data.append({"Field": label, "Your Value": val, "Safe Limit": limit, "Color": color})
    if chart_data:
        df_chart = pd.DataFrame(chart_data)
        fig = go.Figure()
        for _, row in df_chart.iterrows():
            fig.add_trace(go.Bar(name=row["Field"], x=[row["Field"]], y=[row["Your Value"]],
                                 marker_color=row["Color"],
                                 text=f"{row['Your Value']} (limit {row['Safe Limit']})", textposition="outside"))
        fig.update_layout(barmode="group", yaxis_title="Value", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

# ========== RISK ANALYSIS (No center logo) ==========
def show_risk_analysis():
    st.title("Risk Analysis")
    
    result = st.session_state.result
    if not result:
        with st.spinner("Loading latest assessment..."):
            response = supabase.table("health_records").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(1).execute()
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
        if st.button("Go to Assessment", use_container_width=True):
            st.session_state.page = "assessment"
            st.rerun()
        return

    risk_label, probability = result["risk_label"], result["probability"]
    label_color = {"LOW": "#10B981", "MEDIUM": "#F59E0B"}.get(risk_label, "#EF4444")
    
    fig = go.Figure(go.Indicator(mode="gauge+number", value=probability, domain={'x': [0, 1], 'y': [0, 1]},
                                 title={'text': "Risk Probability"},
                                 gauge={'axis': {'range': [0, 100]}, 'bar': {'color': label_color},
                                        'steps': [{'range': [0, 40], 'color': "#10B981"},
                                                  {'range': [40, 65], 'color': "#F59E0B"},
                                                  {'range': [65, 100], 'color': "#EF4444"}],
                                        'threshold': {'line': {'color': "black", 'width': 4}, 'value': probability}}))
    fig.update_layout(height=300)
    st.plotly_chart(fig, use_container_width=True)
    
    st.markdown(f"<h2 style='text-align:center;color:{label_color};'>Risk Level: {risk_label}</h2>", unsafe_allow_html=True)
    
    if result.get("reasons"):
        st.subheader("Why this risk?")
        for r in result["reasons"]:
            st.write(f"• {r}")
    
    if result.get("ai_explanation"):
        st.subheader("🤖 AI Insights")
        st.write(result["ai_explanation"])
    
    if st.button("Take New Assessment", use_container_width=True):
        st.session_state.page = "assessment"
        st.rerun()

# ========== MONITORING (No center logo) ==========
def show_monitoring():
    st.title("📈 Health Monitoring & Trends")
    st.markdown("Track your health metrics over time and receive early warnings.")

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start date", value=None, key="start_date")
    with col2:
        end_date = st.date_input("End date", value=None, key="end_date")
    start_str = start_date.isoformat() if start_date else None
    end_str = end_date.isoformat() if end_date else None
    
    with st.spinner("Fetching your health records..."):
        records = monitor_agent.get_user_history(user_id, start_str, end_str)
    
    if len(records) == 0:
        st.info("No assessments found for the selected period.")
        if st.button("Go to Assessment", use_container_width=True):
            st.session_state.page = "assessment"
            st.rerun()
        return

    st.subheader("Key Metrics")
    metrics = ["trestbps", "chol", "thalach", "oldpeak"]
    metric_labels = {"trestbps": "Resting BP (mmHg)", "chol": "Cholesterol (mg/dL)",
                     "thalach": "Max Heart Rate (bpm)", "oldpeak": "ST Depression"}
    cols = st.columns(4)
    for i, metric in enumerate(metrics):
        latest_val, percent, symbol = monitor_agent.compute_trends(records, metric)
        if latest_val is not None:
            if metric in ["trestbps", "chol", "oldpeak"]:
                color = "#EF4444" if percent > 0 else ("#10B981" if percent < 0 else "#F59E0B")
            else:
                color = "#10B981" if percent > 0 else ("#EF4444" if percent < 0 else "#F59E0B")
            delta = f"{symbol} {abs(percent):.1f}%" if percent != 0 else "No change"
            with cols[i]:
                st.metric(metric_labels[metric], f"{latest_val:.1f}" if isinstance(latest_val, float) else latest_val, delta)
        else:
            with cols[i]:
                st.metric(metric_labels[metric], "N/A")

    st.subheader("📊 Latest Values vs Safe Ranges")
    latest = records[-1]
    chart_data = monitor_agent.generate_comparison_data(latest)
    if chart_data:
        df_chart = pd.DataFrame(chart_data)
        fig = go.Figure()
        for _, row in df_chart.iterrows():
            if row["Direction"] == "lower":
                color = "#10B981" if row["Your Value"] <= row["Safe Limit"] else (
                    "#F59E0B" if row["Your Value"] <= row["Safe Limit"] * 1.1 else "#EF4444")
            else:
                color = "#10B981" if row["Your Value"] >= row["Safe Limit"] else (
                    "#F59E0B" if row["Your Value"] >= row["Safe Limit"] * 0.9 else "#EF4444")
            fig.add_trace(go.Bar(name=row["Field"], x=[row["Field"]], y=[row["Your Value"]],
                                 marker_color=color,
                                 text=f"{row['Your Value']} (limit {row['Safe Limit']})", textposition="outside"))
        fig.update_layout(barmode="group", yaxis_title="Value", showlegend=False, height=400)
        st.plotly_chart(fig, use_container_width=True)
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
                fig.add_trace(go.Scatter(x=df_sel["created_at"], y=df_sel[metric],
                                         mode='lines+markers', name='Actual',
                                         line=dict(color='#6B46C1'), marker=dict(size=8)))
                fig.add_trace(go.Scatter(x=df_sel["created_at"], y=rolling_avg,
                                         mode='lines', name='3-point Rolling Average',
                                         line=dict(color='#F59E0B', dash='dash')))
                fig.update_layout(title=f"{metric_labels[metric]} Over Time",
                                  xaxis_title="Date", yaxis_title=metric_labels[metric],
                                  hovermode='x unified', height=450)
                st.plotly_chart(fig, use_container_width=True)
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

# ========== RECOMMENDATIONS (No center logo) ==========
def show_recommendations():
    st.title("💡 Personalised Recommendations")
    st.markdown("Health advice based on your latest assessment.")

    data = st.session_state.latest_data
    if not data:
        with st.spinner("Loading your latest assessment..."):
            response = supabase.table("health_records").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(1).execute()
            if response.data:
                latest = response.data[0]
                data = {k: latest.get(k) for k in ["age","sex","cp","trestbps","chol","fbs","restecg",
                                                    "thalach","exang","oldpeak","slope","ca","thal"]}
                st.session_state.latest_data = data

    if not data:
        st.info("No health data available. Please submit an assessment first.")
        if st.button("Go to Assessment", use_container_width=True):
            st.session_state.page = "assessment"
            st.rerun()
        return

    with st.spinner("Generating personalised recommendations..."):
        recs = generate_recommendations(data)
    
    for i, rec in enumerate(recs, 1):
        st.write(f"{i}. {rec}")
    
    st.markdown("---")
    st.caption("💡 These recommendations are AI-generated and should be discussed with your healthcare provider.")

# ========== PAGE ROUTER ==========
page = st.session_state.page
if page == "dashboard":
    show_dashboard()
elif page == "assessment":
    show_assessment()
elif page == "risk_analysis":
    show_risk_analysis()
elif page == "data_agent":
    show_data_agent()
elif page == "monitoring":
    show_monitoring()
elif page == "recommendations":
    show_recommendations()
else:
    show_dashboard()