"""
app/admin_dashboard.py
-----------------------
Mandatory Admin Dashboard: view all bookings, filter by name/email/date.
"""

import streamlit as st
import pandas as pd

from db.database import get_all_bookings, update_booking_status


def admin_dashboard_page():
    st.title("📊 Admin Dashboard — All Bookings")

    bookings = get_all_bookings()
    if not bookings:
        st.info("No bookings yet.")
        return

    df = pd.DataFrame(bookings)

    # ---- Filters ----
    col1, col2, col3 = st.columns(3)
    with col1:
        name_filter = st.text_input("Filter by name")
    with col2:
        email_filter = st.text_input("Filter by email")
    with col3:
        date_filter = st.text_input("Filter by date (YYYY-MM-DD)")

    filtered = df.copy()
    if name_filter:
        filtered = filtered[filtered["name"].str.contains(name_filter, case=False, na=False)]
    if email_filter:
        filtered = filtered[filtered["email"].str.contains(email_filter, case=False, na=False)]
    if date_filter:
        filtered = filtered[filtered["created_at"].str.contains(date_filter, na=False)]

    st.dataframe(filtered, use_container_width=True)

    st.divider()
    st.subheader("Manage a booking")
    booking_ids = df["id"].tolist()
    if booking_ids:
        selected_id = st.selectbox("Select booking ID", booking_ids)
        new_status = st.selectbox("Set status", ["confirmed", "cancelled"])
        if st.button("Update status"):
            update_booking_status(selected_id, new_status)
            st.success(f"Booking #{selected_id} updated to '{new_status}'.")
            st.rerun()

    st.divider()
    st.download_button(
        "⬇️ Export all bookings as CSV",
        data=df.to_csv(index=False),
        file_name="bookings_export.csv",
        mime="text/csv",
    )
