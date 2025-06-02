"""
agent.py

Assembles the LangGraph workflow using all nodes from agent_nodes.py.
Exports `healthcare_assistant` (the compiled graph) and `db` so that UI can import them.
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore
from langchain_core.runnables import RunnableConfig

from agent_nodes import (
    HealthcareState,
    patient_interaction_node,
    symptom_triage_node,
    emergency_response_node,
    non_urgent_symptom_suggestions_node,
    booking_appointment_node,
    cancelling_appointment_node,
    rescheduling_appointment_node,
    patient_records_access_node,
    general_response_node,
    route_from_patient_interaction,
    route_from_symptom_triage,
    db,  # DatabaseManager instance
)

# ─────── Build the StateGraph ─────────────────────────────────────────────────────
workflow = StateGraph(HealthcareState)

# 1) Add each node function
workflow.add_node("patient_interaction", patient_interaction_node)
workflow.add_node("symptom_triage", symptom_triage_node)
workflow.add_node("emergency_response", emergency_response_node)
workflow.add_node("booking_appointment", booking_appointment_node)
workflow.add_node("cancelling_appointment", cancelling_appointment_node)
workflow.add_node("rescheduling_appointment", rescheduling_appointment_node)
workflow.add_node("patient_records_access", patient_records_access_node)
workflow.add_node("general_response", general_response_node)
workflow.add_node("non_urgent_symptom_suggestions", non_urgent_symptom_suggestions_node)

# 2) Define the entry point
workflow.set_entry_point("patient_interaction")

# 3) Add conditional edges from patient_interaction
workflow.add_conditional_edges(
    "patient_interaction",
    route_from_patient_interaction,
    {
        "symptom_triage": "symptom_triage",
        "booking_appointment": "booking_appointment",
        "cancelling_appointment": "cancelling_appointment",
        "rescheduling_appointment": "rescheduling_appointment",
        "patient_records_access": "patient_records_access",
        "general_response": "general_response"
    }
)

# 4) Add conditional edges from symptom_triage
workflow.add_conditional_edges(
    "symptom_triage",
    route_from_symptom_triage,
    {
        "emergency_response": "emergency_response",
        "non_urgent_symptom_suggestions": "non_urgent_symptom_suggestions"
    }
)

# 5) All terminal nodes point to END
workflow.add_edge("booking_appointment", END)
workflow.add_edge("cancelling_appointment", END)
workflow.add_edge("rescheduling_appointment", END)
workflow.add_edge("patient_records_access", END)
workflow.add_edge("general_response", END)
workflow.add_edge("emergency_response", END)
workflow.add_edge("non_urgent_symptom_suggestions", END)

# 6) Compile the graph
enhanced_memory = InMemoryStore()
checkpointer = MemorySaver()

healthcare_assistant = workflow.compile(
    checkpointer=checkpointer,
    store=enhanced_memory
)

# 7) Export db (DatabaseManager instance) as well
__all__ = [
    "healthcare_assistant",
    "db",
    "RunnableConfig"
]
