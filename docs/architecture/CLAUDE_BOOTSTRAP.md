# SOC-IQ — Claude Bootstrap

You are continuing work on SOC-IQ. This file is instructions to you, a fresh Claude session
with no memory of any previous chat.

## Before touching code

1. Read `PROJECT_CONSTITUTION.md`.
2. Read `NON_NEGOTIABLE_RULES.md`.
3. Read `docs/architecture/PHASE4_NEXT_GENERATION_ARCHITECTURE_MASTER_PLAN.md` (the
   architecture bible) — at least the sections relevant to your task.
4. Read `CURRENT_STATE.md`.
5. Read `IMPLEMENTATION_STATUS.md`.
6. Read the current phase document — check `PROJECT_CONSTITUTION.md` §24/§26 for which one
   that is, and re-confirm it's still accurate rather than trusting the constitution's
   snapshot blindly (phase status changes; this document may be stale by the time you read
   it).
7. Inspect `git status` and `git log -n 5` yourself. If `.git` is unavailable, say so
   explicitly — do not pretend you checked it, and do not assume the same "no git history"
   condition documented in earlier phases still holds without checking.
8. Inspect the relevant source files directly. Do not trust a prior document's claim about
   source content without spot-checking it, especially for anything you're about to modify.
9. Do not assume previous chat context is available. Everything you need is either in this
   docs/architecture tree or verifiable by reading source.

## Never

- Never invent architecture. If a decision isn't documented, that's an UNKNOWN — add it to
  `UNKNOWN_AND_ASSUMPTIONS.md`, don't silently decide it and proceed.
- Never silently change a decision that's already recorded in the constitution, an ADR, or
  the master plan. If you believe one is wrong, say so explicitly, propose the correction,
  and update the authoritative document deliberately (see the Authority Hierarchy in
  `PROJECT_CONSTITUTION.md` §12) — don't just code around it.
- Never start a future phase early. Check `IMPLEMENTATION_STATUS.md`'s phase table and the
  exit criteria for your current phase before beginning work that belongs to a later one.

## Before implementation, state explicitly

- What phase you're in.
- What task is authorized (cite the phase document / roadmap row that authorizes it).
- Which files you expect to change.
- Which architectural boundaries are involved (data/command/event/state ownership,
  technology-responsibility matrix).
- Which tests are required to prove the change.
- Exit criteria for the task.

## After implementation

- Run the tests. Report the actual command and actual output — don't state a test count you
  didn't personally observe this session.
- Inspect the diff.
- Verify architecture boundaries weren't crossed (check against `NON_NEGOTIABLE_RULES.md`).
- Update `IMPLEMENTATION_STATUS.md` (and `CURRENT_STATE.md` if the repo shape changed).
- Update other docs only if architectural behavior genuinely changed — not to "keep docs in
  sync" cosmetically.
- Report exactly what changed, including what you deliberately did NOT do and why, mirroring
  the "Explicit non-actions" pattern already used in `docs/migration/PHASE4B_EXIT_CRITERIA.md`.

## If code and documentation disagree

Don't blindly change either. Determine whether the code is stale, the documentation is
stale, or the architecture decision genuinely changed since the doc was written. Then update
the authoritative document deliberately, with a visible before/after note (Phase 4B already
set this precedent in `09-database-architecture.md`, `06-event-architecture.md`,
`07-state-architecture.md` — follow that pattern).
