"""
app/chat_logic.py
------------------
The "brain" of the app: decides whether an incoming message should go to
greeting/small-talk, the RAG tool, or the booking flow. Also manages
short-term memory (assignment requires last 20-25 messages).

Also handles the case where the user asks an unrelated question WHILE a
booking is in progress -- we answer the question via RAG, then remind them
of the pending booking step, instead of losing their progress.
"""

import re

from app.config import MAX_MEMORY_MESSAGES, STUDIO_NAME
from app.tools import rag_tool
from app.booking_flow import handle_booking_turn, pending_prompt_for

BOOKING_KEYWORDS = [
    "book", "booking", "enroll", "enrol", "sign up", "signup",
    "register", "reserve", "i want to join", "i want to book",
]

GREETING_PATTERN = re.compile(
    r"^\s*(hi|hello|hey|hiya|yo|good\s?(morning|afternoon|evening)|"
    r"what'?s up|how are you|thanks|thank you|ok|okay|cool|bye)\s*[!.?]*\s*$",
    re.IGNORECASE,
)

GREETING_REPLY = (
    f"Hi there! 👋 I'm the {STUDIO_NAME} assistant. I can answer questions about our "
    f"dance styles, schedules, and packages, or help you book a class. What would you like to do?"
)

# Words/patterns that signal "this is a question", used both to detect side
# questions asked mid-booking-flow, and to keep simple info queries (like
# "packages" or "styles") from accidentally triggering booking mode.
QUESTION_STARTERS = (
    "who", "what", "when", "where", "why", "how", "is", "are", "can",
    "do", "does", "did", "could", "would", "will", "which",
)
CONFIRMATION_WORDS = {
    "yes", "y", "confirm", "yep", "sure", "correct", "no", "n", "cancel", "nope",
}


def trim_memory(messages: list) -> list:
    """Keep only the last N messages (short-term memory window)."""
    return messages[-MAX_MEMORY_MESSAGES:]


def is_greeting(user_message: str) -> bool:
    return bool(GREETING_PATTERN.match(user_message.strip()))


def is_side_question(user_message: str) -> bool:
    """
    True if this looks like a question rather than a field
    answer/confirmation/booking request.
    """
    stripped = user_message.strip().lower()
    if stripped in CONFIRMATION_WORDS:
        return False
    if stripped.endswith("?"):
        return True
    first_word = stripped.split(" ")[0] if stripped else ""
    return first_word in QUESTION_STARTERS


def detect_intent(llm, user_message: str, booking_active: bool) -> str:
    """
    Returns "greeting", "booking", or "rag".
    If we're already mid-booking-flow, stay in booking mode unless the user
    clearly wants to leave — this prevents the bot from losing progress
    when the user asks a side question.
    """
    if booking_active:
        return "booking"

    if is_greeting(user_message):
        return "greeting"

    # A question ("what packages do you have?", "packages?") should always
    # go to RAG, even if it contains a word like "package" or "join" —
    # only a genuine booking request should trigger the booking flow.
    if is_side_question(user_message):
        return "rag"

    lowered = user_message.lower()
    if any(kw in lowered for kw in BOOKING_KEYWORDS):
        return "booking"

    # Fallback to LLM classification for ambiguous messages
    prompt = f"""Classify the user's message as exactly one word: "booking" or "question".
"booking" = they want to book/enroll/join a class or package.
"question" = they are asking about the studio, styles, pricing, schedule, or anything else.

Message: "{user_message}"

Answer with one word only:"""
    try:
        response = llm.invoke(prompt)
        label = response.content.strip().lower()
        return "booking" if "book" in label else "rag"
    except Exception:
        return "rag"


def route_message(llm, vector_store, booking_state: dict, user_message: str) -> str:
    """
    Main router called from main.py for every user turn.
    Returns the bot's reply text.
    """
    # If a booking is mid-flow and this message looks like an unrelated
    # question (not a field value, not yes/no), answer it via RAG and then
    # remind the user where the booking stands -- don't lose their progress.
    if booking_state["active"] and is_side_question(user_message):
        answer = rag_tool(user_message, vector_store, llm)
        reminder = pending_prompt_for(booking_state)
        return f"{answer}\n\n---\n{reminder}"

    intent = detect_intent(llm, user_message, booking_state["active"])

    if intent == "greeting":
        return GREETING_REPLY
    elif intent == "booking":
        booking_state["active"] = True
        return handle_booking_turn(llm, booking_state, user_message)
    else:
        return rag_tool(user_message, vector_store, llm)