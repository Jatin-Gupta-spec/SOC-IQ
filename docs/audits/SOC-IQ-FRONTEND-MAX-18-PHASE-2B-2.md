# SOC-IQ FRONTEND — MAX-18 Phase 2B-2: Original Defect Reproduction Audit

**Finding under audit:** MAX18-F-01 — Unsaved Settings edits are silently
discarded on navigation.

## 1. Baseline integrity

| Check | Result |
|---|---|
| Input archive | `SOC-IQ-FRONTEND-MAX-18-PHASE-2B-1-FULL-PROJECT.zip` |
| `unzip -t` | `No errors detected in compressed data` |
| SHA-256 (input) | `0b92196ea12859888b228cd32cb3edaafbf8d11fd80d73423d16b3bb53f4142a` |
| Entry count | 863 |
| Byte size | 2,733,549 bytes |
| Suspicious artifacts | None (`node_modules/`, `dist/`, `__pycache__/` absent) |
| `npm ci` | 159 packages, clean |

## 2. Methodology

Phase 2B-1 verified the implementation by direct source reading. This phase
goes further: it drives the **real, unmodified** application — the actual
`<App/>` component tree, real `HashRouter`, real `AppShell` (sidebar +
command palette + navigation-guard dialog exactly as production composes
them) — inside jsdom, and observes real DOM output, rather than reading
source or trusting any existing test's name or description.

A temporary, independently-authored reproduction harness
(`src/app/__phase2b2_repro__.live.test.tsx`) was added for this purpose
only. It:

- mocks only the two things a browserless jsdom run cannot provide (the
  `useSettings` data-fetch hook and the backend `runCommand`/
  `setVirustotalApiKey` calls — the same minimal seam every existing
  `.live.test.tsx` in this project already uses), and
- otherwise renders the real production component tree and interacts with
  it via real DOM events (`dispatchEvent` on real `<select>`/`<input>`/
  `<a>`/`<button>` elements located by their real `id`s and text content).

After capturing results, the harness file was **deleted** and the full
suite (`npx vitest run`, `npx tsc --noEmit`, `npm run build`) was re-run
against the now-restored, unmodified source to confirm zero residual change
— see §7. No production source file was edited, added to, or removed at
any point.

## 3. Required reproduction matrix — results

All ten scenarios below were executed against the real app and passed.
Evidence is the harness's own `console.log` output, captured verbatim from
the actual test run (values are booleans/counts only — no secret material
is logged; see §4 for the VirusTotal-specific check).

### Theme
```
[2B-2][Theme] navigation interrupted: true
[2B-2][Theme] Stay kept user on Settings: true
[2B-2][Theme] Leave navigated to Dashboard: true
```
Edited the Theme `<select>`, clicked the sidebar "Dashboard" link. The
`role="alertdialog"` confirmation appeared and the URL hash remained
`#/settings`. Clicking "Stay" dismissed the dialog and left the hash
unchanged. Re-attempting navigation and clicking "Leave" navigated the real
`HashRouter` to `#/dashboard`.

### Export Directory
```
[2B-2][ExportDir] navigation interrupted: true
[2B-2][ExportDir] Leave navigated to Dashboard: true
```
Identical workflow against the `#settings-export-directory` input; Stay
verified to keep `window.location.hash` on Settings before the Leave
sub-case was run.

### VirusTotal API key
```
[2B-2][VirusTotal] navigation interrupted: true | key exposed in dialog: false
[2B-2][VirusTotal] Leave navigated to Dashboard: true
```
Identical workflow against the `#settings-virustotal-api-key` input, using
a synthetic placeholder string as the edit-buffer value. The harness
asserted directly (`expect(...).toBe(false)`, backed by the boolean logged
above) that the confirmation dialog's own `textContent` does not contain
that placeholder value. **The actual edit-buffer value is a synthetic,
harness-local placeholder and is never printed by this harness or present
in this document.**

### Multi-field
```
[2B-2][multi-field] dialog count after 3 dirty controls: 1
```
All three controls were dirtied in the same render before attempting
navigation. Exactly one `role="alertdialog"` element was present in the
DOM — not zero, not three — confirming the aggregate collapses all three
signals into one coherent protection instance.

