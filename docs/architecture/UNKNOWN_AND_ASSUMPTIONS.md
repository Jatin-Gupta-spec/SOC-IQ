# SOC-IQ — Unknowns and Assumptions

Most Phase-4B-era unknowns were resolved during Phase 4B itself — see
`docs/architecture/PHASE4B_ARCHITECTURAL_FINDINGS.md`, "Remaining unknowns" section, for the
authoritative list of what that phase explicitly escalated rather than silently assumed
(reporting internals, settings internals beyond what Phase 4C touched, scoring engine
internals, extractor internals beyond what was directly read).

This document tracks what remains open **as of this session**, verified by direct inspection
rather than carried over from memory of prior chats.

## Confirmed-open unknowns (re-checked this session)

1. **Exact target subpackage for `app/main.py`, `initializer.py`, `config.py`,
   `exceptions.py`, `exporters.py`, `display.py`, `logger.py`.** No source document reviewed
   this session pins these down beyond "PRESERVE logic." Do not invent a target path —
   confirm with a human or a dedicated phase document before moving these files.
2. **Exact boundary between `domain/extraction/` and a possible `domain/analysis/`** for
   `extractor.py` vs `analyzer.py`. Master plan §4.1 groups both under
   `backend/app/domain/extraction/`, but doesn't explain why `analyzer.py` (which appears to
   do more than extraction) belongs there rather than a separate module. Treat as LIKELY,
   not CONFIRMED.
3. **Target home for `tests/gui/`.** The GUI code it tests is scheduled for REMOVE, but no
   document states explicitly whether the GUI test suite is deleted alongside it, ported to
   test the React equivalent, or archived. Flag before deleting.
4. **Whether a `.git` history now exists in the live project repository.** Every archive
   snapshot reviewed so far (Phase 4B, Phase 4D) lacked `.git`. If a future session has
   access to the real repo (not a fresh zip), check `git log` directly rather than assuming
   the "no git history" condition still holds — see
   `docs/migration/PHASE4B_GIT_BASELINE_NOTE.md`.
5. **Whether the 542-test combined (GUI + non-GUI) baseline is still accurate.** Only the
   399 non-GUI tests were re-run this session (all passing). The GUI portion could not be
   collected here (missing `PySide6`). Don't cite "542" as freshly verified.
6. **Frontend build tooling choice** (Vite vs. other) — not specified in any document
   reviewed this session. Do not assume one when Phase 4F begins; it needs an explicit
   decision or ADR.
7. **Exact database migration runner design** (versioning scheme, forward-only vs.
   up/down, tooling) — master plan says "introduce" one but does not specify the mechanism.
   Confirm against `docs/architecture/09-database-architecture.md` (BEFORE/AFTER-corrected
   in Phase 4B) before implementing; if it's still silent on the mechanism, that's a design
   task, not an implementation task.

## Assumptions made while writing this documentation layer (flag if wrong)

- Assumed the archive's absence of `.git` and `fastapi`/`PySide6` packages reflects a
  sandbox/packaging limitation, not an intentional removal from the real project. If a
  future session finds these differently, update `CURRENT_STATE.md` and
  `IMPLEMENTATION_STATUS.md` rather than assuming this document is still right.
- Assumed "this session" test results (399 passed, GUI suite uncollectable) are worth
  recording as a fresh data point rather than silently trusting the older "542" claim. If a
  future session gets a different number, that's a real signal (either the environment
  changed or the code did) — investigate, don't just overwrite the number.
