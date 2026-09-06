# SOC-IQ — PD-07: Settings — Partial Build Scope

## Entry checkpoint

`SOC-IQ-PD05-IOC-TI-TOPLEVEL-RETIREMENT-FINAL.zip`

## Decision

**PD-07 — Settings: PARTIAL BUILD (theme + export directory), plus a
later-approved VirusTotal credential write (ADR-008 Part 1B-3).**

This document originally recorded a decision to approve Theme and
Export Directory for a subsequent implementation part, with VirusTotal
API-key writing explicitly out of that approved scope and separately
deferred. Both the originally-approved scope and the later-approved
VirusTotal write have since been implemented — see "Status" below.

## Rationale / current-state (reconciled)

All three capabilities are now implemented in the modern UI:

| Capability | Current state | Evidence |
|---|---|---|
| Theme persistence | Implemented | `ThemeControl.tsx`, wired via `useSettingsFieldSave` to the `save_settings` command; backed by `SettingsService.update_theme` (`app/settings/service.py`) |
| Export directory persistence | Implemented | `ExportDirectoryControl.tsx`, wired via `useSettingsFieldSave` to the `save_settings` command; backed by `SettingsService.update_export_directory` (`app/settings/service.py`) |
| VirusTotal credential write | Implemented (Part 8, ADR-008 Part 1B-3) | `VirustotalControl.tsx` + `useVirustotalKeySave.ts`, calling `setVirustotalApiKey` → `keystore_set_secret`; see "Credential write path" below |

`frontend/src/pages/SettingsPage.tsx` now renders `ThemeControl`,
`ExportDirectoryControl`, and `VirustotalControl`, each wired to a real
save path; none of the three remaining disabled/read-only mock
controls this document originally described.

### Credential write path (reconciled)

Rust owns OS-keystore read *and* write (ADR-008):

```
keystore-core::store::RustSecretStore   get_secret / set_secret  IMPLEMENTED
src-tauri/src/keystore.rs               keystore_get_secret /
                                          keystore_set_secret /
                                          keystore_delete_secret /
                                          keystore_has_secret       registered as
                                                                      #[tauri::command]s
src-tauri/src/sidecar.rs                process-scoped env-var handoff of the
                                          VirusTotal key to the Python sidecar
                                          at startup                IMPLEMENTED
frontend/src/pages/settings/VirustotalControl.tsx +
useVirustotalKeySave.ts                 calls setVirustotalApiKey() →
                                          keystore_set_secret          IMPLEMENTED
```

Python no longer uses `keyring` at all, directly or otherwise: as of a
later migration (ADR-008 Part 1B-2), `app/secrets/store.py` implements
a read-only `RustKeystoreHandoffSecretStore` that only observes the
short-lived, process-scoped environment-variable handoff Rust places at
sidecar startup (`SOCIQ_SECRET_VIRUSTOTAL_API_KEY`); it cannot write or
delete a credential, and `keyring` is not in `requirements.txt` or
imported anywhere in `app/`. The Rust keystore and the Python read-only
handoff resolve to the same underlying OS credential-store entry;
Settings does not have two competing live credential-storage
implementations.

(MAX19A-F-01/F-06, resolved) Until this fix, `save_settings`'s DTO
(`app/application/dto.py::SaveSettingsRequest`) still structurally
accepted and routed a `virustotal_api_key` field through the full
handler → `SettingsService.update_api_key` → `SettingsRepository
.save_api_key` chain, reachable over the same production HTTP endpoint
Theme/Export Directory use, guaranteed to fail with
`SecretStoreReadOnlyError` against the real store above -- a reachable,
always-failing leftover, not a second *live* implementation. `Save
SettingsRequest.__post_init__` now rejects that field outright, before
the request ever reaches `SettingsService`, closing the leftover
surface without touching the legacy GUI's own direct, in-process call
to `SettingsService.update_api_key()`.

Lifecycle behavior (approved: Option A, application restart):

```
Credential saved successfully
→ OS keystore updated immediately (keystore_set_secret)
→ the currently running Python sidecar is not live-refreshed
→ VirustotalControl explicitly tells the user to restart SOC-IQ
→ the next application launch performs a fresh secret handoff
  (apply_secret_handoff(), src-tauri/src/sidecar.rs)
```

There is no live refresh and no sidecar restart-in-place; only a full
application restart picks up a newly-saved credential.

## Scope boundary

Theme and export-directory persistence in the modern Settings UI:
**implemented**, using the `save_settings` backend contract.

VirusTotal API-key writing in the modern Settings UI: **implemented**,
approved and built as ADR-008 Part 1B-3 in a later implementation part
than the one that recorded this decision.

## Status

**DECISION RECORDED — IMPLEMENTED.**

`SettingsPage.tsx` is wired to `save_settings` for theme and export
directory, and to `keystore_set_secret` (via `VirustotalControl`) for
the VirusTotal credential, in later implementation parts than the one
that produced this decision record.

## Next Action

None outstanding for this decision — theme, export directory, and the
VirusTotal credential write are all implemented in the modern UI. Any
further Settings work is a new product decision, not a continuation of
PD-07.
