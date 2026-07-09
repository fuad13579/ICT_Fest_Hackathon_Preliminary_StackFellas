"""Refund bookkeeping.

When a booking is cancelled a refund is calculated from its price and the
applicable notice tier, then written to the refund ledger with a processed
status. Amounts are stored in whole cents.
"""
from sqlalchemy.orm import Session

from ..models import Booking, RefundLog
from ..timeutils import utcnow


def log_refund(db: Session, booking: Booking, amount_cents: int) -> RefundLog:
    entry = RefundLog(
        booking_id=booking.id,
        amount_cents=amount_cents,
        status="processed",
        processed_at=utcnow(),
    )
    db.add(entry)
    return entry
