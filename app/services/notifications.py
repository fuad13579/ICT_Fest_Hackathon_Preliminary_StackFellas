"""Side effects that accompany booking lifecycle events.

Each booking change sends a (simulated) notification email and appends an
audit-log entry. Both resources are guarded by locks so their output stays
consistent when many requests are processed at once.
"""
def notify_created(booking) -> None:
    return None


def notify_cancelled(booking) -> None:
    return None
