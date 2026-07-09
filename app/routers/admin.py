"""Administrative reporting and export endpoints."""
from datetime import datetime, time, timedelta

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from .. import cache
from ..auth import require_admin
from ..database import get_db
from ..errors import AppError
from ..models import Booking, Room, User
from ..services.export import generate_export
from ..timeutils import parse_input_datetime

router = APIRouter(prefix="/admin", tags=["admin"])


def _parse_report_start(value: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        try:
            return parse_input_datetime(value)
        except ValueError:
            raise AppError(400, "INVALID_BOOKING_WINDOW", "Invalid date range")


def _parse_report_end(value: str) -> tuple[datetime, bool]:
    try:
        date_value = datetime.strptime(value, "%Y-%m-%d").date()
        return datetime.combine(date_value + timedelta(days=1), time.min), True
    except ValueError:
        try:
            return parse_input_datetime(value), False
        except ValueError:
            raise AppError(400, "INVALID_BOOKING_WINDOW", "Invalid date range")


@router.get("/usage-report")
def usage_report(
    frm: str = Query(..., alias="from"),
    to: str = Query(...),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    cached = cache.get_report(admin.org_id, frm, to)
    if cached is not None:
        return cached

    range_start = _parse_report_start(frm)
    range_end, end_is_exclusive = _parse_report_end(to)
    if end_is_exclusive:
        end_filter = Booking.start_time < range_end
    else:
        end_filter = Booking.start_time <= range_end

    rooms = db.query(Room).filter(Room.org_id == admin.org_id).order_by(Room.id.asc()).all()
    room_rows = []
    for room in rooms:
        bookings = (
            db.query(Booking)
            .filter(
                Booking.room_id == room.id,
                Booking.status == "confirmed",
                Booking.start_time >= range_start,
                end_filter,
            )
            .all()
        )
        room_rows.append(
            {
                "room_id": room.id,
                "room_name": room.name,
                "confirmed_bookings": len(bookings),
                "revenue_cents": sum(b.price_cents for b in bookings),
            }
        )

    result = {"from": frm, "to": to, "rooms": room_rows}
    cache.set_report(admin.org_id, frm, to, result)
    return result


@router.get("/export")
def export(
    room_id: int | None = Query(None),
    include_all: bool = Query(False),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if room_id is not None:
        room = db.query(Room).filter(Room.id == room_id, Room.org_id == admin.org_id).first()
        if room is None:
            raise AppError(404, "ROOM_NOT_FOUND", "Room not found")
    csv_body = generate_export(db, admin.org_id, room_id, include_all)
    return Response(content=csv_body, media_type="text/csv")
