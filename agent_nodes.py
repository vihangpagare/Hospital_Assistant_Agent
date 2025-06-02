"""
agent_nodes.py

Defines all node functions and the HealthcareState class for the
LangGraph-based Healthcare AI Assistant workflow.
"""
import os 
import re
import random
from datetime import datetime
from typing import Optional, Tuple, Dict, Any, List
from exa_py import Exa
from pydantic import BaseModel, Field
from typing_extensions import Annotated
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.runnables import RunnableConfig

from database import DatabaseManager
from prompts import (
    SYSTEM_PROMPT,
    CLASSIFY_INTENT_PROMPT,
    GET_DATE_PROMPT,
    EXTRACT_DATE_TIME_PROMPT,
    NON_URGENT_SYMPTOM_PROMPT,
    SYMPTOM_TRIAGE_PROMPT,
)
from langchain_anthropic import ChatAnthropic

# ─────── Instantiate DatabaseManager ─────────────────────────────────────────────
db = DatabaseManager()

# ─────── LLM Setup ───────────────────────────────────────────────────────────────
# In each node, we’ll create a new ChatAnthropic instance (as done originally)
# so that the prompts are provided fresh. You can adapt this if you prefer to reuse.
def _new_anthropic_llm():
    return ChatAnthropic(
        model="claude-3-haiku-20240307",
        temperature=1,
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", "")
    )


