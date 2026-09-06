# Filesystem Security Model

**Status:** Implemented (MAX-10 Export Security Remediation, MAX-AUDIT-02).
**Related:** ADR-010, `tauri-capability-model.md`, `trust-boundary-model.md`.

## HISTORY

The original Phase 4A "TARGET STATE" for this document proposed that export path
resolution and the final filesystem write both happen inside the Rust/Tauri layer,
with the Python sidecar never touching a frontend-supplied path. That target was
never built: `export_report` and `export_investigations_csv` are Python-sidecar
commands (`app/application/handlers.py`), and the sidecar itself performs the write
(`app/reporting/*_exporter.py`, `app/services/investigation_csv_export.py`). This
revision replaces the aspirational target with the boundary that is actually
implemented and tested, per MAX-10's Outcome B: document the deliberate existing
boundary rather than fabricate a stronger one.

## CURRENT STATE (implemented and tested)

```text
React
  -> Tauri save() dialog (dialog:allow-save; frontend/src/pages/reports/reportExportPath.ts,
     frontend/src/pages/investigations/investigationsCsvExportPath.ts)
  -> analyst-chosen absolute destination
  -> POST /commands/{export_report,export_investigations_csv} (Python sidecar, loopback HTTP)
  -> app/application/dto.py: absolute-path validation (rejects any relative/bare path)
  -> app/reporting/*_exporter.py or app/services/investigation_csv_export.py: filesystem write
```

**Destination origin.** The frontend never constructs or accepts a raw path string
from anywhere but the native save dialog (`@tauri-apps/plugin-dialog`'s `save()`).
`dialog:allow-save` (`src-tauri/capabilities/default.json`) is the only capability
that lets the frontend obtain a destination path at all; no `fs:allow-write*`
capability is granted, so Tauri's own ACL gives JavaScript no way to write a file
directly.

**Trust boundary being documented.** The sidecar's HTTP command endpoint has no way
to cryptographically prove that a given `output_path` value actually came from the
save dialog rather than from a request crafted by anything else able to reach that
loopback endpoint. That is a real, acknowledged gap relative to the original
aspirational design, not a hidden one — see `docs/security/ipc-security-model.md`
for the loopback-binding and CSP controls that scope who can reach the sidecar at
all. Given that gap, the actual guarantee this layer provides is narrower and is
enforced at the DTO boundary:

- `output_path` must be a non-empty string.
- `output_path` must be an absolute path (`Path(output_path).is_absolute()`) — a
  relative or bare filename is rejected outright, since a legitimate save-dialog
  result is never one of those shapes
  (`app/application/dto.py::ExportReportRequest.__post_init__`,
  `ExportInvestigationsCsvRequest.__post_init__`).
- The command writes to exactly that one destination and nothing else: no directory
  listing, no arbitrary read, no delete/rename. The exporters only ever call
  `output_path.parent.mkdir(parents=True, exist_ok=True)` then write `output_path`
  itself — see `tests/test_export_path_traversal_adversarial.py` and
  `tests/test_bulk_csv_export_path_traversal_adversarial.py` for the adversarial
  proof (traversal payloads rejected with no filesystem trace; absolute paths,
  including through symlinks, resolve and write exactly where expected; an existing
  sibling file is left untouched).

This is deliberately **not** a claim that the native dialog cryptographically
authenticates the write — it does not. It is a claim that (1) the only UI path that
produces an absolute, plausible destination is the dialog, and (2) even a
maliciously-crafted request to the same local endpoint is confined to writing
exactly the one path it names, with no traversal, no directory confinement to
bypass, and no broader filesystem capability to exploit.

## WHY NOT THE ORIGINAL RUST-WRITE DESIGN

Moving the write itself into the Rust/Tauri layer would require a new
`#[tauri::command]` that either duplicates the four report exporters'
format-specific logic (`app/reporting/{html,json,markdown,pdf}_exporter.py`) and the
CSV exporter (`app/services/investigation_csv_export.py`) in Rust, or has Python
write to a temp location and Rust perform a second, redundant copy — both are a new
architecture layer, not a minimal fix, and were out of scope for this remediation
(MAX-10 Rule B: preserve existing architecture, no architecture rewrite). If a
future phase deliberately restores the stronger Rust-write boundary, it should
update this document at that time; the current implementation is Outcome B as
defined in that phase's remediation spec, not an interim step already headed there.

## MIGRATION NOTES

This model directly informs `tests/test_export_path_traversal_adversarial.py` and
`tests/test_bulk_csv_export_path_traversal_adversarial.py`, which should be extended
first if this boundary's guarantees ever change.

## UNKNOWN / REQUIRES VERIFICATION

None outstanding for the boundary as implemented and tested above. Whether a future
phase restores Rust-mediated writes is a deliberate architectural decision for that
phase, not an unresolved item here.
