import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.graph_objects as go
import random
import string
import time
import re
import requests
import os
from supabase_client import supabase
from data_agent import save_health_data
from risk_agent import doctor_ai_agent
from reco_agent import generate_recommendations
import monitor_agent

# ========== AI HELPER (Placeholder) ==========
def get_ai_response(prompt, model_name="gemini-2.0-flash"):
    return "✨ AI insights are currently being generated. Stay tuned for personalised health recommendations!"

# ========== PDF EXTRACTOR (Placeholder) ==========
def parse_pdf_health_data(uploaded_file):
    return {}

# ========== PAGE CONFIG ==========
st.set_page_config(page_title="HeartVigil AI", layout="wide")

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

# ========== LOAD ENV ==========
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def get_secret(key: str, default=""):
    """Returns secret from environment or st.secrets (always returns string)."""
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
.otp-box input {
    letter-spacing: 0.3em;
    font-size: 1.4em;
    text-align: center;
}
</style>
""", unsafe_allow_html=True)

# ========== COUNTRY CODES ==========
COUNTRY_CODES = [
    ("Afghanistan", "+93"), ("Albania", "+355"), ("Algeria", "+213"),
    ("Argentina", "+54"), ("Australia", "+61"), ("Austria", "+43"),
    ("Bangladesh", "+880"), ("Belgium", "+32"), ("Brazil", "+55"),
    ("Canada", "+1"), ("Chile", "+56"), ("China", "+86"),
    ("Colombia", "+57"), ("Czech Republic", "+420"), ("Denmark", "+45"),
    ("Egypt", "+20"), ("Ethiopia", "+251"), ("Finland", "+358"),
    ("France", "+33"), ("Germany", "+49"), ("Ghana", "+233"),
    ("Greece", "+30"), ("Hungary", "+36"), ("India", "+91"),
    ("Indonesia", "+62"), ("Iran", "+98"), ("Iraq", "+964"),
    ("Ireland", "+353"), ("Israel", "+972"), ("Italy", "+39"),
    ("Japan", "+81"), ("Jordan", "+962"), ("Kenya", "+254"),
    ("Malaysia", "+60"), ("Mexico", "+52"), ("Morocco", "+212"),
    ("Myanmar", "+95"), ("Nepal", "+977"), ("Netherlands", "+31"),
    ("New Zealand", "+64"), ("Nigeria", "+234"), ("Norway", "+47"),
    ("Pakistan", "+92"), ("Peru", "+51"), ("Philippines", "+63"),
    ("Poland", "+48"), ("Portugal", "+351"), ("Romania", "+40"),
    ("Russia", "+7"), ("Saudi Arabia", "+966"), ("Singapore", "+65"),
    ("South Africa", "+27"), ("South Korea", "+82"), ("Spain", "+34"),
    ("Sri Lanka", "+94"), ("Sweden", "+46"), ("Switzerland", "+41"),
    ("Taiwan", "+886"), ("Tanzania", "+255"), ("Thailand", "+66"),
    ("Turkey", "+90"), ("Uganda", "+256"), ("Ukraine", "+380"),
    ("United Arab Emirates", "+971"), ("United Kingdom", "+44"),
    ("United States", "+1"), ("Vietnam", "+84"),
]
COUNTRY_OPTIONS = [f"{name} ({code})" for name, code in COUNTRY_CODES]
DEFAULT_COUNTRY_INDEX = next((i for i, (name, _) in enumerate(COUNTRY_CODES) if name == "India"), 0)

OTP_EXPIRY_SECONDS = 600
MAX_RESEND_ATTEMPTS = 2

# ========== SESSION STATE ==========
defaults = {
    "page": "dashboard",
    "auth_session": None,
    "result": None,
    "latest_data": None,
    "extracted": {},
    "show_reset_popover": False,
    "otp_sent": False,
    "otp_code": None,
    "otp_timestamp": None,
    "otp_contact": None,
    "otp_resend_count": 0,
    "otp_verified": False,
    "otp_error": None,
    "login_method": "Email",
    "auth_mode": "login",
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ========== OTP HELPERS ==========
def generate_otp(length=4):
    return "".join(random.choices(string.digits, k=length))

def is_valid_email(email):
    return bool(re.match(r"^[\w\.\+\-]+@[\w\-]+\.[a-zA-Z]{2,}$", email.strip()))

def is_valid_phone(phone):
    return bool(re.match(r"^\d{10}$", phone.strip()))

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

def send_otp_email(email, otp):
    """Send OTP via email using native Supabase OTP or fallback to console."""
    use_native = get_secret("SUPABASE_USE_NATIVE_OTP", "false").lower() == "true"
    if use_native:
        try:
            supabase.auth.sign_in_with_otp({
                "email": email,
                "options": {"should_create_user": True}
            })
            st.session_state.otp_code = "__SUPABASE_NATIVE__"
            return True
        except Exception as e:
            print(f"[EMAIL OTP ERROR] {e}")
            return False
    # Fallback: print to console (dev mode)
    print(f"[DEV – OTP for {email}: {otp}")
    return True

def send_otp_sms(phone_with_isd, otp):
    """Send OTP via SMS using Fast2SMS or fallback to console."""
    local_number = phone_with_isd.lstrip("+")
    if local_number.startswith("91") and len(local_number) == 12:
        local_number = local_number[2:]
    fast2sms_key = get_secret("FAST2SMS_API_KEY", "")
    if fast2sms_key and fast2sms_key != "" and len(local_number) == 10:
        try:
            resp = requests.post(
                "https://www.fast2sms.com/dev/bulkV2",
                headers={"authorization": fast2sms_key},
                json={"route": "otp", "variables_values": otp, "numbers": local_number, "flash": 0},
                timeout=10
            )
            return resp.json().get("return", False)
        except Exception as e:
            print(f"[SMS ERROR] {e}")
            return False
    # Fallback: print to console (dev mode)
    print(f"[DEV – OTP for {phone_with_isd}: {otp}")
    return True

def dispatch_otp(contact, method):
    otp = generate_otp()
    st.session_state.otp_code = otp
    st.session_state.otp_timestamp = time.time()
    st.session_state.otp_contact = contact
    st.session_state.otp_error = None
    if method == "Email":
        return send_otp_email(contact, otp)
    else:
        return send_otp_sms(contact, otp)

def reset_otp_state():
    st.session_state.otp_sent = False
    st.session_state.otp_code = None
    st.session_state.otp_timestamp = None
    st.session_state.otp_contact = None
    st.session_state.otp_resend_count = 0
    st.session_state.otp_verified = False
    st.session_state.otp_error = None

def resolve_session_after_otp(contact, method):
    try:
        if method == "Email":
            return True, {"email": contact, "id": contact}, None
        else:
            return True, {"phone": contact, "id": contact}, None
    except Exception as e:
        return False, None, str(e)

def _build_pseudo_session(user_info, contact, method):
    class _User:
        def __init__(self, uid, email, phone):
            self.id = uid
            self.email = email
            self.phone = phone
            self.created_at = None
    class _Session:
        def __init__(self, user):
            self.user = user
            self.access_token = None
            self.refresh_token = None
    uid = user_info.get("id", contact)
    email = contact if method == "Email" else None
    phone = contact if method == "Phone" else None
    return _Session(_User(uid, email, phone))

def _clear_form_state():
    keys_to_clear = ["age", "sex", "cp", "trestbps", "chol", "fbs", "restecg",
                     "thalach", "exang", "oldpeak", "slope", "ca", "thal"]
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
    st.session_state.extracted = {}

# ========== AUTHENTICATION ==========
def check_session():
    return st.session_state.auth_session is not None

def login_signup():
    st.title("HeartVigil AI")
    tab_login, tab_signup = st.tabs(["Login", "Sign Up"])

    for tab, mode in [(tab_login, "login"), (tab_signup, "signup")]:
        with tab:
            _render_otp_panel(mode)

def _render_otp_panel(mode: str):
    label = "Login" if mode == "login" else "Sign Up"
    method = st.radio("Login with", ["Email", "Phone Number"], horizontal=True, key=f"{mode}_method")
    contact_ready = False
    contact = ""

    if method == "Email":
        email_input = st.text_input("Email Address", placeholder="you@example.com", key=f"{mode}_email")
        contact = email_input.strip()
        contact_ready = is_valid_email(contact)
        if contact and not contact_ready:
            st.caption("⚠️ Please enter a valid email address.")
    else:
        col_country, col_phone = st.columns([2, 3])
        with col_country:
            country_choice = st.selectbox("Country", COUNTRY_OPTIONS, index=DEFAULT_COUNTRY_INDEX, key=f"{mode}_country")
        with col_phone:
            phone_input = st.text_input("Phone Number (10 digits)", placeholder="9876543210", max_chars=10, key=f"{mode}_phone")
        isd_code = COUNTRY_CODES[COUNTRY_OPTIONS.index(country_choice)][1]
        local_phone = phone_input.strip()
        contact = f"{isd_code}{local_phone}"
        contact_ready = is_valid_phone(local_phone)
        if local_phone and not contact_ready:
            st.caption("⚠️ Enter exactly 10 digits (no spaces or dashes).")

    method_key = "Email" if method == "Email" else "Phone"

    if not st.session_state.otp_sent or st.session_state.otp_contact != contact:
        send_btn = st.button(f"Send OTP", key=f"{mode}_send_otp", disabled=not contact_ready, use_container_width=True)
        if send_btn and contact_ready:
            ok = dispatch_otp(contact, method_key)
            if ok:
                st.session_state.otp_sent = True
                st.session_state.otp_resend_count = 0
                st.session_state.auth_mode = mode
                st.success(f"✅ OTP sent to your {method.lower()}. Valid for 10 minutes.")
                st.rerun()
            else:
                st.error("Failed to send OTP. Please try again.")
    else:
        remaining = seconds_remaining()
        if remaining > 0:
            components.html(f"""
