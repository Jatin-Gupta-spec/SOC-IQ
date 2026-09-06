# Design System Architecture

**Status:** Documentation Foundation (Phase 4A).
**Related:** Master Plan §10, §1.7 (current-state token confirmation).

## CURRENT STATE (CONFIRMED)

`app/gui/design/tokens/` contains eight distinct token category modules:
`colors.py`, `spacing.py`, `radius.py`, `typography.py`, `elevation.py`, `duration.py`,
`easing.py`, `opacity.py`. This is genuine, non-trivial design-system groundwork
(CONFIRMED by directory listing and prior audit) — not boilerplate, and not something to
discard and rebuild from nothing.

**This document does not restate the specific values inside those token files.** Per the
instruction governing this documentation pass, token *values* are not invented here without
direct verification against the current implementation — doing so risks silently diverging
from the real values and shipping wrong constants into a future TypeScript port. The specific
numeric/hex values are **UNKNOWN — VERIFY IN PHASE 4B** (a direct read of each token file)
before any TypeScript token module is written.

## TARGET STATE (PROPOSED — structure, not values)

```
tokens/
├── color.ts        base + semantic (bg/surface/border/text) + status (malicious/suspicious/clean/unknown)
├── spacing.ts
├── radius.ts
├── typography.ts
├── elevation.ts     → box-shadow scale
├── duration.ts      → motion timing scale (feeds 12-motion-animation-architecture.md)
├── easing.ts        → cubic-bezier scale
└── opacity.ts
```

The eight categories are **preserved as a structure**; their *implementation* moves from
Python/Qt objects to TypeScript constants + CSS custom properties (Master Plan §27:
"design tokens: PRESERVE (values) / REDESIGN (implementation)").

**Semantic cybersecurity verdict colors** are a new addition on top of the base token set —
malicious / suspicious / clean / not-found / unavailable each get a distinct, named semantic
color so the `NOT_FOUND != CLEAN` invariant (see `08-threat-intelligence-architecture.md`) is
visually enforced, not just data-enforced. The exact color values are chosen at
implementation time against accessibility contrast requirements (see
`docs/security/` is not the right home for this — accessibility contrast is tracked as an
implementation detail of Phase 4F, not a security concern).

**Component hierarchy, responsive behavior, dashboard constraints:** see
`13-frontend-information-architecture.md` for the 1440×900/1280×720 layout rules this token
system must support.

## MIGRATION NOTES

Token porting is part of Phase 4F (Master Plan §26), gated on the Phase 4B value-verification
step above — no TS token file should be written with placeholder/invented numeric values.

## UNKNOWN / REQUIRES VERIFICATION

Exact current values of all eight token categories: **UNKNOWN — VERIFY IN PHASE 4B.** This is
the single most important unknown blocking accurate (not just structurally-correct) design
system porting.
