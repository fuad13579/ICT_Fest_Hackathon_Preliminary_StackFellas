from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import jwt
from fastapi.testclient import TestClient

from app.config import JWT_ALGORITHM, JWT_SECRET
from app.main import app

client = TestClient(app)


def _future(hours: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).replace(
        minute=0, second=0, microsecond=0
    ).isoformat()


def _register_login(org: str, username: str = "alice") -> dict:
    registered = client.post(
        "/auth/register",
        json={"org_name": org, "username": username, "password": "pw12345"},
    )
    assert registered.status_code == 201
    logged_in = client.post(
        "/auth/login",
        json={"org_name": org, "username": username, "password": "pw12345"},
    )
    assert logged_in.status_code == 200
    tokens = logged_in.json()
    tokens["headers"] = {"Authorization": f"Bearer {tokens['access_token']}"}
    return tokens


def _create_room(headers: dict, name: str = "Focus Room") -> int:
    response = client.post(
        "/rooms",
        json={"name": name, "capacity": 4, "hourly_rate_cents": 1001},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_access_ttl_logout_and_refresh_rotation():
    tokens = _register_login(f"auth-{datetime.now().timestamp()}")

    payload = jwt.decode(tokens["access_token"], JWT_SECRET, algorithms=[JWT_ALGORITHM])
    assert payload["exp"] - payload["iat"] == 900

    assert client.post("/auth/logout", headers=tokens["headers"]).status_code == 200
    assert client.get("/rooms", headers=tokens["headers"]).status_code == 401

    refreshed = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refreshed.status_code == 200
    reused = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert reused.status_code == 401


def test_duplicate_registration_conflicts():
    org = f"dupe-{datetime.now().timestamp()}"
    _register_login(org)
    duplicate = client.post(
        "/auth/register",
        json={"org_name": org, "username": "alice", "password": "different"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "USERNAME_TAKEN"


def test_back_to_back_bookings_and_pagination_contract():
    headers = _register_login(f"pages-{datetime.now().timestamp()}")["headers"]
    room_id = _create_room(headers)

    first = client.post(
        "/bookings",
        json={"room_id": room_id, "start_time": _future(60), "end_time": _future(61)},
        headers=headers,
    )
    assert first.status_code == 201
    second = client.post(
        "/bookings",
        json={"room_id": room_id, "start_time": _future(61), "end_time": _future(62)},
        headers=headers,
    )
    assert second.status_code == 201

    page_one = client.get("/bookings?page=1&limit=1", headers=headers)
    page_two = client.get("/bookings?page=2&limit=1", headers=headers)
    assert page_one.status_code == 200
    assert page_two.status_code == 200
    assert page_one.json()["items"][0]["id"] == first.json()["id"]
    assert page_two.json()["items"][0]["id"] == second.json()["id"]


def test_booking_detail_preserves_start_time_and_cancel_refund_policy():
    headers = _register_login(f"detail-{datetime.now().timestamp()}")["headers"]
    room_id = _create_room(headers)
    booking = client.post(
        "/bookings",
        json={"room_id": room_id, "start_time": _future(25), "end_time": _future(26)},
        headers=headers,
    )
    assert booking.status_code == 201
    booking_json = booking.json()

    detail = client.get(f"/bookings/{booking_json['id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["start_time"] == booking_json["start_time"]

    cancelled = client.post(f"/bookings/{booking_json['id']}/cancel", headers=headers)
    assert cancelled.status_code == 200
    assert cancelled.json()["refund_percent"] == 50
    assert cancelled.json()["refund_amount_cents"] == 501


def test_short_booking_window_is_rejected():
    headers = _register_login(f"window-{datetime.now().timestamp()}")["headers"]
    room_id = _create_room(headers)
    response = client.post(
        "/bookings",
        json={
            "room_id": room_id,
            "start_time": _future(60),
            "end_time": (
                datetime.now(timezone.utc) + timedelta(hours=60, minutes=30)
            ).replace(second=0, microsecond=0).isoformat(),
        },
        headers=headers,
    )
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_BOOKING_WINDOW"

    invalid = client.post(
        "/bookings",
        json={"room_id": room_id, "start_time": "not-a-date", "end_time": _future(61)},
        headers=headers,
    )
    assert invalid.status_code == 400
    assert invalid.json()["code"] == "INVALID_BOOKING_WINDOW"


def test_export_include_all_does_not_leak_cross_org_room():
    org_a = _register_login(f"export-a-{datetime.now().timestamp()}")
    org_b = _register_login(f"export-b-{datetime.now().timestamp()}")
    room_b = _create_room(org_b["headers"], "Other Org Room")
    booking_b = client.post(
        "/bookings",
        json={"room_id": room_b, "start_time": _future(80), "end_time": _future(81)},
        headers=org_b["headers"],
    )
    assert booking_b.status_code == 201

    exported = client.get(
        f"/admin/export?include_all=true&room_id={room_b}",
        headers=org_a["headers"],
    )
    assert exported.status_code == 404
    assert exported.json()["code"] == "ROOM_NOT_FOUND"


def test_report_cache_includes_room_created_after_cached_report():
    headers = _register_login(f"report-cache-{datetime.now().timestamp()}")["headers"]
    first_room = _create_room(headers, "First")
    first_report = client.get("/admin/usage-report?from=2099-01-01&to=2099-01-01", headers=headers)
    assert first_report.status_code == 200
    assert [row["room_id"] for row in first_report.json()["rooms"]] == [first_room]

    second_room = _create_room(headers, "Second")
    second_report = client.get("/admin/usage-report?from=2099-01-01&to=2099-01-01", headers=headers)
    assert second_report.status_code == 200
    assert [row["room_id"] for row in second_report.json()["rooms"]] == [first_room, second_room]


def test_room_stats_are_derived_from_confirmed_bookings():
    headers = _register_login(f"stats-{datetime.now().timestamp()}")["headers"]
    room_id = _create_room(headers)
    booking = client.post(
        "/bookings",
        json={"room_id": room_id, "start_time": _future(90), "end_time": _future(91)},
        headers=headers,
    )
    assert booking.status_code == 201

    stats = client.get(f"/rooms/{room_id}/stats", headers=headers)
    assert stats.status_code == 200
    assert stats.json()["total_confirmed_bookings"] == 1
    assert stats.json()["total_revenue_cents"] == 1001

    cancelled = client.post(f"/bookings/{booking.json()['id']}/cancel", headers=headers)
    assert cancelled.status_code == 200
    stats_after_cancel = client.get(f"/rooms/{room_id}/stats", headers=headers)
    assert stats_after_cancel.status_code == 200
    assert stats_after_cancel.json()["total_confirmed_bookings"] == 0
    assert stats_after_cancel.json()["total_revenue_cents"] == 0


def test_concurrent_overlapping_bookings_allow_only_one_success():
    headers = _register_login(f"concurrent-book-{datetime.now().timestamp()}")["headers"]
    room_id = _create_room(headers)
    payload = {"room_id": room_id, "start_time": _future(100), "end_time": _future(101)}

    def create():
        return client.post("/bookings", json=payload, headers=headers).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = sorted(executor.map(lambda _: create(), range(2)))

    assert statuses == [201, 409]


def test_concurrent_cancel_creates_exactly_one_refund():
    headers = _register_login(f"concurrent-cancel-{datetime.now().timestamp()}")["headers"]
    room_id = _create_room(headers)
    booking = client.post(
        "/bookings",
        json={"room_id": room_id, "start_time": _future(110), "end_time": _future(111)},
        headers=headers,
    )
    assert booking.status_code == 201
    booking_id = booking.json()["id"]

    def cancel():
        return client.post(f"/bookings/{booking_id}/cancel", headers=headers).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = sorted(executor.map(lambda _: cancel(), range(2)))

    assert statuses == [200, 409]
    detail = client.get(f"/bookings/{booking_id}", headers=headers)
    assert detail.status_code == 200
    assert len(detail.json()["refunds"]) == 1
