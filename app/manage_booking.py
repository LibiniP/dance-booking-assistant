"""
app/manage_booking.py
-----------------------
Self-service page: shows ONLY the bookings tied to the currently logged-in
student account (via student_id), with edit/cancel options. No manual ID or
email lookup -- ownership is proven by being logged into that account.
"""

import streamlit as st

from app.config import VALID_DANCE_STYLES, VALID_PACKAGES, VALID_SLOTS
from db.database import get_bookings_for_student, update_booking_fields, update_booking_status


def manage_booking_page():
    st.title("🔍 Manage My Booking")

    student_id = st.session_state.get("student_id")
    if not student_id:
        st.warning("Please log in first.")
        return

    bookings = get_bookings_for_student(student_id)
    if not bookings:
        st.info(
            "You haven't made a booking yet. Go to the **Chat** page to book a class — "
            "it'll show up here automatically once confirmed."
        )
        return

    for booking in bookings:
        _render_booking_card(booking)


def _render_booking_card(booking):
    st.divider()
    st.subheader(f"Booking #{booking['id']} — {booking['status'].upper()}")
    st.write(f"**Name:** {booking['name']}")
    st.write(f"**Email:** {booking['email']}")
    st.write(f"**Phone:** {booking['phone']}")
    st.write(f"**Booked on:** {booking['created_at']}")

    if booking["status"] == "cancelled":
        st.info("This booking has been cancelled.")
        return

    with st.form(key=f"edit_form_{booking['id']}"):
        new_package = st.selectbox(
            "Package", VALID_PACKAGES,
            index=VALID_PACKAGES.index(booking["package"]) if booking["package"] in VALID_PACKAGES else 0,
        )
        new_style = st.selectbox(
            "Dance Style", VALID_DANCE_STYLES,
            index=VALID_DANCE_STYLES.index(booking["dance_style"]) if booking["dance_style"] in VALID_DANCE_STYLES else 0,
        )
        new_slot = st.selectbox(
            "Preferred Slot", VALID_SLOTS,
            index=VALID_SLOTS.index(booking["preferred_slot"]) if booking["preferred_slot"] in VALID_SLOTS else 0,
        )

        col_a, col_b = st.columns(2)
        with col_a:
            save_clicked = st.form_submit_button("💾 Save changes", use_container_width=True)
        with col_b:
            cancel_clicked = st.form_submit_button("❌ Cancel booking", use_container_width=True)

    if save_clicked:
        update_booking_fields(booking["id"], package=new_package, dance_style=new_style, preferred_slot=new_slot)
        st.success("Booking updated!")
        st.rerun()

    if cancel_clicked:
        update_booking_status(booking["id"], "cancelled")
        st.success("Booking cancelled.")
        st.rerun()