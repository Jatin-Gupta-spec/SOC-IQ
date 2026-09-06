# Phase 4 Checkpoint Naming — Canonical Note

**Status:** Documentation clarification only. No code or history was changed to produce
this note; it exists to stop the ambiguity below from confusing a future implementation
agent.

## The contradiction

Two unrelated things have both been called "Phase 4E Part 1" or "Part 1" in this repo's
history:

1. **`docs/phase4/PHASE4E_PART1_IMPLEMENTATION.md`** — the Python sidecar entrypoint +
   `/health` route work (the P0 items from `PHASE4E_SIDECAR_TAURI_SCOPE.md` §4). Verified,
   frozen, 572 passed / 2 skipped at last real run.
2. **`docs/phase4/PHASE4E_PART1_REACT_TAURI_FOUNDATION_REPORT.md`** — the React +
   TypeScript frontend scaffold and the Tauri/Rust shell scaffold (`frontend/`,
   `src-tauri/`). This is what the current checkpoint zip
   (`SOC-IQ-Phase4-Part1-React-Tauri-Foundation.zip`) contains.

Separately, `docs/architecture/03-frontend-architecture.md` and
`docs/phase4/PHASE4E_SIDECAR_TAURI_SCOPE.md` §6 both state the React frontend is master-plan
**Phase 4F+** work and should not exist until the Tauri foundation and IPC contract are
already in place — which is in tension with building `frontend/` at this checkpoint.

## Canonical interpretation (this document is the tie-breaker)

- **Historical phase documents** (`PHASE4E_SIDECAR_TAURI_SCOPE.md`, the master plan, and
  `PHASE4E_PART1_IMPLEMENTATION.md`) describe the **original planned sequencing** and are
  preserved as-is — they are not rewritten by this note.
- **Current implementation checkpoints** (this repository's actual, executed increments)
  do not have to match that original sequencing 1:1, because later task briefs explicitly
  chose to build the React scaffold and the Tauri scaffold together as one foundation
  checkpoint, ahead of the strict "4E fully done, then 4F" ordering. That deviation was
  flagged, not silently made, in
  `PHASE4E_PART1_REACT_TAURI_FOUNDATION_REPORT.md` §18.
- From this checkpoint forward, **"Phase 2A" refers exclusively** to the sidecar-core /
  supervisor / lifecycle work described in this task's own brief (Sections 10–15 of the
  correction task, and `PHASE4E_SIDECAR_TAURI_SCOPE.md` §4 P1 "minimal Tauri shell"
  behavior: spawn, health-check, shutdown). It is **not** a synonym for any historical
  "Part 1" or "Part 2" label used elsewhere.
- **Historical phase documents ≠ current implementation checkpoints.** Where the two
  disagree on ordering, the current checkpoint's own report (its "Architecture Deviations"
  section, if present) is the record of what actually happened and why; the historical
  document is the record of what was originally planned. Neither is edited to match the
  other after the fact.

## What this means for the next implementation agent

Before starting anything labeled "Phase 2A" in this repository, confirm it means the
sidecar supervisor work defined in the correction task that produced this checkpoint —
**not** a renumbering of `PHASE4E_PART1_IMPLEMENTATION.md`'s already-frozen sidecar
entrypoint work, and not a resumption of the strict master-plan 4E→4F ordering that this
checkpoint's own React+Tauri scaffold already departed from.
