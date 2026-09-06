# Event Versioning

**Status:** Documentation Foundation (Phase 4A).
**Related:** `event-model.md`, Master Plan §15.

## CURRENT STATE

No event versioning exists today — the current Qt signal buses carry unversioned payloads
(CONFIRMED by source inspection of `application_events.py` and `event_bus.py`; Signal
definitions have no version concept).

## TARGET STATE (PROPOSED)

Every event carries an explicit integer `version` field (see `event-model.md`'s envelope).
Rules:

- A **backward-compatible** payload change (adding an optional field) does not require a
  version bump.
- A **breaking** payload change (removing a field, changing a field's type or meaning)
  requires incrementing `version` for that event name, and the publisher must be able to
  emit the new version only after all consumers (frontend, and any other future subscriber)
  are updated to handle it — there is no silent breaking change.
- Subscribers should ignore fields they don't recognize (forward-compatible parsing) rather
  than failing on an unexpected field.
- Contract tests (`docs/testing/testing-architecture.md`) pin the current schema for each
  `(event, version)` pair as a golden file, so an accidental breaking change without a version
  bump fails CI.

## MIGRATION NOTES

Versioning is introduced from the very first event ever published (Phase 4D) — there is no
"unversioned v0" period to migrate away from, unlike the current buses.

## UNKNOWN / REQUIRES VERIFICATION

None — this is a new, from-scratch design constraint with no current-state dependency beyond
the negative confirmation that no versioning exists today.
