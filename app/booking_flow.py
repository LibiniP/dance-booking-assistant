"""
app/booking_flow.py
--------------------
Implements the multi-turn booking flow (assignment section 2.2 / 5):
  1. Extract known details from the user's message
  2. Validate against known/valid values (dance style, package, slot)
  3. Ask only for missing/invalid fields
  4. Once all fields are valid -> summarize -> ask explicit confirmation
  5. On "yes" -> save to DB (booking_persistence_tool) + send email (email_tool)
  6. On "no" -> let user correct a field

Also exposes `pending_prompt_for()` so chat_logic can re-show "what's next"
after answering an unrelated question mid-booking, without losing progress.
"""

import json
import re

import streamlit as st

from app.config import REQUIRED_BOOKING_FIELDS, STUDIO_NAME, VALID_DANCE_STYLES, VALID_PACKAGES, VALID_SLOTS
from app.tools import booking_persistence_tool, email_tool, build_confirmation_email_body

FIELD_QUESTIONS = {
    "name": "What's your name?",
    "email": "What's your email address?",
    "phone": "What's your phone number?",
    "package": f"Which package would you like? Options: {', '.join(VALID_PACKAGES)}",
    "dance_style": f"Which dance style are you interested in? Options: {', '.join(VALID_DANCE_STYLES)}",
    "preferred_slot": f"Which time slot works for you? Options: {', '.join(VALID_SLOTS)}",
}

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_REGEX = re.compile(r"^\+?\d[\d\s-]{7,14}\d$")


def init_booking_state():
    return {
        "active": False,
        "fields": {k: None for k in REQUIRED_BOOKING_FIELDS},
        "awaiting_confirmation": False,
    }


def _closest_match(value: str, options: list):
    """Simple case-insensitive substring/keyword match against a canonical list."""
    value_l = value.lower().replace("-", " ").replace("+", " plus ")
    for opt in options:
        opt_l = opt.lower().replace("-", " ").replace("+", " plus ")
        if value_l in opt_l or opt_l in value_l:
            return opt
    for opt in options:
        opt_tokens = set(re.findall(r"[a-z0-9]+", opt.lower()))
        value_tokens = set(re.findall(r"[a-z0-9]+", value.lower()))
        if opt_tokens and len(opt_tokens & value_tokens) >= max(1, len(opt_tokens) - 1):
            return opt
    return None


def validate_field(field: str, value: str):
    """Returns (is_valid, normalized_value_or_error_message)."""
    value = value.strip()
    if not value:
        return False, "That field can't be empty — could you provide it again?"

    if field == "email" and not EMAIL_REGEX.match(value):
        return False, "That doesn't look like a valid email. Could you re-enter it? (e.g. name@example.com)"

    if field == "phone" and not PHONE_REGEX.match(value):
        return False, "That doesn't look like a valid phone number. Please enter digits only (e.g. 9876543210)."

    if field == "dance_style":
        match = _closest_match(value, VALID_DANCE_STYLES)
        if not match:
            return False, f"We don't offer '{value}'. Available styles: {', '.join(VALID_DANCE_STYLES)}."
        return True, match

    if field == "package":
        match = _closest_match(value, VALID_PACKAGES)
        if not match:
            return False, f"'{value}' isn't a package we offer. Available packages: {', '.join(VALID_PACKAGES)}."
        return True, match

    if field == "preferred_slot":
        match = _closest_match(value, VALID_SLOTS)
        if not match:
            return False, f"'{value}' isn't a valid slot. Available slots: {', '.join(VALID_SLOTS)}."
        return True, match

    return True, value


