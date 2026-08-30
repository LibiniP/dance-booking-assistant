"""
db/models.py
------------
Simple dataclasses representing the DB schema (mirrors the assignment's
required schema: customers + bookings).
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Customer:
    customer_id: Optional[int]
    name: str
    email: str
    phone: str


@dataclass
class Booking:
    id: Optional[int]
    customer_id: int
    package: str          # e.g. "Dance+ 3 Months - 48 sessions"
    dance_style: str      # e.g. "Hiphop"
    preferred_slot: str   # e.g. "Sat/Sun 5PM-6PM"
    status: str            # "confirmed" / "cancelled"
    created_at: Optional[str] = None
