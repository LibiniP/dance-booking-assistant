"""
app/main.py
-----------
Streamlit entry point. Handles account-based login (Admin fixed credentials /
Student username+password), navigation, PDF auto-loading for RAG, persisted
chat history, and top-level error handling.

Run with: streamlit run app/main.py
"""

import sys
import os
import glob

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st

from app.config import STUDIO_NAME, MAX_MEMORY_MESSAGES, ADMIN_USERNAME, ADMIN_PASSWORD
from app.rag_pipeline import build_vector_store
from app.chat_logic import route_message, trim_memory
from app.booking_flow import init_booking_state
from app.tools import get_llm
from app.admin_dashboard import admin_dashboard_page
from app.manage_booking import manage_booking_page
from db.database import (
    init_db,
    authenticate_or_register_student,
    save_chat_message,
    get_chat_history,
    delete_chat_history,
)

DEFAULT_PDF_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "docs"))


def _autoload_default_pdfs():
    pdf_paths = glob.glob(os.path.join(DEFAULT_PDF_DIR, "*.pdf"))
    if not pdf_paths:
        return None
    try:
        file_objs = [open(p, "rb") for p in pdf_paths]
        vector_store = build_vector_store(file_objs)
        for f in file_objs:
            f.close()
        return vector_store
    except Exception:
        return None


def init_session_state():
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "vector_store" not in st.session_state:
        st.session_state.vector_store = _autoload_default_pdfs()
    if "booking_state" not in st.session_state:
        st.session_state.booking_state = init_booking_state()
    if "llm" not in st.session_state:
        try:
            st.session_state.llm = get_llm()
            st.session_state.llm_error = None
        except Exception as e:
            st.session_state.llm = None
            st.session_state.llm_error = str(e)
    if "role" not in st.session_state:
        st.session_state.role = None  # "admin" or "student"
    if "student_id" not in st.session_state:
        st.session_state.student_id = None


def role_gate():
    """
    Shown before anything else.
    Student: username + password. First login with a new username creates
    the account; returning users must match their saved password. This lets
    two people with the same display name have separate, private accounts.
    Admin: fixed credentials from config (.streamlit/secrets.toml).
    """
    st.title(f"💃 {STUDIO_NAME}")
    st.subheader("Who's using this?")

    choice = st.radio("I am a:", ["Student / Participant", "Admin"], horizontal=True)

    if choice == "Student / Participant":
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        display_name = st.text_input("Your name (only needed the first time you use this username)")

        if st.button("Continue"):
            if not username.strip() or not password:
                st.warning("Please enter both a username and password.")
                return

            result = authenticate_or_register_student(username.strip(), password, display_name)
            if not result["success"]:
                st.error(result["error"])
                return

            st.session_state.role = "student"
            st.session_state.student_id = result["student_id"]
            st.session_state.display_name = result["display_name"]
            # Load this account's persisted chat history so it carries over across logins
            st.session_state.messages = get_chat_history(result["student_id"])
            st.rerun()
    else:
        username = st.text_input("Admin username")
        password = st.text_input("Admin password", type="password")
        if st.button("Log in"):
            if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
                st.session_state.role = "admin"
                st.rerun()
            else:
                st.error("Incorrect username or password.")


def instructions_page():
    st.title(f"💃 {STUDIO_NAME} — AI Booking Assistant")
    st.markdown(f"""
    ### Setup (for developers)
    Add these to `.streamlit/secrets.toml`:
```toml
    GROQ_API_KEY = "your-groq-key"
    GROQ_MODEL = "openai/gpt-oss-120b"
    SMTP_EMAIL = "youremail@gmail.com"
    SMTP_APP_PASSWORD = "your-16-char-app-password"
    ADMIN_USERNAME = "admin"
    ADMIN_PASSWORD = "choose-a-real-password"
```
    Get a free Groq key at https://console.groq.com/keys
    """)


def chat_page():
    st.title(f"💃 {STUDIO_NAME} — Chat")

    if st.session_state.llm_error:
        st.error(f"⚠️ LLM not configured: {st.session_state.llm_error}")
        return

    with st.sidebar:
        st.subheader("📄 Studio Knowledge Base")
        if st.session_state.vector_store is not None:
            st.success("✅ Studio info is loaded and ready.")
        else:
            st.warning("No studio info loaded yet.")

        if st.session_state.role == "admin":
            uploaded_files = st.file_uploader(
                "Upload additional/updated PDF(s)", type=["pdf"], accept_multiple_files=True
            )
            if uploaded_files and st.button("Process PDFs"):
                with st.spinner("Reading and indexing PDF(s)..."):
                    try:
                        st.session_state.vector_store = build_vector_store(uploaded_files)
                        st.success(f"Indexed {len(uploaded_files)} PDF(s) successfully!")
                    except Exception as e:
                        st.error(f"Failed to process PDF(s): {e}")

        st.divider()
        if st.button("🗑️ Clear Chat History", use_container_width=True):
            st.session_state.messages = []
            st.session_state.booking_state = init_booking_state()
            if st.session_state.role == "student" and st.session_state.student_id:
                delete_chat_history(st.session_state.student_id)
            st.rerun()

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Ask a question or say 'I want to book a class'..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        if st.session_state.role == "student" and st.session_state.student_id:
            save_chat_message(st.session_state.student_id, "user", prompt)

        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    response = route_message(
                        st.session_state.llm,
                        st.session_state.vector_store,
                        st.session_state.booking_state,
                        prompt,
                    )
                except Exception as e:
                    response = f"⚠️ Something went wrong: {e}. Please try again."
                st.markdown(response)

        st.session_state.messages.append({"role": "assistant", "content": response})
        if st.session_state.role == "student" and st.session_state.student_id:
            save_chat_message(st.session_state.student_id, "assistant", response)

        st.session_state.messages = trim_memory(st.session_state.messages)


def main():
    st.set_page_config(
        page_title=f"{STUDIO_NAME} — AI Booking Assistant",
        page_icon="💃",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    init_db()
    init_session_state()

    if st.session_state.role is None:
        role_gate()
        return

    with st.sidebar:
        st.title("Navigation")
        if st.session_state.role == "admin":
            page_options = ["Chat", "Admin Dashboard", "Instructions"]
        else:
            page_options = ["Chat", "Manage Booking"]
        page = st.radio("Go to:", page_options, index=0)

        st.divider()
        role_label = "Admin" if st.session_state.role == "admin" else st.session_state.get("display_name", "Student")
        st.caption(f"Logged in as: **{role_label}** ({st.session_state.role})")
        if st.button("Switch user"):
            st.session_state.role = None
            st.session_state.student_id = None
            st.session_state.messages = []
            st.session_state.booking_state = init_booking_state()
            st.rerun()

    if page == "Chat":
        chat_page()
    elif page == "Manage Booking":
        manage_booking_page()
    elif page == "Instructions":
        instructions_page()
    elif page == "Admin Dashboard":
        admin_dashboard_page()


if __name__ == "__main__":
    main()