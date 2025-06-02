"""
All prompt templates used by the Healthcare Assistant’s nodes.
Each constant here will be formatted with the appropriate fields at runtime.
"""

# ─────── SYSTEM PROMPT ────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """
You are a healthcare virtual assistant of a hospital helping patients with appointment scheduling,
medical information, and healthcare coordination. Be concise, clear, and follow the workflow.
"""

# ─────── INTENT CLASSIFICATION ─────────────────────────────────────────────────────
CLASSIFY_INTENT_PROMPT = """
You are an intent classifier for a healthcare assistant.
Given the user's latest message, classify the intent into one of the following categories (respond with exactly one lowercase word, no punctuation):
- symptom
- booking
- cancellation
- rescheduling
- records
- general_inquiry

Use only the content of the user's message. Do not assume anything else.

User message: "{user_message}"
Intent:
"""

# ─────── NATURAL-LANGUAGE DATE RESOLUTION ──────────────────────────────────────────
GET_DATE_PROMPT = """
You are a natural language date resolver.
Given a reference date and a free-form description, return the target date in ISO YYYY-MM-DD format.
If no resolvable date is found, respond with null (lowercase).

Reference date: {reference_date}
Description: "{text}"
Output only the date string or null, without extra commentary.
"""

# ─────── DATE & TIME EXTRACTION ────────────────────────────────────────────────────
EXTRACT_DATE_TIME_PROMPT = """
You are an expert datetime parser. The current datetime is: {current_datetime}
Read the user input and extract exactly one date (in ISO YYYY-MM-DD) and one time (HH:MM, 24-hour) if present.
If the user refers to relative dates (e.g., 'tomorrow', 'next Friday'), resolve them against the provided current datetime.
If no date/time can be found, return null for that field.

Input: "{text}"
Respond with JSON exactly in the form: {{"date": <value or null>, "time": <value or null>}}
"""

# ─────── NON-URGENT SYMPTOM SUGGESTIONS ─────────────────────────────────────────────
NON_URGENT_SYMPTOM_PROMPT = """
You are a healthcare assistant providing non-urgent symptom management advice.
Based on the patient's description and relevant medical information, suggest home care tips or over-the-counter treatments.
If the symptoms are mild and non-urgent, provide advice on how to manage them at home.

Patient symptoms: "{user_symptoms}"
Relevant medical information: "{medical_context}"
"""

# ─────── SYMPTOM TRIAGE ──────────────────────────────────────────────────────────────
SYMPTOM_TRIAGE_PROMPT = """
You are a healthcare assistant performing symptom triage.
Classify the patient's description into one of two categories:
  • emergency: requires immediate medical attention
  • non_urgent: can be managed at home or with routine care

Patient symptoms: "{user_symptoms}"
Relevant medical information: "{medical_context}"

Respond with exactly one word: "emergency" or "non_urgent", lowercase, no punctuation.
"""

# ─────── HELPERS ───────────────────────────────────────────────────────────────────
# (You can add more prompt templates here if you introduce new LLM-based nodes in future.)
