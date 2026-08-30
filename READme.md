# Dance Company — AI Booking Assistant

An AI-driven chat assistant for a dance studio that:
- Answers questions about dance styles, schedules, and packages using RAG over the studio's PDF
- Detects booking intent and collects details via multi-turn conversation, validating each value against the studio's real offerings
- Confirms details before saving, and sends an email confirmation after booking
- Supports two account types: **Student/Participant** (book, chat, manage own bookings) and **Admin** (view/manage all bookings, update the knowledge base)
- Keeps booking progress intact even if the user asks an unrelated question mid-flow

## Tech Stack (all free tiers)
- **LLM:** Groq (`openai/gpt-oss-120b`) — free API, fast inference
- **Embeddings:** `sentence-transformers/all-MiniLM-L6-v2` — runs locally, zero API cost
- **Vector store:** FAISS — local, free
- **Database:** SQLite (students, customers, bookings, chat history)
- **Email:** Gmail SMTP (App Password)
- **Frontend:** Streamlit, with a custom dark neon theme

## Project Structure
```
project_root/
├── app/
│   ├── main.py              # Streamlit entry point, login/role gate, custom theme
│   ├── chat_logic.py         # Intent detection + memory + mid-booking question handling
│   ├── booking_flow.py       # Slot filling, field validation, confirmation
│   ├── rag_pipeline.py       # PDF ingestion + embeddings + FAISS
│   ├── tools.py              # RAG / booking persistence / email tools
│   ├── admin_dashboard.py    # Admin-only bookings view/filter/export
│   ├── manage_booking.py     # Student self-service booking view/edit/cancel
│   └── config.py             # Central config (env vars / secrets)
├── db/
│   ├── database.py           # SQLite client: students, customers, bookings, chat history
│   └── models.py
├── docs/
│   └── *.pdf                 # Studio knowledge-base PDF(s), auto-loaded at startup
├── requirements.txt
├── README.md
├── .gitignore
└── .streamlit/
    ├── config.toml            # Dark neon theme (committed — no secrets)
    └── secrets.toml.example   # Template only — copy to secrets.toml locally
```

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Get a free Groq API key:** https://console.groq.com/keys

3. **Get a Gmail App Password** (for sending confirmation emails):
   - Enable 2-Step Verification on your Google account
   - Generate a 16-character app password at https://myaccount.google.com/apppasswords

4. **Create `.streamlit/secrets.toml`** (copy from `secrets.toml.example` and fill in real values):
   ```toml
   GROQ_API_KEY = "your-groq-api-key"
   GROQ_MODEL = "openai/gpt-oss-120b"
   SMTP_EMAIL = "youraddress@gmail.com"
   SMTP_APP_PASSWORD = "your-16-char-app-password"
   ADMIN_USERNAME = "admin"
   ADMIN_PASSWORD = "choose-a-real-password"
   STUDIO_NAME = "Dance Company"
   ```
   **Never commit this file** — it's already in `.gitignore`.

5. **Run locally:**
   ```bash
   streamlit run app/main.py
   ```

## Deployment (Streamlit Cloud)

1. Push this repo to GitHub (confirm `.streamlit/secrets.toml` and `*.db` are NOT committed — check `.gitignore`)
2. Go to https://share.streamlit.io → **New app** → connect your GitHub repo
3. Set the main file path to `app/main.py`
4. In the app's **Settings → Secrets**, paste the same key-value pairs as your local `secrets.toml`
5. Deploy — you'll get a public URL
6. Test end-to-end on the live URL: log in as a student, ask a question, complete a booking, confirm the email arrives, then log in as admin and verify the booking appears on the dashboard

## Usage

**As a Student:**
1. Choose "Student / Participant" on the login screen, enter a username + password (first login creates the account)
2. Ask questions on the **Chat** page (e.g. "what packages do you have?") or say "I want to book a class"
3. Check the **Manage Booking** page to view, edit, or cancel your own bookings

**As Admin:**
1. Choose "Admin" on the login screen, enter the fixed credentials from `secrets.toml`
2. Use the **Admin Dashboard** to view all bookings, filter by name/email/date, update status, or export CSV
3. Upload an updated studio PDF from the Chat page sidebar if packages/schedules change

## Known Limitations / Future Improvements
- SQLite resets on Streamlit Cloud restarts unless persisted externally (Supabase would fix this)
- No OCR — the source PDF must have a real text layer (an image-only PDF will fail to index)
- Booking doesn't validate that a requested dance style is actually offered in the requested time slot
- No STT/TTS (bonus feature, not implemented)
- Passwords are hashed with SHA-256; a production version should use bcrypt/argon2