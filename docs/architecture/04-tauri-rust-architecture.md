# Tauri + Rust Architecture

**Status:** Documentation Foundation (Phase 4A). No Rust/Tauri code exists yet.
**Related:** Master Plan §7 (capability architecture), §8 (Rust responsibilities), ADR-003,
ADR-004, and `docs/security/tauri-capability-model.md`.

## CURRENT STATE

No Rust or Tauri code exists in this project. There is no current native-shell layer at all —
PySide6 is both the UI toolkit and the OS-integration layer today (file dialogs, window
management), CONFIRMED by the presence of Qt-based dialog/window code under `app/gui/`. There
is no current least-privilege capability boundary between "what the UI can request" and "what
the OS will do" — Qt widgets call OS-integration APIs directly, in-process, with no
declared permission model. This is a real gap the target architecture closes, not a
preexisting feature being replaced.

## TARGET STATE (PROPOSED)

Tauri/Rust owns, and only owns (Master Plan §8):

| Responsibility | Timing |
|---|---|
| Tauri shell, window lifecycle, packaging | NOW |
| Python sidecar process supervision (spawn/health-check/restart/shutdown) | NOW |
| Capability-scoped native filesystem ops (open/save dialogs, export writes) | NOW |
| OS notifications | NOW |
| OS credential-store read/write for the TI API key | NOW |
| File hashing (SHA-256 of uploaded reports) | LATER |
| YARA scanning | LATER |
| PE metadata/malware artifact inspection | OPTIONAL / Research |
| Risk scoring, TI orchestration, investigation logic | **NEVER** |

The "NEVER" row is the load-bearing constraint: Rust is deliberately scoped to shell and
native-capability duties so that its inclusion is justified by concrete responsibilities, not
by resume-technology-count. See Master Plan §30.A/B for the explicit justification argument
and ADR-004 for the formal decision record.

Command flow (Master Plan §7):

```
Frontend request (invoke("export_report", {investigationId}))
   → Tauri command handler (Rust)
   → permission check against capabilities manifest for the calling window
   → native dialog for save location (user-in-the-loop, not a raw path from JS)
   → native filesystem write, scoped to the chosen path only
   → result returned to frontend / export.completed event emitted
```

Full capability manifest design: `docs/security/tauri-capability-model.md`.

## MIGRATION NOTES

Tauri foundation work is Phase 4E (Master Plan §26) — an empty shell that can launch the
Phase 4D Python sidecar and successfully invoke one command is the exit criterion; no UI, no
business logic, at that stage.

## UNKNOWN / REQUIRES VERIFICATION

None specific to this document beyond the general Phase 4B backend inventory — this layer has
no current-state source to verify since it doesn't exist yet.
