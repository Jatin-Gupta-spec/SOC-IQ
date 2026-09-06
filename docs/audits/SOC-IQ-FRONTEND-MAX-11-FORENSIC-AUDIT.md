# SOC-IQ Frontend MAX-11 — Phase 1

## Forensic Audit → Highest-Leverage Direction

---

## 1. Executive Summary

This audit found **zero P0 findings and zero P1 findings** in the frontend
codebase itself. It confirms one **new P2 finding, MAX11-F-01**: the Export
Directory setting (`ExportDirectoryControl.tsx`) is still a hand-typed text
field with no native folder picker, an explicitly self-documented gap
("no filesystem-picker architecture is introduced ... has no frontend
equivalent yet") that has stood since the control was first implemented and
was never raised as a candidate direction in MAX-1 through MAX-10. It is
the one concrete, low-risk, analyst-facing gap sitting directly on the
export workflow the prior two checkpoints (MAX-10 Phase 2A, and this
baseline's MAX-10 Export & Filesystem Security Remediation) just finished
hardening from the security side — the picker side of that same workflow
was never closed to match.

Two carried-forward items are reconfirmed, unchanged:

- `MAX9-F-01` (P3): `package.json`'s `description` field still says
  "Analyze, Risk, and Settings remain mock/placeholder pending further
  implementation" — false as of MAX-7/MAX-9 (Analyze is real; Risk was
  retired from navigation entirely per PD-05; Settings has two real
  fields). Still open, still P3 (metadata only, zero runtime effect).
- The MAX-10 audit's standing observation that no MAX phase since MAX-3
  has ever rendered this application in an actual browser or Tauri
  runtime remains true. Every accessibility/responsive/motion/visual
  conclusion in this and prior audits is static/source-level unless
  explicitly marked otherwise.

**Selected MAX-11 direction:** add a native "Browse…" folder picker to
`ExportDirectoryControl`, reusing the exact `tauri-plugin-dialog` pattern
`nativeFileSelection.ts` already established for Analyze, with **no new
Tauri capability grant** (§7, §12).

**Verdict: `MAX-11 AUDIT COMPLETE WITH CONDITIONS`.**

---

## 2. Authoritative Baseline

- Started from `SOC-IQ-FRONTEND-MAX-10-EXPORT-SECURITY-REMEDIATION-FULL.zip`.
- ZIP integrity verified (`unzip -t`: no errors detected). 732 files, no
  nested checkpoint ZIPs.
- SHA-256 of the input baseline archive:
  `482bffffcfff6d6f6838e8cf21a0b87cfff1cc5cf50b0b2add777d7a2c3d321f`.
- Confirmed `docs/audits/SOC-IQ-FRONTEND-MAX-10-EXPORT-SECURITY-REMEDIATION-CLOSURE.md`
  is present and states explicitly: *"No restart, no redesign, no MAX-11
  work performed."* — verifying the premise of this phase's task brief
  directly against the archive rather than assuming it.
- Also read: `docs/audits/SOC-IQ-FRONTEND-MAX-10-FORENSIC-AUDIT.md`,
  `SOC-IQ-FRONTEND-MAX-10-PHASE-2A-HIGHEST-LEVERAGE-CLOSURE.md`,
  `SOC-IQ-FRONTEND-MAX-10-PHASE-2B-INTEGRATION-CLOSURE.md`,
  `docs/security/filesystem-security-model.md`,
  `docs/security/tauri-capability-model.md`,
  `src-tauri/capabilities/default.json`.
- **Git provenance unavailable; filesystem/static verification performed.**
  No `.git` directory found — unchanged since MAX-3.

MAX-10 (all phases, including the export-security remediation) is confirmed
closed on defensible terms. Proceeding.

---

## 3. Audit Method

Fresh `npm ci` + `npx tsc --noEmit` + `npm test -- --run` + `npm run build`
baseline established before any inspection (§21). Read the full frontend
source tree directly (`frontend/src`, 202 built modules pre-change);
did not rely on prior audits' conclusions without re-checking the current
source for areas most likely to have drifted (export/filesystem workflow,
navigation, DataTable consumers, test-file coverage). Areas with no
plausible drift since their last dedicated MAX pass (motion, design tokens,
color/typography) were not re-walked file-by-file; their MAX-4/MAX-6
conclusions are treated as still authoritative absent evidence otherwise,
consistent with MAX-10's own method note.

Specific checks performed this phase:
- Full `find`/`grep` sweep for `TODO`/`FIXME`/`mock`/`placeholder` across
  `pages/`.
- Confirmed current top-level navigation (`Dashboard`, `Analyze`,
  `Investigations`, `Reports`, `Settings`) against `navigationModel.ts`
  and its own tests (`/risk`, `/ioc-explorer`, `/threat-intel` confirmed
  absent).
- Enumerated every `.tsx` component without a co-located `.test.tsx`/
  `.test.ts` file (§6) to distinguish the project's established
  integration-test convention from genuine coverage gaps.
- Traced every real `DataTable` consumer (`InvestigationsPage`,
  `ReportsPage`, `InvestigationThreatIntel`, `InvestigationIocWorkspace`,
  `DashboardRecentInvestigations`) to check MAX10-F-01's sort feature's
  consistency across consumers (§8).
- Read every `save()`/`open()` call site for `@tauri-apps/plugin-dialog`
  against `src-tauri/capabilities/default.json`'s actual granted
  permissions (§7) — the same class of gap MAX-10's own audit
  (`MAX-AUDIT-01`) found and fixed, checked here for any sibling instance
  it might have missed.
- Read `ExportDirectoryControl.tsx`, `useSettingsFieldSave.ts`,
  `SettingsPage.tsx`, and their test files end to end.
- Verified, via official `tauri-plugin-dialog` source (`docs.rs`, v2.3.3
  and v2.7.0), that `open()`'s `directory` field is part of a single
  Rust command (`commands::open`) registered under one permission
  (`dialog:allow-open`) — not a separate command/permission from file
  selection — since this phase's selected direction's capability claim
  (§7) depends on that fact and no Rust toolchain is available in this
  sandbox to compile-verify it directly (§21).

---

## 4. Repository / Architecture Findings

No architectural regressions found. Structure is unchanged from MAX-10:
one router (`app/router.tsx`), one typed command client
(`shared/api/client.ts`), one sidecar-status/event model
(`shared/sidecar/`), page-scoped view-model/hook pairs, shared primitives
in `pages/components/`. No duplicate state machines, no direct
DB/provider access from the frontend, no handler-bypass. **No finding.**

---

## 5. UX / Analyst Efficiency Findings

**MAX11-F-01 (P2).** `ExportDirectoryControl.tsx` (Settings page) is a
plain `<input type="text">` with no native folder picker. Its own doc
comment says so: *"no filesystem-picker architecture is introduced (the
legacy Qt page's `QFileDialog` browse button has no frontend equivalent
yet)."* An analyst who wants exports to go somewhere other than the
persisted default has to know, or go find, the exact absolute path and
type it correctly by hand — no OS-native browsing, no confirmation the
folder exists, no protection against typos. This is the same class of gap
`nativeFileSelection.ts` (Phase 4I Remediation, Blocker A) already closed
for file *selection* on the Analyze page; the folder-*selection* side of
the equivalent workflow — where exports actually land — was never closed
to match. It sits directly downstream of the export write-path
MAX-10 Phase 2A and this baseline's remediation just finished hardening,
making it the most exposed remaining rough edge on that specific,
recently-scrutinized workflow. Severity: P2 (real, bounded, evidence-backed
friction on a primary workflow; not a blocker, not cosmetic).

