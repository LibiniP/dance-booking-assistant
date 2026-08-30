"""
app/tools.py
------------
Wraps the core actions as discrete "tools", per the assignment's requirement
(2.5 Tool Calling): RAG Tool, Booking Persistence Tool, Email Tool.
Also provides the shared Groq LLM client used across the app.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from langchain_groq import ChatGroq

from app.config import (
    GROQ_API_KEY, GROQ_MODEL,
    SMTP_HOST, SMTP_PORT, SMTP_EMAIL, SMTP_APP_PASSWORD, STUDIO_NAME,
)
from app.rag_pipeline import retrieve_relevant_chunks
from db.database import find_or_create_customer, create_booking


def get_llm():
    """Returns a configured Groq chat model. Raises a clear error if the key is missing."""
    if not GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Add it to .streamlit/secrets.toml or as an env var."
        )
    return ChatGroq(api_key=GROQ_API_KEY, model=GROQ_MODEL, temperature=0.3)


# ---------------------------------------------------------------------------
# TOOL 1: RAG TOOL
# Input: query (str) -> Output: retrieved answer (str)
# ---------------------------------------------------------------------------
def rag_tool(query: str, vector_store, llm) -> str:
    chunks = retrieve_relevant_chunks(vector_store, query, k=4)
    if not chunks:
        return ("I don't have that information in the uploaded documents yet. "
                "Please make sure a PDF has been uploaded, or ask something else.")

    context = "\n\n---\n\n".join(chunks)
    prompt = f"""You are a helpful assistant for {STUDIO_NAME}, a dance studio.
Answer the user's question using ONLY the context below. If the answer isn't
in the context, say you don't have that information — do not make anything up.
When the answer involves multiple packages, prices, or session counts, format
it as a markdown table for readability.

Context:
{context}

Question: {query}

Answer clearly and concisely:"""

    response = llm.invoke(prompt)
    return response.content


# ---------------------------------------------------------------------------
# TOOL 2: BOOKING PERSISTENCE TOOL
# Input: structured booking payload -> Output: success + booking ID
# ---------------------------------------------------------------------------
def booking_persistence_tool(booking_data: dict, student_id: int = None) -> dict:
    """
    booking_data must contain: name, email, phone, package, dance_style, preferred_slot
    student_id ties this booking to a logged-in student account (so it shows up
    in their Manage Booking page). Pass None if not tied to an account.
    Returns: {"success": bool, "booking_id": int|None, "error": str|None}
    """
    required = ["name", "email", "phone", "package", "dance_style", "preferred_slot"]
    missing = [f for f in required if not booking_data.get(f)]
    if missing:
        return {"success": False, "booking_id": None, "error": f"Missing fields: {', '.join(missing)}"}

    try:
        customer_id = find_or_create_customer(
            booking_data["name"], booking_data["email"], booking_data["phone"]
        )
        booking_id = create_booking(
            customer_id,
            booking_data["package"],
            booking_data["dance_style"],
            booking_data["preferred_slot"],
            student_id=student_id,
        )
        return {"success": True, "booking_id": booking_id, "error": None}
    except Exception as e:
        return {"success": False, "booking_id": None, "error": str(e)}


# ---------------------------------------------------------------------------
# TOOL 3: EMAIL TOOL
# Input: to_email/subject/body -> Output: success/failure
# ---------------------------------------------------------------------------
def email_tool(to_email: str, subject: str, body: str) -> dict:
    """Sends a confirmation email via Gmail SMTP. Returns {"success": bool, "error": str|None}."""
    if not SMTP_EMAIL or not SMTP_APP_PASSWORD:
        return {"success": False, "error": "Email credentials not configured (SMTP_EMAIL / SMTP_APP_PASSWORD)."}

    try:
        msg = MIMEMultipart()
        msg["From"] = SMTP_EMAIL
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_EMAIL, SMTP_APP_PASSWORD)
            server.sendmail(SMTP_EMAIL, to_email, msg.as_string())

        return {"success": True, "error": None}
    except Exception as e:
        return {"success": False, "error": str(e)}


def build_confirmation_email_body(booking_id: int, booking_data: dict) -> str:
    return f"""Hi {booking_data['name']},

Your booking with {STUDIO_NAME} is confirmed! 🎉

Booking ID: {booking_id}
Package: {booking_data['package']}
Dance Style: {booking_data['dance_style']}
Preferred Slot: {booking_data['preferred_slot']}

Classes will be confirmed in the group based on mentor & studio availability.

See you on the dance floor!
{STUDIO_NAME}
"""