# ─────── Helper: Extract date & time from free text ──────────────────────────────
def extract_date_time(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Returns (date_iso, time_hhmm) or (None, None) if not found.
    Uses the LLM with EXTRACT_DATE_TIME_PROMPT.
    """
    now = datetime.now()
    prompt = EXTRACT_DATE_TIME_PROMPT.format(
        current_datetime=now.strftime("%Y-%m-%d %H:%M"),
        text=text
    )
    llm = ChatAnthropic(
        model="claude-3-haiku-20240307",
        temperature=1,
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", "")
    )
    resp = llm.invoke([
        SystemMessage(content="Date/time extraction assistant with context."),
        HumanMessage(content=prompt)
    ]).content.strip()

    # Parse JSON-like output
    m_date = re.search(r'"date"\s*:\s*"?([^",}]+)"?', resp)
    m_time = re.search(r'"time"\s*:\s*"?([^",}]+)"?', resp)
    date_val = m_date.group(1) if m_date and m_date.group(1).lower() != "null" else None
    time_val = m_time.group(1) if m_time and m_time.group(1).lower() != "null" else None
    return date_val, time_val


# ─────── Helper: Resolve NL date to ISO ───────────────────────────────────────────
def get_date_from_natural_language(reference_date: datetime, text: str) -> Optional[datetime]:
    """
    Uses the LLM with GET_DATE_PROMPT to resolve relative/absolute dates.
    Returns a datetime or None.
    """
    prompt = GET_DATE_PROMPT.format(
        reference_date=reference_date.strftime("%Y-%m-%d"),
        text=text
    )
    llm = ChatAnthropic(
        model="claude-3-haiku-20240307",
        temperature=1,
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", "")
    )
    reply = llm.invoke([
        SystemMessage(content="Natural language date solver."),
        HumanMessage(content=prompt)
    ]).content.strip()

    if reply.lower() == 'null':
        return None
    try:
        return datetime.strptime(reply, "%Y-%m-%d")
    except ValueError:
        return None


# ─────── Helper: Extract doctor name from text ────────────────────────────────────
def extract_doctor(text: str) -> Optional[str]:
    """
    Looks for patterns like 'Dr. Smith' or 'dr smith' in the user’s message.
    Returns None if not found.
    """
    m = re.search(r"dr\.?\s+([A-Za-z]+(?:\s+[A-Za-z]+)*)", text, re.IGNORECASE)
    if m:
        return "Dr. " + m.group(1).strip()
    return None


# ─────── Node: Classify Intent ────────────────────────────────────────────────────
def classify_intent(state: dict, llm) -> str:
    """
    Takes the last user message (state['messages'][-1]) and returns one of:
    'symptom', 'booking', 'cancellation', 'rescheduling', 'records', 'general_inquiry'
    """
    user_message = state["messages"][-1].content if state["messages"] else ""
    prompt = CLASSIFY_INTENT_PROMPT.format(user_message=user_message)
    model = ChatAnthropic(
        model="claude-3-haiku-20240307",
        temperature=1,
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", "")
    )
    response = model.invoke([
        SystemMessage(content="Healthcare intent classifier."),
        HumanMessage(content=prompt)
    ]).content.strip().lower()

    valid_intents = {"symptom", "booking", "cancellation", "rescheduling", "records", "general_inquiry"}
    return response.split()[0] if response.split()[0] in valid_intents else "general_inquiry"


# ─────── Node: Patient Interaction (Entry Point) ─────────────────────────────────
def patient_interaction_node(state: "HealthcareState", config: RunnableConfig) -> Dict[str, Any]:
    """
    Classifies intent but does not generate a full response. It merely sets
    state["intent"] and state["current_node"] so that routing can occur.
    """
    intent = classify_intent(state, llm=None)
    return {
        "messages": state["messages"],  # no new message here
        "intent": intent,
        "current_node": "patient_interaction"
    }


# ─────── Node: Symptom Triage ─────────────────────────────────────────────────────
def symptom_triage_node(state: "HealthcareState", config: RunnableConfig) -> Dict[str, Any]:
    """
    Uses SYMPTOM_TRIAGE_PROMPT to decide if an “emergency” or “non_urgent” scenario.
    """
    user_message = state["messages"][-1].content
    # Use hospital manual vectorstore retrieval in UI; here we just pass a placeholder context
    medical_context = "Relevant medical information has been preloaded."

    prompt = SYMPTOM_TRIAGE_PROMPT.format(
        user_symptoms=user_message,
        medical_context=medical_context
    )
    llm = ChatAnthropic(
        model="claude-3-haiku-20240307",
        temperature=1,
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", "")
    )
    verdict = llm.invoke([
        SystemMessage(content="Symptom triage classifier."),
        HumanMessage(content=prompt)
    ]).content.strip().lower()

    emergency_detected = True if "emergency" in verdict else False
    return {
        "messages": [AIMessage(content="Analyzing your symptoms…")],
        "current_node": "symptom_triage",
        "emergency_detected": emergency_detected
    }


# ─────── Node: Emergency Response ─────────────────────────────────────────────────
def emergency_response_node(state: "HealthcareState", config: RunnableConfig) -> Dict[str, Any]:
    """
    If emergency_detected == True, respond with an emergency instruction.
    """
    emergency_info = (
        "EMERGENCY DETECTED!\n"
        "Call emergency services (e.g., 911 or your local equivalent) immediately. "
        "Do not delay seeking help. If possible, have someone stay with you until help arrives."
    )
    return {
        "messages": [AIMessage(content=emergency_info)],
        "current_node": "emergency_response",
        "emergency_detected": True
    }


# ─────── Node: Non-Urgent Symptom Suggestions ─────────────────────────────────────
def non_urgent_symptom_suggestions_node(state: "HealthcareState", config: RunnableConfig) -> Dict[str, Any]:
    """
    Provides home-care advice if emergency_detected == False.
    Retrieves one page of hospital manual (placeholder) and calls LLM with NON_URGENT_SYMPTOM_PROMPT.
    """
    user_message = state["messages"][-1].content
    # In a real implementation, you’d retrieve from a vectorstore. Here we pass placeholder text.
    medical_context = "Relevant document snippet (e.g., hospital manual) loaded."

    prompt = NON_URGENT_SYMPTOM_PROMPT.format(
        user_symptoms=user_message,
        medical_context=medical_context
    )
    llm = ChatAnthropic(
        model="claude-3-haiku-20240307",
        temperature=1,
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", "")
    )
    advice = llm.invoke([
        SystemMessage(content="Non-urgent symptom advice assistant."),
        HumanMessage(content=prompt)
    ]).content.strip()

    return {
        "messages": [AIMessage(content=advice)],
        "current_node": "non_urgent_symptom_suggestions"
    }


# ─────── Node: Booking Appointment ────────────────────────────────────────────────
def booking_appointment_node(state: "HealthcareState", config: RunnableConfig) -> Dict[str, Any]:
    """
    Extracts doctor, date, time, purpose from the user message.
    If missing, picks defaults. Then calls db.book_appointment(...).
    """
    user_message = state["messages"][-1].content
    patient_id = config["configurable"]["user_id"]

    # 1. Extract doctor name if present
    doctor_pref = extract_doctor(user_message)

    # 2. Extract date/time using extract_date_time
    date_str, time_str = extract_date_time(user_message)
    if not date_str:
        date_str = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    if not time_str:
        time_str = "09:00"  # default to 9:00 if not provided

    # 3. Purpose: look for 'for X' or fallback
    m = re.search(r"(for|about|regarding)\s+([A-Za-z0-9 ]+)", user_message, re.IGNORECASE)
    purpose = m.group(2).strip() if m else "General consultation"

    # 4. If doctor not found, pick a random available doctor
    if not doctor_pref:
        available_doctors = db.get_available_doctors()
        doctor_pref = random.choice(available_doctors) if available_doctors else "Dr. Smith"

    # 5. Book with DatabaseManager
    result = db.book_appointment(patient_id, doctor_pref, date_str, time_str, purpose)
    confirmation = (
        f"Appointment booked! ID: {result['appointment_id']}\n"
        f"Doctor: {result['doctor']}\n"
        f"Date: {result['date']}, Time: {result['time']}\n"
        f"Status: {result['status']}"
    )
    return {
        "messages": [AIMessage(content=confirmation)],
        "current_node": "booking_appointment"
    }


# ─────── Node: Cancel Appointment ──────────────────────────────────────────────────
def cancelling_appointment_node(state: "HealthcareState", config: RunnableConfig) -> Dict[str, Any]:
    """
    Expects the user to mention an appointment_id. Cancels it via db.cancel_appointment(...).
    """
    user_message = state["messages"][-1].content
    m = re.search(r"\b\d+\b", user_message)  # find first number = appointment_id
    if not m:
        return {
            "messages": [AIMessage(content="Please specify the appointment ID to cancel.")],
            "current_node": "cancelling_appointment"
        }
    appointment_id = int(m.group())
    result = db.cancel_appointment(appointment_id)
    reply = (
        f"Cancellation status: {result['status']}.\n"
        f"Message: {result.get('message', '')}"
    )
    return {
        "messages": [AIMessage(content=reply)],
        "current_node": "cancelling_appointment"
    }


# ─────── Node: Reschedule Appointment ──────────────────────────────────────────────
def rescheduling_appointment_node(state: "HealthcareState", config: RunnableConfig) -> Dict[str, Any]:
    """
    Expects user to provide appointment_id and new date/time. Uses extract_date_time.
    """
    user_message = state["messages"][-1].content
    m_id = re.search(r"\b\d+\b", user_message)
    if not m_id:
        return {
            "messages": [AIMessage(content="Please specify the appointment ID to reschedule.")],
            "current_node": "rescheduling_appointment"
        }

    appointment_id = int(m_id.group())
    # Extract new date/time
    date_str, time_str = extract_date_time(user_message)
    if not date_str:
        return {
            "messages": [AIMessage(content="Please specify the new date for rescheduling.")],
            "current_node": "rescheduling_appointment"
        }
    if not time_str:
        time_str = "09:00"

    result = db.reschedule_appointment(appointment_id, date_str, time_str)
    reply = (
        f"Reschedule status: {result['status']}.\n"
        f"Doctor: {result.get('doctor','')}\n"
        f"New Date: {result.get('new_date','')} Time: {result.get('new_time','')}\n"
        f"{result.get('message','')}"
    )
    return {
        "messages": [AIMessage(content=reply)],
        "current_node": "rescheduling_appointment"
    }


# ─────── Node: Patient Records Access ──────────────────────────────────────────────
def patient_records_access_node(state: "HealthcareState", config: RunnableConfig) -> Dict[str, Any]:
    """
    Returns a summary of past appointments + medical records for this patient_id.
    """
    patient_id = config["configurable"]["user_id"]
    past_appts = db.get_past_appointments(patient_id)
    med_history = db.get_medical_history(patient_id)

    reply_parts = []
    if past_appts:
        reply_parts.append("Your Past Appointments:")
        for appt in past_appts[:5]:  # show up to 5
            reply_parts.append(
                f"- ID {appt['appointment_id']}: Dr. {appt['doctor_name']} on {appt['appointment_date']} at {appt['start_time']} (Status: {appt['status']})"
            )
    else:
        reply_parts.append("You have no past appointments on record.")

    if med_history:
        reply_parts.append("\nYour Recent Medical Records:")
        for rec in med_history[:5]:
            reply_parts.append(
                f"- {rec['record_date']}: Diagnosis={rec['diagnosis']}, Treatment={rec['treatment']}"
            )
    else:
        reply_parts.append("No medical records found.")

    return {
        "messages": [AIMessage(content="\n".join(reply_parts))],
        "current_node": "patient_records_access"
    }


# ─────── Node: General Response ────────────────────────────────────────────────────
def general_response_node(state: HealthcareState, config: RunnableConfig):
    user_question = state["messages"][-1].content

    # 1) Retrieve hospital manual passages
    retriever = hospital_manual_vectorstore.as_retriever()
    retrieved_docs = retriever.invoke(user_question)
    manual_context = "\n\n".join(doc.page_content for doc in retrieved_docs)

    # 2) Perform live web research via Exa API
    exa_api_key = os.getenv("EXA_API_KEY", "9b08534f-b360-45ba-a024-c47bd9bb3834")
    exa = Exa(api_key=exa_api_key)
    web_research = ""
    try:
        # Customize this prompt template if needed
        research_results = exa.search_and_contents(
            query=f"{user_question} ",
            num_results=4,
            start_published_date="2024-11-01T00:00:00.000Z",
            include_domains=["healthcareweekly.com"],
            summary=True
        )
        web_research = "\n".join(r.summary for r in research_results.results if r.summary)
    except Exception:
        web_research = f"Answer of {user_question}"

    # 3) Build the combined RAG prompt
    prompt = f"""
 You are a friendly and knowledgeable hospital virtual assistant. Use the following excerpt from the hospital’s official manual to answer the patient’s question. If the manual does not cover the topic, direct the user to contact hospital staff or the appropriate department.

---  
Hospital Manual Excerpt:  
{manual_context}

---  
Live Web Research Excerpts:  
{web_research}

---  
Patient’s Question:  
{user_question}

Provide a clear, concise answer in your answers

"""

    # 4) Invoke the LLM with system + human messages
    response = llm.invoke([
        
        HumanMessage(content=prompt)
    ])

    return {
        "messages": [response],
        "current_node": "general_response"
    }


# ─────── Routing Functions ─────────────────────────────────────────────────────────
def route_from_patient_interaction(state: "HealthcareState") -> str:
    intent = state.get("intent", "")
    if intent == "symptom":
        return "symptom_triage"
    elif intent == "booking":
        return "booking_appointment"
    elif intent == "cancellation":
        return "cancelling_appointment"
    elif intent == "rescheduling":
        return "rescheduling_appointment"
    elif intent == "records":
        return "patient_records_access"
    else:
        return "general_response"


def route_from_symptom_triage(state: "HealthcareState") -> str:
    if state.get("emergency_detected", False):
        return "emergency_response"
    else:
        return "non_urgent_symptom_suggestions"


# ─────── HealthcareState Definition ───────────────────────────────────────────────
from langgraph.graph import MessagesState


class HealthcareState(MessagesState):
    """
    Extends MessagesState with fields that nodes read/update:
      - patient_info: dict
      - current_appointment: Optional[dict]
      - current_node: str
      - emergency_detected: bool
      - tool_results: dict
      - intent: Optional[str]
    All fields are added/overwritten by node functions at runtime.
    """
    patient_info: dict
    current_appointment: Optional[dict]
    current_node: str
    emergency_detected: bool
    tool_results: dict
    intent: Optional[str]
