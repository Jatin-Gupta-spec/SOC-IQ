# Motion / Animation Architecture

**Status:** Documentation Foundation (Phase 4A). No motion implementation exists yet — the
current PySide6 GUI's animation surface (`app/gui/design/animations/`,
`app/gui/components/buttons/animated_button.py`) was not independently re-verified in detail
during this pass; treat any specific current animation behavior as **UNKNOWN — VERIFY IN
PHASE 4B**.
**Related:** Master Plan §11.

## CURRENT STATE

`app/gui/design/animations/__init__.py` exists (CONFIRMED, directory listing) and an
`AnimatedButton` component exists (CONFIRMED, `app/gui/components/buttons/animated_button.py`
present). The specific easing/duration values and transition patterns currently in use are
**UNKNOWN — VERIFY IN PHASE 4B**; this document does not assume they match the target scale
below.

## TARGET STATE (PROPOSED)

Principles adapted from Framer Motion / motion.dev interaction conventions (Master Plan §11
— referenced for inspiration only, not copied):

- **Duration scale:** micro 100ms · small 150ms · base 250ms · large 400ms — driven by the
  ported `duration` token (see `11-design-system-architecture.md`).
- **Easing scale:** standard ease-out for entrances, ease-in for exits; a slightly overshot
  spring reserved for exactly one use — the risk-score gauge transition — so it reads as a
  meaningful moment rather than decoration.
- **Entrance/exit rules:** page transitions cross-fade with a slight vertical slide (8px);
  panels within a page use scale+fade, never full-page slide, to preserve spatial continuity
  inside the investigation workspace.
- **Verdict-state transitions:** a TI status badge changing state (e.g. "pending →
  malicious") animates via a color+icon morph, not a full re-render flash — this is the
  motion-layer expression of the `NOT_FOUND != CLEAN` invariant staying perceptible during a
  live update.
- **Skeleton shimmer:** used only for data genuinely loading over the wire (investigation
  fetch, TI enrichment in progress) — never used to fake latency that isn't real.
- **Reduced-motion behavior:** `prefers-reduced-motion` disables all non-essential
  transitions. State-changing animations (verdict updates) degrade to an instant color
  change rather than disappearing — the status change itself must remain perceivable even
  with motion off.
- **Where animation is prohibited:** dense data tables (IOC lists, history), form inputs, and
  the command-palette result list (beyond a 100ms fade) — an analyst scanning many rows needs
  visual stability, not motion.

## MIGRATION NOTES

Motion system implementation is part of Phase 4F (design system), consuming the `duration`
and `easing` tokens defined in `11-design-system-architecture.md`.

## UNKNOWN / REQUIRES VERIFICATION

Current PySide6 animation behavior (`app/gui/design/animations/`,
`animated_button.py`, and any transition logic in `app/gui/design/theme/`): **UNKNOWN —
VERIFY IN PHASE 4B.** Nothing above should be read as a claim that the target motion system
matches or replaces a specific verified current behavior.
