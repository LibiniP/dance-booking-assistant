"""
config.py
---------
Centralizes all configuration: API keys, model names, DB path, email settings.
Values are read from Streamlit secrets (when deployed) or environment variables
(when running locally). NEVER hardcode real keys here.
"""

import os

try:
    import streamlit as st
    _SECRETS_AVAILABLE = True
except Exception:
    _SECRETS_AVAILABLE = False


def _get(key: str, default: str = "") -> str:
    """Fetch a config value: Streamlit secrets first, then env vars, then default."""
    if _SECRETS_AVAILABLE:
        try:
            if key in st.secrets:
                return st.secrets[key]
        except Exception:
            pass
    return os.getenv(key, default)


# ---- LLM (Groq) ----
GROQ_API_KEY = _get("GROQ_API_KEY", "")
GROQ_MODEL = _get("GROQ_MODEL", "openai/gpt-oss-120b")

# ---- Embeddings (local, free — no API key needed) ----
EMBEDDING_MODEL_NAME = _get("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")

# ---- Database ----
DB_PATH = _get("DB_PATH", "dance_studio.db")

# ---- Email (SMTP via Gmail App Password) ----
SMTP_HOST = _get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(_get("SMTP_PORT", "587"))
SMTP_EMAIL = _get("SMTP_EMAIL", "")          # your Gmail address
SMTP_APP_PASSWORD = _get("SMTP_APP_PASSWORD", "")  # 16-char Gmail app password
STUDIO_NAME = _get("STUDIO_NAME", "Dance Company") #Studio Name

# ---- Chat behavior ----
MAX_MEMORY_MESSAGES = 50  # short-term memory window (assignment requires 20-25)

# ---- Booking required fields ----
REQUIRED_BOOKING_FIELDS = ["name", "email", "phone", "package", "dance_style", "preferred_slot"]

# ---- Admin access ----
ADMIN_USERNAME = _get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = _get("ADMIN_PASSWORD", "admin123")  # CHANGE THIS in secrets.toml for real use

# ---- Valid values (from studio's official schedule/packages) ----
VALID_DANCE_STYLES = ["Bollywood", "Hiphop", "Bhangra", "Semi-Classical", "Contemporary"]
VALID_SLOTS = ["Sat/Sun 11AM-12PM", "Sat/Sun 5PM-6PM", "Mon-Fri 8PM-9PM"]
VALID_PACKAGES = [
    "Drop-in",
    "Premium - 2 Months", "Premium - 3 Months", "Premium - 6 Months", "Premium - 12 Months",
    "Dance+ - 1 Month", "Dance+ - 3 Months", "Dance+ - 6 Months", "Dance+ - 12 Months",
]
