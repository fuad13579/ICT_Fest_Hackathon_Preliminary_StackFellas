"""Caching helpers.

Caching is intentionally disabled so read endpoints always reflect the current
database state, which is required by the API contract.
"""


def get_report(org_id: int, frm: str, to: str):
    return None


def set_report(org_id: int, frm: str, to: str, value: dict) -> None:
    return None


def invalidate_report(org_id: int) -> None:
    return None


def get_availability(room_id: int, date: str):
    return None


def set_availability(room_id: int, date: str, value: dict) -> None:
    return None


def invalidate_availability(room_id: int, date: str) -> None:
    return None