### Save then navigate (per control)
```
[2B-2][save][Theme] navigated without confirmation after save: true
[2B-2][save][ExportDir] navigated without confirmation after save: true
[2B-2][save][VirusTotal] navigated without confirmation after save: true
```
For each control: edited, clicked its real Save button, awaited the
(mocked, resolved) backend call, then attempted navigation. In all three
cases the app navigated straight to `#/dashboard` with no confirmation
dialog appearing at any point.

### Failed save then navigate (per control)
```
[2B-2][fail-save][Theme] protection remained active after forced failure: true
[2B-2][fail-save][ExportDir] protection remained active after forced failure: true
[2B-2][fail-save][VirusTotal] protection remained active after forced failure: true
```
For each control: edited, forced the backend call
(`runCommand`/`setVirustotalApiKey`) to reject exactly once via
`mockRejectedValueOnce`, clicked Save, awaited the rejection, then
attempted navigation. In all three cases the confirmation dialog appeared
— the forced failure did not clear protection.

## 4. Secret-handling check

No VirusTotal key value — real or synthetic — appears anywhere in this
document, in the harness's console output, or in any file produced by this
audit. The one explicit content check performed (§3, VirusTotal case)
confirmed programmatically that the confirmation dialog's rendered text
does not include the edit-buffer value, consistent with the dialog's fixed,
generic wording found in the Phase 2B-1 source audit.

## 5. Interpretation

Every expected outcome in the task brief's reproduction matrix was observed
against the real, running application, not inferred from source reading or
from an existing test's assertions:

- Navigation is interrupted while any control is dirty (Theme, Export
  Directory, VirusTotal, and all three together).
- Stay leaves the user on Settings with the confirmation dismissed.
- Leave completes the navigation to the originally-attempted destination.
- A successful save clears protection for that control.
- A failed save (forced deterministically via a rejected mock, per each
  control's own save path) leaves protection active.
- The VirusTotal key value is never exposed in the confirmation UI.

## 6. Deviations / limitations

- "Rapid"/"repeated navigation" and native-`beforeunload` dialog behavior
  were not re-driven in this phase's harness (they were the specific
  subject of Phase 2A's own dedicated tests and Phase 2B-1's source audit,
  §"CHECK" already covers the underlying listener lifecycle); this phase's
  scope, per its own required reproduction matrix, was the per-control and
  multi-field confirm/save/fail workflows, which are fully covered above.
  `popstate`/browser back-forward interception remains out of scope for
  MAX18-F-01 as a whole, per the guard store's own documented boundary
  (Phase 2A-3, reconfirmed in Phase 2B-1 §4).
- This phase's harness necessarily mocks the backend IPC boundary
  (`runCommand`, `setVirustotalApiKey`) and the settings data-fetch hook,
  since no real Tauri/Python backend is available in this sandboxed jsdom
  environment — identical to the mocking boundary every pre-existing
  `.live.test.tsx` in this project already uses, not a weaker boundary
  invented for this audit.

## 7. Post-harness integrity check

After deleting the temporary reproduction harness, the full verification
suite was re-run against the restored, unmodified source:

```
npx vitest run   → 97 test files passed (97), 1368 tests passed (1368)
npx tsc --noEmit → 0 errors
npm run build    → clean
```

Identical to Phase 2B-1's own results — confirming the harness left no
residue and no production file was altered.

## 8. Output artifact

| Item | Value |
|---|---|
| Archive | `SOC-IQ-FRONTEND-MAX-18-PHASE-2B-2-FULL-PROJECT.zip` |
| Contents | Complete project, plus this document; no other change vs. the Phase 2B-1 input |
| Source modifications | None (temporary harness added and removed within this session only; never present in the packaged output) |

(SHA-256, entry count, and byte size for this specific output archive are
recorded in the delivery message accompanying this document, computed
after final packaging and independently re-verified by fresh extraction —
per this checkpoint's own "no source modifications merely to create the
ZIP" instruction, this document does not pre-declare a hash for a file that
does not yet exist at the time this paragraph is written.)

## 9. Verdict

**PASS — READY FOR PHASE 2B-3**

All ten required reproduction scenarios (Theme, Export Directory,
VirusTotal — each individually — plus multi-field, three save-success
cases, and three forced-save-failure cases) were independently reproduced
against the real, unmodified application and behaved exactly as specified.
No secret material was exposed or logged. No blocker was found.
