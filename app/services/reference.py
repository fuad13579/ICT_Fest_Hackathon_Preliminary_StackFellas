"""Human-facing booking reference codes.

Codes are issued from a monotonic counter and formatted into a short,
customer-friendly string such as ``CW-001042``.
"""
import threading
import uuid

_counter = {"value": 1000}
_counter_lock = threading.Lock()


def next_reference_code() -> str:
    with _counter_lock:
        current = _counter["value"]
        _counter["value"] = current + 1
    return f"CW-{current:06d}-{uuid.uuid4().hex[:6].upper()}"
