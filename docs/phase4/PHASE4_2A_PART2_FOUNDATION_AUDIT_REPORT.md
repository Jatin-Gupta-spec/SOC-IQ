# SOC-IQ Phase 2A Part 2 (sidecar-core, hardened) — Independent Freeze Audit

**Status:** PRE-2A/2A-PART2 CHECKPOINT — FROZEN
**Scope note:** This audit was performed against `SOC-IQ-Phase4-Part2A-Part2-SidecarCore-Hardened-Frozen.zip`,
a later checkpoint than the pre-2A freeze task brief originally supplied with this session assumed
(that brief predates `sidecar-core/` and explicitly forbids it). Per user instruction, this
checkpoint's already-implemented `sidecar-core` Part 1 + Part 2 (hardening) work is treated as
legitimate, in-scope prior work — not a violation to roll back. This report independently
re-verifies it rather than taking the repo's own `PHASE4_2A_PART1_SIDECAR_CORE.md` "frozen" claim
on faith.

## What was independently re-run (not just re-read)

| Check | Result |
|---|---|
| `npm install` (frontend/) | PASS — 72 packages, clean |
| `tsc --noEmit` | PASS — no errors |
| `npm run build` | PASS — produces `frontend/dist/` (144.79 kB JS, 4.16 kB CSS) matching `frontendDist` |
| Tauri `devUrl` vs Vite port | Consistent — both `1420` |
| Tauri `frontendDist` path | Correct — `../frontend/dist` resolves from `src-tauri/` |
| `python3 -m pytest tests/` | PASS — **574 passed**, 0 failed, matches the prior verified baseline exactly |
| `cargo check` (src-tauri, sidecar-core) | **ENVIRONMENT BLOCKED** — no `rustc`/`cargo` binary exists anywhere in this sandbox (not merely an old version this time — absent entirely) |

## Architecture boundary re-verification

- `sidecar-core/` is a standalone `rlib`, no Tauri dependency, `rust-version = 1.75` deliberately
  decoupled from `src-tauri`'s toolchain requirement — confirmed by reading `Cargo.toml` directly.
- `src-tauri/Cargo.toml` has **not** been touched to depend on `sidecar-core` — confirmed by reading
  it directly. No `tokio`, `reqwest`, or process-spawn crate present.
- `src-tauri/src/lib.rs` / `main.rs` are still the empty-shell scaffold — no `#[tauri::command]`,
  no sidecar wiring, no business logic. Confirmed by reading both files in full (they're 20 and 6
  lines).
- `sidecar-core/src/process.rs` defines only an `ExitStatus` data shape — no OS process spawn/kill/poll
  code anywhere in the crate. Confirmed by reading all 6 source files (616 lines total).
- Frontend (`frontend/src/`) contains only the app shell, providers, API/event-stream client
  scaffolding, and design tokens — no Dashboard, Investigation Workspace, Analyze, History, or
  Settings pages. Confirmed by directory listing.
- Rust test suite: 76 `#[test]` functions across 5 files (`error_tests.rs` 7, `lifecycle_tests.rs` 22,
  `shutdown_tests.rs` 13, `startup_tests.rs` 21, `supervisor_tests.rs` 13) — present and readable, but
  **could not be executed** (no cargo in this sandbox). This is an environment limitation, not a
  code defect assessment.

## Documentation consistency

- `PHASE4_CHECKPOINT_NAMING.md` and `PHASE4_2A_PART1_SIDECAR_CORE.md` §15 correctly disambiguate
  "Phase 2A" and record Part 1 + Part 2 hardening as one combined, internally consistent document
  (not a missing doc, as initially suspected — Part 2 is an addendum section, not a separate file).
- `docs/security/ipc-security-model.md` still correctly flags the loopback CSP wildcard as temporary
  and explicitly states Phase 2A must reconcile it before it can be called closed — accurate, since
  the sidecar-core ↔ Tauri wiring (the part that would need a real port) has not happened yet.

## Generated artifacts cleaned before freeze

Removed: all `__pycache__/`, `.pytest_cache/`, `frontend/node_modules/`, `frontend/dist/`.
Kept: `frontend/package-lock.json`, `src-tauri/Cargo.lock` (no `sidecar-core/Cargo.lock` — correct
per Cargo convention, since it's a library crate with no dev-dependencies).

## Remaining blocker

`cargo check` for both `src-tauri` and `sidecar-core` remains unverified in any sandbox used so far
across this project's history. This needs to happen on a machine with a real Rust toolchain
(≥1.85 for the Tauri graph; `sidecar-core` alone only needs ≥1.75) before Phase 2B (real process
integration / wiring sidecar-core into Tauri) begins.

## Final recommendation

**READY FOR PHASE 2B, CONDITIONAL ON A REAL `cargo check`.** Everything checkable without a Rust
toolchain — frontend build, Python regression suite, architecture boundaries, documentation
consistency, capability/CSP posture, absence of scope creep — passes. The Rust code itself has never
been compiled in any environment this project has used; that's the one open item before wiring
`sidecar-core` into `src-tauri` for real.