<div id="otp-banner" style="background:#1e3a5f; border:1px solid #2d6a9f; border-radius:6px; padding:10px 16px; font-size:15px; color:#90caf9; margin-bottom:4px;">
  OTP sent to <b style="color:#ffffff">{st.session_state.otp_contact}</b>.
  Expires in <b id="countdown" style="color:#facc15; font-size:16px;">--:--</b>
</div>
<script>
  var remaining = {remaining};
  function tick() {{
    if (remaining <= 0) {{
      document.getElementById('otp-banner').innerHTML = '⏰ <b>OTP has expired.</b> Click <b>Resend OTP</b> below.';
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
""", height=60)
        else:
            st.warning("⏰ OTP has expired. Click **Resend OTP** to get a new one.")

        otp_input = st.text_input("Enter 4-digit OTP", max_chars=4, placeholder="••••", key=f"{mode}_otp_input")
        if st.session_state.otp_error:
            st.error(st.session_state.otp_error)

        verify_col, resend_col, change_col = st.columns([1, 1, 1])

        with verify_col:
            if st.button(f"Verify & {label}", key=f"{mode}_verify", use_container_width=True):
                if otp_is_expired():
                    st.session_state.otp_error = "OTP has expired. Please request a new one."
                    st.rerun()
                elif otp_input.strip() != st.session_state.otp_code:
                    st.session_state.otp_error = "❌ Incorrect OTP. Please try again."
                    st.rerun()
                else:
                    success, user_info, err = resolve_session_after_otp(st.session_state.otp_contact, method_key)
                    if success:
                        st.session_state.auth_session = _build_pseudo_session(user_info, st.session_state.otp_contact, method_key)
                        _clear_form_state()
                        reset_otp_state()
                        st.success("✅ Logged in successfully!")
                        st.rerun()
                    else:
                        st.session_state.otp_error = f"Authentication error: {err}"
                        st.rerun()

        with resend_col:
            resends_left = MAX_RESEND_ATTEMPTS - st.session_state.otp_resend_count
            if st.button(f"Resend OTP ({resends_left} left)", key=f"{mode}_resend", disabled=resends_left <= 0, use_container_width=True):
                ok = dispatch_otp(st.session_state.otp_contact, method_key)
                if ok:
                    st.session_state.otp_resend_count += 1
                    st.success("OTP resent successfully!")
                    st.rerun()
                else:
                    st.error("Failed to resend OTP.")

        with change_col:
            if st.button("Change Contact", key=f"{mode}_change", use_container_width=True):
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
user_phone = getattr(st.session_state.auth_session.user, "phone", None)
user_created_at = getattr(st.session_state.auth_session.user, "created_at", None)

# ========== TOP BAR ==========
top_col1, top_col2, top_col3 = st.columns([1, 4, 1])
with top_col1:
    pass
with top_col2:
    st.title("HeartVigil AI")
with top_col3:
    with st.popover("👤 Profile", width='stretch'):
        if user_email:
            st.write(f"**Email:** {user_email}")
        if user_phone:
            st.write(f"**Phone:** {user_phone}")
        if user_created_at:
            st.write(f"**Joined:** {str(user_created_at)[:10]}")
        if st.button("Logout"):
            logout()

# ========== SIDEBAR ==========
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

# ========== DASHBOARD ==========
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
                st.plotly_chart(fig, width='stretch')
        if st.button("Take New Assessment"):
            st.session_state.page = "assessment"
            st.rerun()
    else:
        st.markdown("## Welcome to HeartVigil AI")
        st.write("Get a personalised heart health assessment in minutes.")
        if st.button("Start Your Assessment", type="primary"):
            st.session_state.page = "assessment"
            st.rerun()

# ========== ASSESSMENT ==========
def show_assessment():
    st.title("Heart Health Assessment")
    st.markdown("Fields marked with * are required.")

    if "form_initialized" not in st.session_state:
        st.session_state.form_initialized = True
        for f in ["age", "trestbps", "chol", "thalach", "oldpeak", "ca"]:
            st.session_state[f] = ""
        for s in ["sex", "cp", "fbs", "restecg", "exang", "slope", "thal"]:
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
            trestbps = st.text_input("Resting blood pressure *", key="trestbps")
            if is_empty(trestbps): missing_fields.append("Blood Pressure")
            chol = st.text_input("Cholesterol *", key="chol")
            if is_empty(chol): missing_fields.append("Cholesterol")
            fbs_label = st.selectbox("Fasting blood sugar", ["Select", "No", "Yes"], key="fbs")
            restecg_label = st.selectbox("Resting ECG", ["Select", "Normal", "ST-T abnormality", "LV hypertrophy"], key="restecg")

        with col2:
            thalach = st.text_input("Max heart rate *", key="thalach")
            if is_empty(thalach): missing_fields.append("Max Heart Rate")
            exang_label = st.selectbox("Exercise induced angina *", ["Select", "No", "Yes"], key="exang")
            if is_empty(exang_label): missing_fields.append("Exercise Angina")
            oldpeak = st.text_input("ST depression", key="oldpeak")
            slope_label = st.selectbox("Slope", ["Select", "Upsloping", "Flat", "Downsloping"], key="slope")
            ca = st.text_input("Major vessels", key="ca")
            thal_label = st.selectbox("Thalassemia", ["Select", "Normal", "Fixed defect", "Reversible defect"], key="thal")

        all_filled = len(missing_fields) == 0
        submitted = st.form_submit_button("Analyse My Heart Health")

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
        except Exception:
            st.error("⚠️ Invalid input format.")
            st.stop()

        valid, errors = validate_all_fields(data)
        if not valid:
            for err in errors:
                st.error(err)
            st.stop()

        success, result = save_health_data(data, user_id)
        if not success:
            st.error(f"Failed: {result}")
            st.stop()

        doctor_result = doctor_ai_agent(data)
        st.session_state.result = doctor_result
        st.session_state.latest_data = data
        st.session_state.form_initialized = False
        st.success("✅ Assessment complete!")
        st.session_state.page = "dashboard"
        st.rerun()

# ========== DATA AGENT (HISTORY) ==========
def show_data_agent():
    st.title("Data Agent – Your Health Records")
    response = supabase.table("health_records").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(5).execute()
    records = response.data

    if not records:
        st.info("No assessments yet. Start your first assessment!")
        if st.button("Start Your Assessment"):
            st.session_state.page = "assessment"
            st.rerun()
        return

    if len(records) >= 2:
        summary = get_ai_response(f"Summarize health trends from: {records}")
        if summary:
            st.subheader("AI Summary")
            st.info(summary)

    st.subheader("Recent Assessments (last 5)")
    history_data = [{"Date": rec["created_at"][:10], "Age": rec.get("age"),
                     "Sex": "Male" if rec.get("sex") == 1 else "Female",
                     "BP": rec.get("trestbps"), "Chol": rec.get("chol"),
                     "HR": rec.get("thalach"), "Chest Pain": rec.get("cp")}
                    for rec in records]
    st.table(pd.DataFrame(history_data))

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
        st.plotly_chart(fig, width='stretch')

# ========== RISK ANALYSIS ==========
def show_risk_analysis():
    st.title("Risk Analysis")
    result = st.session_state.result
    if not result:
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
        if st.button("Go to Assessment"):
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
    st.plotly_chart(fig, width='stretch')
    st.markdown(f"<h2 style='text-align:center;color:{label_color};'>Risk Level: {risk_label}</h2>", unsafe_allow_html=True)
    if result.get("reasons"):
        st.subheader("Why this risk?")
        for r in result["reasons"]:
            st.write(f"• {r}")
    if result.get("ai_explanation"):
        st.subheader("AI Insights")
        st.write(result["ai_explanation"])
    if st.button("Take New Assessment"):
        st