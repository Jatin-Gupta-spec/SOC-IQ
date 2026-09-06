# Tauri Capability Model

**Status:** Implemented (Phase 4O Security, Part 2A — capability-manifest snapshot).
**Related:** Master Plan §7, ADR-003, ADR-010, `docs/architecture/04-tauri-rust-architecture.md`.

## CURRENT STATE

A Tauri capability manifest exists at `src-tauri/capabilities/default.json` and is
wired into `src-tauri/tauri.conf.json` (`app.security.capabilities`). As of this
checkpoint (MAX-10 Export Security Remediation, MAX-AUDIT-01) it grants exactly
four permissions: `core:default`, `dialog:allow-open`, `dialog:allow-save`, and
`fs:allow-read-file` — see that file's own `description` field for the specific,
per-permission rationale (native open/save file pickers + reading only the bytes
of a path the open picker returns; no `dialog:default`/`fs:default`, no
`fs:allow-write*`, no static `fs` scope, no shell or HTTP plugin capability).
`dialog:allow-save` backs the native save dialog used by
`frontend/src/pages/reports/reportExportPath.ts` and
`frontend/src/pages/investigations/investigationsCsvExportPath.ts` — it lets the
frontend obtain a user-chosen destination path, not write to it; the write itself
happens in the Python sidecar behind the `export_report`/
`export_investigations_csv` commands (see `docs/security/
filesystem-security-model.md` for that boundary).

This manifest is protected by a permanent regression test,
`tests/test_architecture_capability_snapshot.py`, which canonicalizes the
manifest and `tauri.conf.json`'s security-relevant fields
(`tests/architecture/capability_manifest_guard.py`) and compares that
canonical form against a committed baseline,
`tests/fixtures/capability_manifest.snapshot.json`. A future change that adds a
capability, widens a scope, or adds a shell/process permission will fail this
test and must update the committed snapshot deliberately (via
`tests/architecture/update_capability_snapshot.py --write`) as part of a
reviewed change, rather than passing silently. Harmless changes (permission
reordering, JSON formatting, `description` edits) do not trip it.

## ORIGINAL DESIGN INTENT (historical; superseded in part by CURRENT STATE above)

**Command flow:**

```
Frontend request (invoke("export_report", {investigationId}))
   → Tauri command handler (Rust)
   → permission check against capabilities manifest for the calling window
   → native dialog for save location (user-in-the-loop, not a raw path from JS)
   → native filesystem write, scoped to the chosen path only
   → result returned to frontend / export.completed event emitted
```

**Illustrative least-privilege capabilities:**

| Capability | Granted? | Notes |
|---|---|---|
| `dialog:allow-open`, `dialog:allow-save` | Yes, scoped | User-in-the-loop for any file selection |
| `fs:allow-write` | Not granted broadly | Writes only happen inside a Rust command handler after a user-driven dialog; no generic "write this path" command is exposed to JS |
| `notification:allow-notify` | Yes | |
| `shell:*` | **Denied entirely, no exceptions** | Matches the existing Python-side no-`shell=True` discipline (`threat-model.md`) as a cross-language rule |
| `http:*` from the frontend | **Denied** | All network access is mediated by the Python sidecar |

Note: `dialog:allow-save` (table above) is now granted, as described in CURRENT
STATE. `notification:allow-notify` remains ungranted — no notification feature is
wired today. The original design's "native filesystem write, scoped to the chosen
path only" step, performed inside a Rust command handler, was **not** built this
way; the actual write happens in the Python sidecar, per
`docs/security/filesystem-security-model.md`'s CURRENT STATE and "WHY NOT THE
ORIGINAL RUST-WRITE DESIGN" sections.

## MIGRATION NOTES

The capability-manifest snapshot test described above was added in Phase 4O
Security, Part 2A, so a future change that widens permissions is visible in
code review rather than silent (Master Plan Top-10 security risks, #1: "Tauri
capability manifest over-scoped 'to save time' during 4E/4G").

## UNKNOWN / REQUIRES VERIFICATION

None outstanding for the capability-manifest snapshot covered here. The
export/save-dialog capabilities in the target-state table above remain
unimplemented and untested until that feature is built.
