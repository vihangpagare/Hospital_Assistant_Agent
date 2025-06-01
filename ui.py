# ui.py

import sqlite3
import streamlit as st
import pandas as pd

from main import healthcare_assistant, HumanMessage, db

# --- Page config ---
st.set_page_config(
    page_title="Healthcare Assistant",
    layout="wide",
    page_icon="🩺"
)

# --- CSS for profile card ---
st.markdown("""
<style>
.profile-card {
    background-color: #ffffff;
    border: 1px solid #e0e0e0;
    border-radius: 12px;
    padding: 24px;
    max-width: 500px;
    margin: auto;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
.profile-card h2 {
    font-size: 24px;
    color: #2c3e50;
    margin-bottom: 18px;
    text-align: center;
}
.profile-row {
    display: flex;
    justify-content: space-between;
    margin-bottom: 12px;
}
.profile-label {
    font-weight: bold;
    color: #555;
}
.profile-value {
    color: #222;
    text-align: right;
    flex: 1;
    margin-left: 12px;
}
@media (max-width: 600px) {
    .profile-card { padding: 16px; }
    .profile-row { flex-direction: column; }
    .profile-value { margin-left: 0; margin-top: 4px; }
}
</style>
""", unsafe_allow_html=True)
import streamlit as st

def render_profile(profile: dict):
    """Render patient profile as a styled card with white text."""
    
    # Define custom CSS for styling
    st.markdown("""
        <style>
            .profile-card {
                background-color: #2c2f33;
                padding: 20px;
                border-radius: 10px;
                color: white;
            }
            .profile-row {
                margin-bottom: 10px;
            }
            .profile-label {
                font-weight: bold;
                margin-right: 10px;
                display: inline-block;
                width: 150px;
                color: white;
            }
            .profile-value {
                color: white;
            }
        </style>
    """, unsafe_allow_html=True)

    # Start profile card
    #st.markdown('<div class="profile-card">', unsafe_allow_html=True)
    
    st.markdown(f'<h2 style="color: white;">{profile["first_name"]} {profile["last_name"]}</h2>', unsafe_allow_html=True)
    
    fields = [
        ("Date of Birth", profile["date_of_birth"]),
        ("Gender", profile["gender"]),
        ("Contact", profile["contact_number"]),
        ("Email", profile["email"]),
        ("Address", profile["address"]),
        ("Emergency Contact", f'{profile["emergency_contact_name"]} ({profile["emergency_contact_number"]})'),
        ("Insurance ID", profile["insurance_id"]),
        ("Registered On", profile["registration_date"])
    ]
    
    for label, value in fields:
        st.markdown(
            f'<div class="profile-row">'
            f'<span class="profile-label">{label}</span>'
            f'<span class="profile-value">{value}</span>'
            f'</div>',
            unsafe_allow_html=True
        )

    st.markdown('</div>', unsafe_allow_html=True)


# --- Sidebar login ---
with st.sidebar:
    st.header("Patient Login")
    pid = st.text_input("Enter your Patient ID", value=st.session_state.get("patient_id", ""))
    if st.button("Login"):
        if pid.isdigit():
            st.session_state["patient_id"] = pid
            st.session_state["messages"] = []
            st.success(f"Logged in as Patient #{pid}")
        else:
            st.error("Please enter a valid numeric Patient ID")

if not st.session_state.get("patient_id"):
    st.warning("Please log in with your Patient ID to access your data.")
    st.stop()

patient_id = int(st.session_state["patient_id"])

# --- Main tabs ---
tabs = st.tabs([
    "💬 Chat Assistant",
    "👤 Your Profile",
    "📅 Upcoming Appointments",
    "📑 Medical Records"
])

# --- Tab 1: Chat Assistant ---
with tabs[0]:
    st.subheader("AI Healthcare Chat")
    if "messages" not in st.session_state:
        st.session_state["messages"] = []

    for msg in st.session_state["messages"]:
        st.chat_message(msg["role"]).write(msg["content"])

    user_input = st.chat_input("Type your message here...")
    if user_input:
        # append user
        st.session_state["messages"].append({"role": "user", "content": user_input})

        # prepare state & config
        state = {
            "messages": [
                HumanMessage(content=m["content"])
                if m["role"] == "user" else m["content"]
                for m in st.session_state["messages"]
            ],
            "patient_info": {"patient_id": patient_id},
            "current_appointment": None,
            "current_node": "patient_interaction",
            "emergency_detected": False,
            "tool_results": {},
            "intent": None,
        }
        config = {"configurable": {"thread_id": patient_id, "user_id": patient_id}}

        # stream assistant response
        assistant_response = ""
        for chunk in healthcare_assistant.stream(state, config, stream_mode="values"):
            last = chunk["messages"][-1]
            assistant_response = last.content if hasattr(last, "content") else str(last)

        # append assistant
        st.session_state["messages"].append({"role": "assistant", "content": assistant_response})

        # if booking confirmed, rerun to refresh appointments
        if "appointment booked" in assistant_response.lower() or "confirmed" in assistant_response.lower():
            st.rerun()
        else:
            st.rerun()

# --- Tab 2: Profile ---
with tabs[1]:
    st.subheader("Your Profile")
    # fetch and convert to dict
    db.conn.row_factory = sqlite3.Row
    cursor = db.conn.cursor()
    cursor.execute("SELECT * FROM Patients WHERE patient_id = ?", (patient_id,))
    row = cursor.fetchone()
    if row:
        profile = dict(row)
        render_profile(profile)
    else:
        st.info("No profile found.")

# --- Tab 3: Upcoming Appointments ---
with tabs[2]:
    st.subheader("Your Upcoming Appointments")
    upcoming = db.get_upcoming_appointments(patient_id)
    if upcoming:
        df = pd.DataFrame(upcoming)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("You have no upcoming appointments.")

# --- Tab 4: Medical Records ---
with tabs[3]:
    st.subheader("Your Past Appointments and Medical Records")

    # Fetch and show past appointments
    past_appts = db.get_past_appointments(patient_id)
    if past_appts:
        st.markdown("**Past Appointments**")
        df_appts = pd.DataFrame(past_appts)
        st.dataframe(df_appts, use_container_width=True)
    else:
        st.info("You have no past appointments on record.")

    # Divider
    st.markdown("---")

    # Fetch and show medical records
    records = db.get_medical_history(patient_id)
    if records:
        st.markdown("**Medical Records**")
        df_records = pd.DataFrame(records)
        st.dataframe(df_records, use_container_width=True)
    else:
        st.info("No medical records found.")
