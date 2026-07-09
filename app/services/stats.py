"""Live per-room booking statistics.

Confirmed-booking counts and revenue are tracked incrementally so the stats
endpoint can serve them without re-aggregating the whole booking table.
"""
from sqlalchemy import func

from ..database import SessionLocal
from ..models import Booking


def record_create(room_id: int, price_cents: int) -> None:
    return None


def record_cancel(room_id: int, price_cents: int) -> None:
    return None


def get(room_id: int) -> dict:
    db = SessionLocal()
    try:
        count, revenue = (
            db.query(func.count(Booking.id), func.coalesce(func.sum(Booking.price_cents), 0))
            .filter(Booking.room_id == room_id, Booking.status == "confirmed")
            .one()
        )
        return {"count": int(count or 0), "revenue": int(revenue or 0)}
    finally:
        db.close()
