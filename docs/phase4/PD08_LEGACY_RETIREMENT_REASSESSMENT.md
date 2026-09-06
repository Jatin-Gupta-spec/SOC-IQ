# PD-08-P6 — Legacy GUI Retirement Reassessment & Safe Retirement Decision Gate

**Status:** Decision gate only. No legacy files deleted in this part.
**Input checkpoint:** `SOC-IQ-PD08-P5-4-BULK-CSV-FINAL-CLOSURE-FULL.zip`
**Output checkpoint:** `SOC-IQ-PD08-P6-LEGACY-RETIREMENT-REASSESSMENT-FULL.zip`

---

## 0. Checkpoint Forensics

| Property | Value |
|---|---|
| Input archive SHA-256 | `a9f2e7e520af41f9733e537a8f4af8aef8b56cdadc66bf93d003d5597ca625e` |
| Input archive size | 2,288,000 bytes |
| Files in archive | 764 |
| Extraction | Succeeded, no errors |
| Git repository | **Absent** — no `.git` directory; git-state history could not be inspected |
| Files after extraction (excl. archive itself) | 678 |

**Finding — documentation gap (not a blocking defect, but material to this audit):**
The archive name and PD-08-P6 task both refer to this checkpoint as the
"P5.4 bulk-CSV final closure." However, `docs/phase4/` contains **only**
`PD08_P5_1_BULK_CSV_EXPORT_BACKEND_CONTRACT.md` — there are no PD-08-P2,
P3, P4, P5.2, P5.3, or P5.4 documents in the checkpoint, and no prior
"PASS" report for this checkpoint was present to verify. Per this task's
own instruction ("do not assume the checkpoint is valid because the
previous report says PASS"), I did not take the filename's closure claim
on faith. Instead, every conclusion below is based on independent
source-level inspection and live test execution against the code actually
present in the archive, not on any absent closure report. The frontend CSV
export code (§5.C) is present and fully wired despite P5.1's own doc
stating the frontend button was deferred to "a later P5 part" — that later
part's documentation simply never made it into this checkpoint, even
though its code did.

---

## 1. Re-opened Prior Decision (Phase 4O Part 4)

`docs/phase4/PHASE4O_PART4_LEGACY_GUI_RETIREMENT.md` explicitly deferred
final disposition of three files pending exactly the product question
PD-08 exists to answer:

> "...is bulk CSV export of investigation history still a required
> feature. Until at least one of these gets a 'no, drop it' answer,
> `risk_explanation_widget.py`, the significance half of
> `ioc_summary_widget.py`, and `csv_exporter.py`/`history_page.py` all
> stay, along with everything `investigation_workspace.py` pulls in
> transitively — which is most of the remaining `app/gui` file count."

That same document also establishes a load-bearing fact this reassessment
confirms still holds: `investigation_workspace.py` transitively imports a
cluster of **13 other retained widgets** plus the `design/tokens` and
`design/theme` (partial) systems. None of these are independent files —
they are one entangled unit.

No part of the prior retirement decision is invalidated here; this part
adds evidence, it does not overrule it.

---

## 2. Behavioral Parity Matrix

| Behavior | Legacy source | Modern replacement (full chain) | Parity |
|---|---|---|---|
| Risk explanation | `app/gui/widgets/risk_explanation_widget.py` | `GetInvestigationRiskExplanationCommandHandler` (`app/application/handlers.py`) → `app/services/risk_explanation_service.py` / `risk_explanation_models.py` → `InvestigationOverviewRisk.tsx` (+ tests) | **FULL** |
| Risk significance | Significance half of `app/gui/widgets/ioc_summary_widget.py`, backed by `app/services/ioc_significance.py` | Same `app/services/ioc_significance.py` (see §4 — this is a **shared**, not legacy-only, module) surfaced through `app/application/handlers.py` → `InvestigationIocWorkspace.tsx` (significance badge/tone mapping, with explicit comment cross-referencing the PD-08-P3 `ioc_type_significance()` vocabulary) | **FULL** |
| Bulk CSV export | `app/gui/utils/csv_exporter.py` via `app/gui/pages/history_page.py` | `ExportInvestigationsCsvCommandHandler` (`app/application/handlers.py`) → `app/services/investigation_csv_export.py` → `useInvestigationsCsvExport.ts` / `InvestigationsCsvExportAction.tsx` (+ path/unit/component tests) | **FULL** |

**Important correction to the location assumed in this task's brief:**
§B of the task instructions expects the legacy significance utility at
`app/gui/utils/ioc_significance.py`. It is not there. The actual file is
`app/services/ioc_significance.py` — it was never GUI-only code. This
matters directly for §4.

For CSV, parity was verified against the exact legacy contract recorded in
`docs/phase4/PD08_P5_1_BULK_CSV_EXPORT_BACKEND_CONTRACT.md` (column order,
header casing, `utf-8` encoding, RFC 4180 quoting, `Analyzed At` format,
and the legacy's confirmed `None`-timestamp bug) — the modern
`investigation_csv_export.py` module's own docstrings cite that same
legacy module by dotted path purely as behavioral-contract documentation;
grep confirmed these are comments only, **not live imports** (see §5.C).

---

## 3. Full Repository Consumer Audit

| Candidate file | Real (non-comment) consumers | Classification |
|---|---|---|
| `app/gui/utils/csv_exporter.py` | `app/gui/pages/history_page.py` (production import), `tests/test_bulk_csv_export.py`, `tests/test_export_path_traversal_adversarial.py` | **Legacy-only, but not isolated** — still the live export engine for the still-retained `history_page.py` |
| `app/gui/widgets/risk_explanation_widget.py` | `app/gui/pages/investigation_workspace.py`, `tests/gui/test_investigation_workspace_risk_explanation.py`, `tests/gui/test_phase3e_acceptance.py` | **Legacy-only, but not isolated** — one node in the 13-widget `investigation_workspace.py` cluster |
| `app/services/ioc_significance.py` | Legacy: `app/gui/widgets/ioc_summary_widget.py`, `app/gui/services/investigation_correlation_context.py`. **Modern/production**: `app/services/ioc_detail_context.py`, `app/services/correlation_service.py`, `app/services/risk_explanation_service.py`, `app/services/risk_explanation_models.py`, `app/application/handlers.py`. Tests: `test_application_layer.py`, `test_ioc_detail_context.py`, `tests/gui/test_ioc_summary_risk_relevance.py` | **Shared dependency (category 5)** — actively required by modern production code, independent of any legacy GUI question |
| `app/gui/pages/history_page.py` | `app/application/dto.py` (comment only), `tests/test_export_path_traversal_adversarial.py` | Legacy-only, entangled with `csv_exporter.py` |

**Architecture boundary check (§9 of the task):** confirmed clean —
`grep` for `from app.gui` / `import app.gui` across `app/application/`,
`app/api/`, and `frontend/src/` returned **zero** matches. `cargo`/`rustc`
were not present in this execution environment (see §7), so `src-tauri`
could not be compiled, but a text search of `src-tauri/src` for the three
candidate file names also returned zero matches. The one packaging
reference to `app/gui` (`packaging/pyinstaller/socq_backend.spec` line 31)
is a comment noting the PySide6 shell is *not* bundled — not a live
reference. No forbidden modern → legacy dependency exists in either
direction that would matter for this reassessment, **except** the one
already flagged in §4: `ioc_significance.py` is a legacy → *and* modern →
consumer, i.e. modern code depends on it, which is the opposite direction
of concern and confirms it cannot be retired as "legacy."

Also confirmed: `QApplication(` (the PySide6 GUI bootstrap) appears only
in `tests/gui/conftest.py`, never in `app/api/entrypoint.py` or any other
production entrypoint. `app/gui` is unreachable at runtime in the shipped
application; its retained files exist only as source, not as a running
shell.

---

## 4. Test Dependency Audit

No tests were deleted or modified in this part (per rule).

| Test | Protects | Disposition |
|---|---|---|
| `tests/test_bulk_csv_export.py` | Legacy CSV contract + modern `ExportInvestigationsCsvCommandHandler` | Still needed — exercises modern handler |
| `tests/test_export_path_traversal_adversarial.py` | Path-safety of both legacy and modern export paths | Still needed — security regression coverage |
| `tests/gui/test_investigation_workspace_risk_explanation.py`, `tests/gui/test_phase3e_acceptance.py` | Legacy widget behavior only | Obsolete *if and only if* the whole widget cluster (§1) is retired together; not obsolete in isolation today |
| `tests/gui/test_ioc_summary_risk_relevance.py`, `tests/test_ioc_detail_context.py`, `tests/test_application_layer.py` | `ioc_significance.py`, which is production-shared (§3) | **Not** obsolete — protects live production logic regardless of GUI retirement |

---

## 5. Regression Verification (executed live against this checkpoint)

| Suite | Result |
|---|---|
| Backend (`pytest`) | **1207 passed**, 4 warnings, 3 subtests passed, 0 failed |
| Frontend (`vitest run`) | **79 test files / 1094 tests passed**, 0 failed |
| TypeScript (`tsc --noEmit`) | **0 errors** |
| Frontend production build (`vite build`) | **Succeeded** (192 modules, dist emitted) |
| Rust/Tauri (`cargo`) | **Unavailable in this execution environment** — `cargo`/`rustc` not on `PATH`. Recorded as an environment limitation, not fabricated as passing. Text-level scan of `src-tauri/src` for references to the three candidate files returned none. |

---

## 6. Security / Artifact Audit

* No credentials, API keys, or private-key material found (`AKIA...`,
  PEM headers, `sk-...`-style tokens) across Python/TS/Rust/config files.
* No stray nested `.zip` archives, no `.DS_Store`, no duplicate project
  trees.
* **Stale build artifacts present:** `__pycache__/*.pyc` under
  `app/reporting/`, `app/database/`, `app/services/`, and elsewhere.
  These are harmless (regenerated, not shipped, not referenced) but are
  noted as checkpoint hygiene, not a security finding.

---

## 7. Retirement Safety Gate — Applied Per File

| Question | `csv_exporter.py` | `risk_explanation_widget.py` | `ioc_significance.py` |
|---|---|---|---|
| Authoritative modern implementation exists? | Yes | Yes | Yes (same file *is* the modern authority) |
| Production-connected? | N/A (modern path is independent) | N/A | **Yes — directly** |
| Covered by tests? | Yes | Yes | Yes |
| Independently consumed elsewhere? | Yes — `history_page.py` | Yes — 13-widget cluster via `investigation_workspace.py` | Yes — modern services |
| Provides behavior absent from modern code? | No | No | N/A (it *is* the behavior) |
| Deletion isolable to a small, reversible change? | **No** — requires retiring `history_page.py` in the same change | **No** — requires retiring the full widget cluster in the same change | **Not applicable — do not retire** |

---

## 8. Retirement Set

### SAFE RETIREMENT CANDIDATES
**None at this time.** All three headline files have full modern parity,
but none can be removed in isolation without violating rule 11.10
("can deletion be isolated to a small, reversible change?" → no for two
of them) or rule 6/§3 (shared-dependency exclusion, for the third).

### RETAIN
* `app/services/ioc_significance.py` — permanently. This is a
  production-shared module, not legacy GUI code; it must never be
  targeted by a future legacy-deletion phase.
* All 13 widgets transitively imported by `investigation_workspace.py`,
  `design/tokens/*`, and the retained half of `design/theme/` — unchanged
  from Phase 4O Part 4's conclusion; still one entangled unit.

### DEFER
* `app/gui/widgets/risk_explanation_widget.py`, `app/gui/pages/history_page.py`,
  `app/gui/utils/csv_exporter.py`, and the rest of the retained
  `app/gui` widget cluster — **now parity-cleared for retirement**, but
  only as a single coordinated deletion of the whole
  `investigation_workspace.py`-rooted cluster, not piecemeal. A future,
  separately scoped controlled-deletion phase should:
  1. Delete the full cluster (widgets + `history_page.py` +
     `csv_exporter.py` + associated legacy-only tests) in one change.
  2. Re-run the full regression suite (§5) after deletion.
  3. Re-verify no `__init__.py` is left orphaned per directory.
  4. Confirm `docs/phase4/PHASE4O_PART4_LEGACY_GUI_RETIREMENT.md`'s
     open question is closed with an explicit written "no longer
     required" for all three named behavioral gaps (this document
     constitutes that answer).

---

## 9. Final Diff Audit

Only one file was added in this part: this document. No production code,
tests, or existing documentation were modified.

```
Modern production behavior: unchanged
Legacy implementation:      unchanged
Tests:                      unchanged
Architecture:                unchanged
Documentation:               1 file added (this document)
```

---

## 10. Final Verdict

### PASS WITH CONDITIONS — RETIREMENT DECISION PASSED WITH DEFERRED ITEMS

Behavioral parity is FULL for all three PD-08 behaviors and is backed by
a live, passing regression suite (§5). No files are cleared for isolated
deletion today. The next phase must scope deletion around the entangled
`investigation_workspace.py` widget cluster as a single unit, and must
permanently exclude `app/services/ioc_significance.py` from any legacy
deletion, since it is shared production infrastructure, not legacy code.