def extract_fields_with_llm(llm, user_message: str, missing_fields: list) -> dict:
    field_list = ", ".join(missing_fields)
    prompt = f"""Extract any of these fields if present in the user's message: {field_list}.
Respond ONLY with a valid JSON object with those exact keys. Use null for
any field not mentioned. Do not include any other text, explanation, or markdown.

User message: "{user_message}"

JSON:"""
    try:
        response = llm.invoke(prompt)
        text = response.content.strip()
        text = re.sub(r"^```(json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
        extracted = json.loads(text)
        return {k: v for k, v in extracted.items() if v}
    except Exception:
        return {}


def get_next_missing_field(fields: dict):
    for f in REQUIRED_BOOKING_FIELDS:
        if not fields.get(f):
            return f
    return None


def build_summary(fields: dict) -> str:
    return (
        f"Here's what I have:\n\n"
        f"- **Name:** {fields['name']}\n"
        f"- **Email:** {fields['email']}\n"
        f"- **Phone:** {fields['phone']}\n"
        f"- **Package:** {fields['package']}\n"
        f"- **Dance Style:** {fields['dance_style']}\n"
        f"- **Preferred Slot:** {fields['preferred_slot']}\n\n"
        f"Shall I confirm this booking? (yes/no)"
    )


def pending_prompt_for(booking_state: dict) -> str:
    """Returns whatever the bot should ask next, without advancing state. Used to
    remind the user of the booking-in-progress after answering a side question."""
    fields = booking_state["fields"]
    if booking_state["awaiting_confirmation"]:
        return build_summary(fields)
    next_missing = get_next_missing_field(fields)
    if next_missing:
        return FIELD_QUESTIONS[next_missing]
    return build_summary(fields)


def finalize_booking(fields: dict) -> str:
    student_id = st.session_state.get("student_id")
    result = booking_persistence_tool(fields, student_id=student_id)
    if not result["success"]:
        return f"⚠️ I couldn't save your booking: {result['error']}. Could we try again?"

    booking_id = result["booking_id"]
    email_body = build_confirmation_email_body(booking_id, fields)
    email_result = email_tool(
        to_email=fields["email"],
        subject=f"Your {STUDIO_NAME} Booking Confirmation — #{booking_id}",
        body=email_body,
    )

    base_msg = (
        f"✅ You're all set! Your booking ID is **#{booking_id}**. "
        f"You can view, edit, or cancel it anytime from the **Manage Booking** page."
    )
    if email_result["success"]:
        base_msg += " A confirmation email has also been sent to you."
    else:
        base_msg += f" (Note: the confirmation email could not be sent — {email_result['error']}. Your booking is still saved.)"
    return base_msg


def handle_booking_turn(llm, booking_state: dict, user_message: str) -> str:
    fields = booking_state["fields"]

    if booking_state["awaiting_confirmation"]:
        answer = user_message.strip().lower()
        if answer in ("yes", "y", "confirm", "yep", "sure", "correct"):
            reply = finalize_booking(fields)
            booking_state["active"] = False
            booking_state["awaiting_confirmation"] = False
            booking_state["fields"] = {k: None for k in REQUIRED_BOOKING_FIELDS}
            return reply
        elif answer in ("no", "n", "cancel", "nope"):
            booking_state["awaiting_confirmation"] = False
            return "No problem — which detail would you like to change?"
        else:
            extracted = extract_fields_with_llm(llm, user_message, REQUIRED_BOOKING_FIELDS)
            errors = []
            for k, v in extracted.items():
                if k in fields:
                    valid, result = validate_field(k, str(v))
                    if valid:
                        fields[k] = result
                    else:
                        errors.append(result)
            if errors:
                return "\n".join(errors) + "\n\n" + build_summary(fields)
            return build_summary(fields)

    missing_fields = [f for f in REQUIRED_BOOKING_FIELDS if not fields.get(f)]
    extracted = extract_fields_with_llm(llm, user_message, missing_fields)

    errors = []
    for field, value in extracted.items():
        if field in fields and value:
            valid, result = validate_field(field, str(value))
            if valid:
                fields[field] = result
            else:
                errors.append(result)

    if errors:
        return "\n".join(errors)

    next_missing = get_next_missing_field(fields)
    if next_missing:
        return FIELD_QUESTIONS[next_missing]

    booking_state["awaiting_confirmation"] = True
    return build_summary(fields)