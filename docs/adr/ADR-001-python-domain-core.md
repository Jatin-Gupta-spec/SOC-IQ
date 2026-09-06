# ADR-001: Python Remains the Domain Core

**Status:** Proposed (approved as part of Phase 4A architecture baseline)
**Implementation note (added during later documentation reconciliation):** "not yet
implemented" above referred to formal ADR acceptance, not to the domain core itself — the
Context section below already states the ~39,300 LOC Python domain core exists and is
shared by the CLI and GUI. Source inspection in later sessions confirms this decision has
been adhered to since: no scoring/extraction/risk logic has been duplicated into
TypeScript or Rust as the frontend and native layers were built out. ADR governance status
is unchanged by this note; see ADR-008 (`docs/adr/ADR-008-secure-secret-storage.md`) for
the same distinction applied to secret storage.
**Related:** Master Plan §28, §4, §1.1–1.2.

## Context

SOC-IQ's current domain logic (extraction, scoring, threat intelligence, persistence,
reporting, correlation) is implemented in Python (~39,300 LOC, CONFIRMED) and is already
shared by two clients — the PySide6 GUI and a 76-line CLI — both importing the same `app.*`
modules directly (CONFIRMED, Master Plan §1.1). The target architecture introduces React,
Rust, and Tauri; a decision is needed about where business logic lives once those are added.

## Problem

Adding new languages/frameworks creates a risk of domain logic being duplicated or
fragmented across them — e.g., a naive integration might reimplement scoring in TypeScript
for UI responsiveness, or risk logic in Rust "for performance," without evidence such
duplication is needed.

## Decision

Python remains the exclusive owner of domain logic: extraction, normalization, risk scoring,
threat-intelligence orchestration, correlation, reporting, and persistence. No other layer
reimplements any part of this logic. React and Rust interact with domain logic only by
issuing commands to the Python layer over the IPC boundary (ADR-006) and never compute
domain results themselves.

## Alternatives Considered

- **Port scoring/extraction to Rust for performance.** No measured evidence in the current
  checkpoint indicates a performance problem (Master Plan baseline problem #14: "no measured
  evidence currently justifies rewriting Python backend logic in Rust"). Rejected for lack of
  justification, not on principle — this could be revisited if profiling ever shows a real
  bottleneck.
- **Duplicate lightweight scoring logic in TypeScript for optimistic UI feedback.** Rejected
  — any duplication risks the two implementations drifting, and the event-stream-driven async
  pattern (`docs/architecture/03-frontend-architecture.md`) makes optimistic *local*
  scoring unnecessary; the UI shows a pending state, not a locally-computed guess.

## Rejected Alternatives (explicit)

Full backend rewrite in another language (considered nowhere seriously — no runtime, ecosystem,
or capability gap in Python was identified that would justify it; CLI/GUI dual-client reuse is
direct evidence Python's current architecture is already sound).

## Consequences

- Positive: single source of truth for domain behavior; the CLI, GUI (during transition), and
  future API all exercise identical logic paths, reducing the chance of the API returning
  different results than the CLI for the same input.
- Negative: any performance-sensitive operation not currently fast enough must be optimized
  within Python (algorithmic improvement, caching) rather than reached for a rewrite — this
  is an accepted tradeoff, not an oversight.

## Security Implications

Concentrating domain logic in one language/process reduces the attack surface for logic
inconsistency (e.g., a scoring bug present in one implementation but not another). It does
mean the Python sidecar becomes the single most security-critical process boundary — see
`docs/security/trust-boundary-model.md`.

## Migration Implications

The bulk of `app/` is preserved and repackaged (Master Plan §4.1 file-level mapping), not
rewritten. This ADR is the reason the migration plan (§26) has no phase dedicated to
"rewrite backend" — there isn't one.
