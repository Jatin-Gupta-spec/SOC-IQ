# ADR-009: Staged Migration — PySide6 Retired Only After Feature Parity

**Status:** Proposed
**Related:** Master Plan §28, §26 (full phase table).

## Context

The target architecture replaces the entire presentation layer (PySide6 → React/Tauri) and
restructures the domain core's packaging, while explicitly preserving ~39,300 LOC of working
Python logic and a 542-test baseline. A migration approach must be chosen.

## Problem

A "rewrite from scratch" approach (Master Plan §26: explicitly rejected — "DO NOT recommend
'delete PySide6 and build React from scratch'") would discard working, tested functionality
and leave the project with no working GUI for an extended period. Conversely, an
unstructured incremental approach without phase gates risks partially-migrated states with
unclear correctness.

## Decision

A 16-phase staged migration (Phase 4A through 4P, Master Plan §26), where:

1. Each phase has an explicit objective, affected modules, deliverables, and exit criterion.
2. The PySide6 GUI remains the only working GUI client until the React frontend reaches
   feature parity (Phase 4O) — the old and new systems coexist during the transition rather
   than one being torn down before the other is ready.
3. No phase is permitted to leave the 542-test Python baseline broken.
4. IPC contract (4D), Tauri foundation (4E), and the TI provider abstraction (4C) are built
   and proven *before* frontend feature work begins (4F onward) — dependencies are ordered so
   later phases build on verified foundations, not assumptions.

## Alternatives Considered

- **Big-bang rewrite:** build the entire new stack in a branch, then switch over. Rejected —
  no working software exists during the entire migration window, and any subtle regression
  in preserved logic (e.g. scoring, reporting) would be caught late, if at all, rather than
  incrementally.
- **Migrate GUI page-by-page inside PySide6 first (e.g. modernize Qt styling) before
  introducing React at all.** Rejected — doesn't address the underlying limitations of Qt for
  the target motion/design-system goals (Master Plan §11) and would be throwaway work once
  React is introduced anyway.

## Rejected Alternatives (explicit)

Retiring PySide6 early (e.g. at Phase 4G once a navigable shell exists) to "reduce
maintenance burden" — rejected; explicitly named as an architecture mistake to avoid (Master
Plan §30.H: "retiring the PySide6 GUI before the React frontend has real parity").

## Consequences

- Positive: at every point in the migration, a working product exists (PySide6, until parity;
  React, after).
- Negative: two GUI implementations must be reasoned about (though not both actively
  developed feature-by-feature) for a significant span of the migration, which is a real
  ongoing cost, accepted deliberately rather than overlooked.

## Security Implications

None directly — this ADR is about sequencing, not security posture. Security-specific
sequencing (why hardening is Phase 4M, not earlier or later) is addressed in
`docs/security/` documents individually.

## Migration Implications

This ADR *is* the migration plan's rationale; the phase table itself lives in the Master Plan
§26 and is not duplicated here.
