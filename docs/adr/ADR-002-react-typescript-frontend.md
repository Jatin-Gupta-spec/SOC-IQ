# ADR-002: React + TypeScript as the Presentation Layer

**Status:** Proposed
**Related:** Master Plan §28, §9.

## Context

The current presentation layer is PySide6 (Qt), CONFIRMED to include a real, if imperfect,
design-token system (eight token categories, Master Plan §1.7) and a working component
library. The target architecture calls for a modernized frontend for both usability and
recruiter-facing credibility (Master Plan baseline problem #16).

## Problem

PySide6 can be extended, but building a modern, animated, dashboard-quality desktop UI in Qt
requires substantial custom widget work that Qt is not naturally suited for compared to a
web-native UI toolkit, and does not demonstrate contemporary frontend engineering skills to a
reviewer.

## Decision

React + TypeScript becomes the presentation layer, rendered inside a Tauri webview. React
owns UI, visualization, dashboards, the investigation workspace's presentation,
interaction/state presentation, the design system, and motion — and nothing else (Master
Plan §2 diagram: React must not access SQLite directly, implement risk scoring, implement
threat-intelligence providers, or duplicate Python domain logic).

## Alternatives Considered

- **Extend PySide6 with custom-painted widgets to achieve a modern look.** Technically
  possible but does not solve the underlying problem that Qt's default widget set drives most
  of the visual/interaction limitations; substantial custom work would still be required, with
  a worse ecosystem for motion/animation libraries than the web has.
- **Vue or Svelte instead of React.** Not evaluated in depth — React was chosen primarily for
  ecosystem maturity (component libraries, motion libraries, TypeScript tooling) rather than a
  hard technical requirement unique to React; this is a **PROPOSED**, not exhaustively
  comparative, decision.

## Rejected Alternatives (explicit)

Keeping PySide6 as the permanent, only presentation layer — rejected because it does not
address baseline problem #16 (frontend/recruiter credibility) or provide a natural path to
the motion/animation system in Master Plan §11.

## Consequences

- Positive: access to a mature web component/motion/visualization ecosystem; clearer
  separation of presentation from domain logic than the current controller/widget mixing in
  `app/gui/`.
- Negative: introduces a second UI stack to maintain during the migration window (Phase 4F–4O)
  before PySide6 is retired; requires the IPC boundary (ADR-006) to be solid before frontend
  work can safely begin.

## Security Implications

React runs inside a sandboxed Tauri webview with no direct filesystem/network access (see
`docs/security/trust-boundary-model.md`) — this is a stricter security posture than the
current in-process Qt GUI, which has no such sandboxing today.

## Migration Implications

The PySide6 GUI is retired only after the React frontend reaches feature parity (Phase 4O),
not before (ADR-009). Until then both UIs exist, but only one (PySide6) is a live product
surface; React is being built, not yet shipped, during Phases 4F–4N.
