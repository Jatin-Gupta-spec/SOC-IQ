# PD-08-P5.1 — Bulk Investigation CSV Export: Forensic Audit & Backend Contract

**Status:** Backend foundation implemented. Frontend export button deferred to a later P5 part (see HARD STOP below).
**Related:** `docs/contracts/command-model.md`, `docs/contracts/response-model.md`,
`docs/contracts/error-model.md`, `docs/architecture/16-reporting-architecture.md`,
`docs/security/filesystem-security-model.md`.

## 1. Legacy behavior (forensic findings)

Source: `app/gui/utils/csv_exporter.py`, `app/gui/pages/history_page.py`,
`app/gui/controllers/history_controller.py`, `app/gui/models/investigation_table_model.py`.

### CSV shape

| Property | Legacy behavior |
|---|---|
| Columns (order) | `Investigation ID, Report Name, Severity, Risk Score, Status, Analyzed At` |
| Header casing | Title Case, exact strings above |
| Delimiter | `,` (Python `csv.writer` default) |
| Quoting | `csv.QUOTE_MINIMAL` (library default; not set explicitly) |
| Escaping | RFC 4180 doubled-quote (library default) |
| Newlines | File opened with `newline=""`; `csv.writer` owns line endings |
| Encoding | Explicit `utf-8` |
| `Analyzed At` format | `analyzed_at.strftime("%Y-%m-%d %H:%M:%S UTC")` — **no timezone conversion**, assumes the stored value is already UTC (true for every investigation created through normal application flow, since `Investigation.analyzed_at`'s default factory always uses `datetime.now(UTC)`) |
| Null/empty handling | **None** — `investigation.analyzed_at.strftime(...)` is called unconditionally; a `None` `analyzed_at` raises `AttributeError` and aborts the whole export. Confirmed bug, not a deliberate design choice. |
| List/nested-data serialization | N/A — no list/nested fields are exported |
| Row order | Whatever order the History page's table model currently holds (see below) |
| Filename | User-chosen via `QFileDialog.getSaveFileName(..., "investigations.csv", "CSV Files (*.csv)")` — no fixed convention |

### Export scope

**Not** "all investigations." Confirmed by tracing the call path:

1. `HistoryPage.refresh()` calls `HistoryController.get_recent_investigations()`,
   which calls `InvestigationService.find_recent(limit=10)` — **the top 10 most
   recent investigations only**, by construction of the controller's own default.
2. `InvestigationTableModel.filter(text)` then narrows that in-memory set
   client-side: case-insensitive substring match against `report_name` OR
   `severity` OR `status` (`InvestigationTableModel.filter`).
3. `HistoryPage._export_csv()` exports exactly what steps 1–2 currently left
   in the table model — explicitly documented in that method's own comment as
   intentional ("export exactly what is currently shown in the table").

So legacy bulk export scope = **top-10-recent, optionally filtered by search text**,
not the investigation history in full. This is a controller-default artifact, not
a documented product requirement for a 10-row cap.

## 2. Modern architecture (traced)

- Transport: single `POST /commands/{name}` dispatcher
  (`app/api/app.py` → `app/application/handlers.py::dispatch`/`COMMAND_HANDLERS`).
  No per-feature REST routes exist or are added here.
- Investigation listing: `list_investigations` command →
  `ListInvestigationsCommandHandler` → `InvestigationService.list_all()` →
  `InvestigationRepository.list_all()` (`ORDER BY id DESC`, deterministic,
  unbounded — returns every investigation, not a page).
- Existing multi-field search: `search_investigations` only supports
  `find_by_report_name` (report name alone) — no repository method
  supports the legacy 3-field OR search, so that filter is reconstructed at
  the application layer instead of as a new repository query (see §4).
- Existing export precedent: `export_report` (`ExportReportRequest` /
  `ExportReportCommandHandler`) — single investigation, one of four rich
  formats, writes directly to a caller-supplied absolute `output_path`
  (no HTTP file download; this is a Tauri sidecar, not a browser). Its own
  docstring explicitly notes the legacy CSV exporter was **excluded** from
  that contract because it "takes a *list* of investigations, not one" —
  the exact gap this part fills.
- Frontend precedent for obtaining `output_path`:
  `frontend/src/pages/reports/reportExportPath.ts::pickReportSavePath` —
  native OS save dialog via `tauri-plugin-dialog`. The future P5.x frontend
  part will add the equivalent for this command; **not implemented here**
  (Part 11 of the driving brief).

## 3. Reporting separation

`app/reporting/*` (`ReportingService`, `ExportManager`, the four
`*_exporter.py` modules) builds one `InvestigationReport` per investigation
in HTML/PDF/JSON/Markdown. There is no reusable primitive between that and a
flat multi-row CSV of investigation summaries — confirmed by reading every
file in `app/reporting/`. `Reporting` is left completely unmodified.

## 4. Modern contract

**Command:** `export_investigations_csv`

**Request DTO:** `ExportInvestigationsCsvRequest` (`app/application/dto.py`)

| Field | Type | Required | Semantics |
|---|---|---|---|
| `output_path` | `str` | yes | Absolute filesystem path. Same validation rule as `ExportReportRequest.output_path`: rejected if not absolute (relative/traversal paths are a shape a legitimate caller — the native save dialog — never produces). |
| `search` | `str \| None` | no | Case-insensitive substring match against `report_name` OR `severity` OR `status`, reconstructing `InvestigationTableModel.filter`'s exact legacy semantics. `None`/blank = no filter (export everything). |

**Data source:** `InvestigationService.list_all()` — same query, same
`id DESC` ordering as `list_investigations`. **Deliberate scope decision:**
unlike the legacy page, this does **not** cap at 10 recent investigations —
a feature named "**Bulk** Investigation CSV Export" is reasonably read as
exporting the full history, and the top-10 cap was traced (§1) to an
incidental controller default, not a specified requirement. Filtering by
`search` remains supported for parity with the legacy search-box behavior.

**Output representation:** CSV file written directly to `output_path` by
the backend (same "no HTTP download, writes to disk" convention as
`export_report`) — six columns identical to legacy (§1), reused via
`app.services.investigation_csv_export.export_investigations_history_csv`.

**Filename convention:** chosen by the caller (via the future native save
dialog) — no backend-enforced convention, matching `export_report`.

**Media type / encoding:** N/A at the command layer (no HTTP body returned);
the file itself is UTF-8 CSV.

**Empty-result behavior:** valid success response, header-only CSV file,
`row_count: 0` — never an error (Part 8).

**Error behavior:** reuses existing conventions unchanged —
`DatabaseError` → `DATABASE_ERROR`; a write failure inside the CSV writer
raises `RuntimeError` (mirroring every `app/reporting/*_exporter.py`
module's own `OSError → RuntimeError` convention) → falls through
`code_for_exception`'s existing fallback to `INTERNAL_ERROR`; DTO validation
failures → `INVALID_COMMAND_PAYLOAD`. No new error codes introduced.

**Response shape** (`ok(...)`):
```json
{ "output_path": "<absolute path>", "row_count": <int> }
```

## 5. CSV correctness & security (Part 6)

- Proper `csv.writer` serialization throughout — no manual string
  concatenation.
- **CSV formula-injection mitigation:** a leading `=`, `+`, `-`, `@`, tab, or
  carriage return on a string field (`report_name`, `severity`, `status` —
  never the two integer fields) is prefixed with `'`, per the standard
  OWASP mitigation. Documented in
  `app/services/investigation_csv_export.py`'s module docstring.
- Null-safety improvements over the legacy exporter (a bug fix, not a shape
  change): `analyzed_at is None`, `investigation_id is None`, and blank/`None`
  string fields all export as an empty CSV field instead of raising and
  aborting the whole export.

## 6. Deliberately out of scope for P5.1

- The frontend export button / native save dialog wiring (next P5 part).
- Any change to Dashboard, Timeline, Risk Significance/Explanation,
  existing Reporting UX, the database schema, or the legacy GUI.
- Background jobs/streaming/queues for large exports — the existing
  `list_all()` path is already used unbounded by `list_investigations`
  and the Dashboard; no evidence in this codebase that bulk CSV export
  needs different infrastructure.