All other list/search/filter/export UX (Investigations, Reports,
Investigation Workspace tabs) matches or exceeds MAX-7/MAX-9's documented
state — search+filter present on both list pages (`MAX7-F-03`), column
sort present on Investigations (`MAX10-F-01`), ARIA tab semantics present
on the Investigation Workspace (`Frontend MAX-1`). **No new finding.**

---

## 6. Test Coverage / Code Quality Findings

Enumerated every `.tsx` without a same-name `.test.tsx`/`.test.ts`. The
~30 files found (page shells, `Card`/`PageHeader`/`SkeletonBlock`/
`DataTable`, all seven Dashboard subcomponents, `AnalyzePage`,
`DashboardPage`) are, on inspection, consistently covered instead by a
co-located integration-style suite (`pages.test.tsx`, `dashboard.test.tsx`,
`InvestigationsPage.test.tsx`, etc.) — an established, deliberate project
convention (visible as far back as MAX-6/MAX-7's own test files), not an
accidental coverage gap. Confirmed by spot-checking `DataTable.tsx`
(no direct test file, but its `MAX10-F-01` sort behavior is exercised
through `InvestigationsPage.test.tsx`) and `DashboardPage.tsx` (covered by
`dashboard/dashboard.test.tsx`). **No finding** — recorded as INFO only,
since a future MAX cycle re-reading this repo cold could otherwise
mistake the pattern for a gap.

No duplicated/drifted component families found (Button/Card/DataTable/
StatusBadge consolidation from MAX-6 holds). No dead files found under
`frontend/src` this pass.

---

## 7. Security / Reliability Findings

Re-checked every `@tauri-apps/plugin-dialog` call site
(`nativeFileSelection.ts`: `open()`; `investigationsCsvExportPath.ts`,
`reportExportPath.ts`: `save()`) against
`src-tauri/capabilities/default.json`'s current grants
(`dialog:allow-open`, `dialog:allow-save`, `fs:allow-read-file`,
`core:default`). All three call sites are covered by an existing grant —
`MAX-AUDIT-01` (this baseline's own fix) closed the one real gap in this
area, and no sibling instance was missed. **No finding.**

For the selected MAX11-F-01 direction specifically: confirmed via
`tauri-plugin-dialog`'s published Rust source (docs.rs, `commands.rs`)
that `open()`'s `directory: bool` option is a field on a single
`OpenDialogOptions` struct handled by one command
(`commands::open`, registered once in `lib.rs`'s
`generate_handler![commands::open, commands::save, commands::message]`),
gated by one permission set (`dialog:allow-open`) regardless of whether
`directory` is `true` or `false`. This means the already-granted
`dialog:allow-open` permission covers a directory-mode `open()` call
without any manifest change — implementing MAX11-F-01 requires **zero**
new capability grants, keeping this phase's security surface identical to
MAX-10's. This is `STATIC VERIFIED` against the plugin's own published
source, not `RUNTIME VERIFIED` — no Rust toolchain is available in this
sandbox to compile and exercise the manifest directly (§21), consistent
with every prior Tauri-touching session in this project.

No other filesystem/export/security boundary finding. `filesystem-security-model.md`'s
documented trust boundary (frontend never writes bytes; only a
native-dialog-derived path crosses the IPC boundary; the Python sidecar
performs the write) is unaffected — MAX11-F-01's picker only ever returns
a path string to the frontend, exactly like `nativeFileSelection.ts`'s
existing `open()` call.

---

## 8. Consistency / Minor Findings (Recorded, Not Selected)

- **DataTable sort is Investigations-only.** `ReportsPage`'s `DataTable`
  (columns: Investigation, Status, Generated, size/format-adjacent
  fields) has no `sortable` columns, unlike Investigations
  (`MAX10-F-01`). A real, evidence-backed consistency gap — but lower
  leverage than MAX11-F-01 this cycle: it duplicates a pattern already
  proven in MAX-10 rather than closing a distinct, previously-unaddressed
  gap, and Reports' own search+filter (`MAX7-F-03`) already covers its
  primary discovery need. Recorded as a standing P3 candidate for a
  future MAX cycle, not selected.
- **`MAX9-F-01` (P3, carried forward, unchanged):** `package.json`'s
  `description` field is stale (see §1). Trivial to fix but was not
  bundled into this phase's implementation per the hard-scope rule (§9
  of the task brief) — it is unrelated to the selected direction and
  touches no analyst-facing surface.

---

## 9. Finding Severity Matrix

| ID | Severity | Area | Status |
|---|---|---|---|
| MAX11-F-01 | P2 | Settings / Export workflow | **New — selected for Phase 2A** |
| (Reports DataTable sort) | P3 | Reports list | New — recorded, not selected |
| MAX9-F-01 | P3 | `package.json` metadata | Carried forward, open |
| — | — | Architecture, security boundaries, accessibility, motion, design tokens, test-convention | No new finding this cycle |

No P0 or P1 finding exists anywhere in this audit.

---

## 10. Highest-Leverage Candidate Ranking

1. **MAX11-F-01 — Export Directory native browse picker.** User impact:
   real, on every analyst who changes their export location. Product
   impact: closes the one remaining "no frontend equivalent" gap on the
   export workflow. Architectural leverage: reuses an existing, proven
   pattern (`nativeFileSelection.ts`) with zero new capability surface.
   Frequency of exposure: Settings is a low-traffic page, but the gap
   affects 100% of analysts who ever need to change the default.
   Severity: P2. Improvement potential: turns a "type it by hand and hope"
   field into a real native picker. Consistency: directly matches
   Analyze's existing "Browse for Analysis" precedent. Implementation
   risk: low (additive-only, no backend/contract change, no new
   permission).
2. **Reports DataTable sort.** Real, but lower leverage this cycle — see
   §8. Would be reasonable as a MAX-12 candidate.
3. **`package.json` description fix.** Trivial, but zero analyst-facing
   effect; a one-line docs fix, not a MAX-cycle-worthy direction on its
   own.

**Selected: MAX11-F-01.** Rejected alternatives: (2) is real but
duplicates a just-proven pattern rather than closing a distinct gap; (3)
has no functional impact.

Expected product improvement: analysts can point exports at a real,
OS-confirmed folder via a native picker instead of hand-typing an absolute
path, matching the trust/UX model already established for Analyze's file
selection.

Files/components likely affected: `frontend/src/pages/settings/
ExportDirectoryControl.tsx` (add the control), a new
`exportDirectoryBrowse.ts` module (the picker logic, mirroring
`nativeFileSelection.ts`), and their tests. No backend, no Tauri
capability manifest, no other page.

Risks: none identified beyond the standard "no Rust toolchain in this
sandbox" verification gap already present for every Tauri-touching change
in this project (§7, §21).

Non-goals: no directory-picker architecture for any other setting or
page; no change to `save_settings`'s contract (still a plain string); no
validation that the picked directory is writable (matches the existing
text-field's behavior — errors, if any, surface at save time exactly as
they do today).

---

## 11. Verification Requirements For Phase 2A

- `npx tsc --noEmit` — 0 errors.
- `npm test -- --run` — 0 regressions against this phase's 1187-test
  baseline (§21); new tests for the added module/control.
- `npm run build` — clean production build.
- Diff-audit against this baseline's untouched extraction — confirm only
  the direction's own files changed.
- Explicit note that `dialog:allow-open` capability coverage for
  directory mode is `STATIC VERIFIED` (§7), not `RUNTIME VERIFIED` — no
  Rust toolchain available to compile `src-tauri` in this sandbox.

**AUDIT RESULT ≠ IMPLEMENTATION RESULT.** This document records the audit
and selected direction only. Implementation, its own verification, and
the post-implementation re-audit are recorded separately in
`docs/audits/SOC-IQ-FRONTEND-MAX-11-PHASE-2A-HIGHEST-LEVERAGE-CLOSURE.md`.
