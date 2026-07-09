# Bug Report

## Bug 1 — Concurrent overlapping bookings allowed
- Difficulty: Hard
- Rule violated: Rule 3, No double-booking under concurrent requests
- File: `app/routers/bookings.py`
- Root cause: Conflict check and insert were not atomic. Two concurrent requests could both see no conflict before either committed.
- Fix: Added a module-level booking creation lock around conflict check, quota check, reference generation, insert, commit, and refresh.
- Test: `test_concurrent_overlapping_bookings_allow_only_one_success`

## Bug 2 — Concurrent cancel could create inconsistent refund state
- Difficulty: Hard
- Rule violated: Rule 6
- File: `app/routers/bookings.py`
- Root cause: Concurrent cancel requests could process the same booking simultaneously and both attempt refund/log updates before cancellation state was visible.
- Fix: Added a cancellation critical-section lock and preserved `ALREADY_CANCELLED` behavior for the loser request.
- Test: `test_concurrent_cancel_creates_exactly_one_refund`

## Bug 3 — Member could read another member’s booking
- Difficulty: Medium/Hard
- Rule violated: Rule 10
- File: `app/routers/bookings.py`
- Root cause: `get_booking` checked organization only, not booking ownership for members.
- Fix: Added owner/admin visibility check and returned `404 BOOKING_NOT_FOUND` for unauthorized member access.
- Test: `test_member_cannot_get_another_members_booking_but_admin_can`

## Bug 4 — Duplicate username in same org returned wrong behavior
- Difficulty: Medium
- Rule violated: Rule 15
- File: `app/routers/auth.py`
- Root cause: Registration could find an existing user in the target org but still treat that path incorrectly instead of returning the required conflict response.
- Fix: Added an explicit duplicate-user check during registration and raised `409 USERNAME_TAKEN`; registration writes are also protected with a lock to avoid races.
- Test: `test_duplicate_registration_conflicts`

## Bug 5 — Refresh token reuse was allowed
- Difficulty: Hard
- Rule violated: Rule 8
- File: `app/routers/auth.py` / `app/auth.py`
- Root cause: Refresh tokens were decoded and accepted repeatedly because the app did not record consumed refresh token JTIs.
- Fix: Added refresh-token consumption tracking under a lock and rejected reused refresh tokens with `401`.
- Test: `test_access_ttl_logout_and_refresh_rotation`
