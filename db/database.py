"""
db/database.py
--------------
SQLite client. Handles table creation and CRUD operations for
customers, bookings, student accounts, and persisted chat history.
"""

import sqlite3
import hashlib
from contextlib import contextmanager
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.config import DB_PATH


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def init_db():
    """Create tables if they don't already exist. Call this once at app startup."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                phone TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                package TEXT NOT NULL,
                dance_style TEXT NOT NULL,
                preferred_slot TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'confirmed',
                created_at TEXT NOT NULL,
                FOREIGN KEY (customer_id) REFERENCES customers (customer_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS students (
                student_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                display_name TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (student_id) REFERENCES students (student_id)
            )
        """)

        # Migration: add student_id to bookings if this DB predates this feature
        cols = [row[1] for row in conn.execute("PRAGMA table_info(bookings)").fetchall()]
        if "student_id" not in cols:
            conn.execute("ALTER TABLE bookings ADD COLUMN student_id INTEGER")


# ---------------------------------------------------------------------------
# Student accounts
# ---------------------------------------------------------------------------
def authenticate_or_register_student(username: str, password: str, display_name: str = None) -> dict:
    """
    If the username already exists: verifies the password, returns the account
    on success or an error if the password is wrong.
    If the username doesn't exist yet: creates a new account with the given
    password and display name (registration-on-first-login).
    """
    pwd_hash = _hash_password(password)
    with get_connection() as conn:
        row = conn.execute(
            "SELECT student_id, username, password_hash, display_name FROM students WHERE username = ?",
            (username,),
        ).fetchone()

        if row:
            if row["password_hash"] != pwd_hash:
                return {"success": False, "error": "Incorrect password for this username."}
            return {
                "success": True,
                "student_id": row["student_id"],
                "username": row["username"],
                "display_name": row["display_name"],
            }

        final_display_name = display_name.strip() if display_name and display_name.strip() else username
        cur = conn.execute(
            "INSERT INTO students (username, password_hash, display_name) VALUES (?, ?, ?)",
            (username, pwd_hash, final_display_name),
        )
        return {
            "success": True,
            "student_id": cur.lastrowid,
            "username": username,
            "display_name": final_display_name,
        }


# ---------------------------------------------------------------------------
# Customers / Bookings
# ---------------------------------------------------------------------------
def find_or_create_customer(name: str, email: str, phone: str) -> int:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT customer_id FROM customers WHERE email = ?", (email,)
        ).fetchone()
        if row:
            return row["customer_id"]
        cur = conn.execute(
            "INSERT INTO customers (name, email, phone) VALUES (?, ?, ?)",
            (name, email, phone),
        )
        return cur.lastrowid


def create_booking(customer_id: int, package: str, dance_style: str, preferred_slot: str, student_id: int = None) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO bookings (customer_id, package, dance_style, preferred_slot, status, created_at, student_id)
               VALUES (?, ?, ?, ?, 'confirmed', ?, ?)""",
            (customer_id, package, dance_style, preferred_slot, datetime.utcnow().isoformat(), student_id),
        )
        return cur.lastrowid


def get_all_bookings():
    """Used by the Admin Dashboard — every booking, regardless of student account."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT b.id, c.name, c.email, c.phone, b.package, b.dance_style,
                   b.preferred_slot, b.status, b.created_at
            FROM bookings b
            JOIN customers c ON b.customer_id = c.customer_id
            ORDER BY b.created_at DESC
        """).fetchall()
        return [dict(r) for r in rows]


def get_bookings_for_student(student_id: int):
    """Used by Manage Booking — ONLY bookings tied to this logged-in account."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT b.id, c.name, c.email, c.phone, b.package, b.dance_style,
                   b.preferred_slot, b.status, b.created_at
            FROM bookings b
            JOIN customers c ON b.customer_id = c.customer_id
            WHERE b.student_id = ?
            ORDER BY b.created_at DESC
        """, (student_id,)).fetchall()
        return [dict(r) for r in rows]


def update_booking_status(booking_id: int, status: str):
    with get_connection() as conn:
        conn.execute("UPDATE bookings SET status = ? WHERE id = ?", (status, booking_id))


def update_booking_fields(booking_id: int, package: str = None, dance_style: str = None, preferred_slot: str = None):
    updates = []
    params = []
    if package is not None:
        updates.append("package = ?")
        params.append(package)
    if dance_style is not None:
        updates.append("dance_style = ?")
        params.append(dance_style)
    if preferred_slot is not None:
        updates.append("preferred_slot = ?")
        params.append(preferred_slot)

    if not updates:
        return

    params.append(booking_id)
    with get_connection() as conn:
        conn.execute(f"UPDATE bookings SET {', '.join(updates)} WHERE id = ?", params)


# ---------------------------------------------------------------------------
# Persisted chat history (per student account)
# ---------------------------------------------------------------------------
def save_chat_message(student_id: int, role: str, content: str):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO chat_messages (student_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (student_id, role, content, datetime.utcnow().isoformat()),
        )


def get_chat_history(student_id: int, limit: int = 25):
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT role, content FROM chat_messages
            WHERE student_id = ?
            ORDER BY id DESC LIMIT ?
        """, (student_id, limit)).fetchall()
        return [dict(r) for r in reversed(rows)]


def delete_chat_history(student_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM chat_messages WHERE student_id = ?", (student_id,))