"""
SOC-IQ
Bulk Investigation History CSV Export (PD-08-P5.1)

Pure(ish) helpers behind the `export_investigations_csv` application
command (app/application/handlers.py::ExportInvestigationsCsvCommandHandler).

# Relationship to the legacy exporter

Reconstructs the CSV shape of the legacy
`app.gui.utils.csv_exporter.export_investigations_to_csv` (six columns,
same order, same header spelling) against the *modern* investigation
data source (`InvestigationService.list_all()`, the same query
`list_investigations`/`search_investigations` already use) instead of
whatever subset happened to be loaded into the legacy History page's
table model at the time.

Two deliberate, documented deviations from the legacy exporter, both
robustness fixes rather than shape changes:

  - `analyzed_at is None` no longer raises `AttributeError`. The legacy
    exporter called `.strftime(...)` unconditionally
    (app/gui/utils/csv_exporter.py); `Investigation.analyzed_at` is
    typed `datetime` with a non-None default, but nothing prevents a
    caller from constructing one with `analyzed_at=None` explicitly, and
    Part 6/9 of the PD-08-P5.1 brief requires this module not to corrupt
    or crash on legitimate investigation data. A missing timestamp
    exports as an empty field, matching how every other optional field
    below is already handled.
  - CSV formula-injection mitigation (Part 6): a leading `=`, `+`, `-`,
    `@`, tab, or carriage return on any string-typed field is prefixed
    with `'` before writing, per the standard OWASP CSV-injection
    mitigation. Only applied to the three free-text fields
    (`report_name`, `severity`, `status`) that ultimately originate from
    user-controlled input (a report's filename / analysis output) --
    never to `investigation_id` or `risk_score`, which are always
    backend-generated integers.

# Relationship to Reporting (app/reporting/*)

Deliberately NOT part of `app.reporting`: that package exports one
`InvestigationReport` (one investigation, four rich formats) built by
`ReportBuilder`/`ExportManager`. This module exports a flat list of
investigation *summary* rows in exactly one format. There is no shared
primitive to reuse between the two -- see
docs/phase4/PD08_P5_1_BULK_CSV_EXPORT_BACKEND_CONTRACT.md Part 3 for the
forensic comparison -- so this stays a standalone module rather than
being force-fit under `app.reporting`.
"""

from __future__ import annotations

import csv
from pathlib import Path

from app.database.models import Investigation

#: Exact header spelling/casing/order reconstructed from
#: `app.gui.utils.csv_exporter.export_investigations_to_csv`.
CSV_HEADERS = (
    "Investigation ID",
    "Report Name",
    "Severity",
    "Risk Score",
    "Status",
    "Analyzed At",
)

#: Leading characters that a spreadsheet application (Excel, LibreOffice
#: Calc, Google Sheets) may interpret as the start of a formula when a
#: CSV cell is opened. Per the OWASP CSV-injection mitigation, prefixing
#: the value with a single `'` neutralizes this while leaving the
#: underlying text otherwise unchanged.
_FORMULA_TRIGGER_CHARS = ("=", "+", "-", "@", "\t", "\r")


def _sanitize_csv_field(value: str) -> str:
    """
    Neutralize a leading formula-trigger character on a single
    string-typed CSV field. Never applied to numeric fields (see
    module docstring).
    """

    if value and value[0] in _FORMULA_TRIGGER_CHARS:
        return "'" + value

    return value


def filter_investigations_by_search_text(
    investigations: list[Investigation],
    search_text: str | None,
) -> list[Investigation]:
    """
    Reconstruct of `InvestigationTableModel.filter`'s exact matching
    rule (app/gui/models/investigation_table_model.py): case-insensitive
    substring match against `report_name` OR `severity` OR `status`. A
    blank/`None` `search_text` returns every investigation unchanged,
    matching the legacy "empty search box" behavior.

    Applied here, in the application layer, over an already-fetched
    list -- not as a new repository query -- per PD-08-P5.1 Part 5
    ("do not duplicate repository logic... do not introduce a new
    database query system").
    """

    if not search_text or not search_text.strip():
        return list(investigations)

    text = search_text.lower().strip()

    return [
        investigation
        for investigation in investigations
        if text in (investigation.report_name or "").lower()
        or text in (investigation.severity or "").lower()
        or text in (investigation.status or "").lower()
    ]


def _format_analyzed_at(investigation: Investigation) -> str:
    """
    Legacy formatting (`%Y-%m-%d %H:%M:%S UTC`, no timezone conversion --
    the legacy exporter trusted the stored value was already UTC, which
    `Investigation.analyzed_at`'s own default factory guarantees for
    every investigation created through normal application flow). A
    missing timestamp exports as an empty field rather than raising --
    see module docstring's "deliberate deviations" section.
    """

    analyzed_at = investigation.analyzed_at

    if analyzed_at is None:
        return ""

    try:
        return analyzed_at.strftime("%Y-%m-%d %H:%M:%S UTC")
    except AttributeError:
        # Defensive only: `analyzed_at` is typed `datetime | None`, so a
        # value with no `.strftime` should never reach this branch in
        # practice. Falls back to the empty-string convention used for
        # every other missing/malformed field, rather than raising and
        # aborting the entire bulk export over one row.
        return ""


def export_investigations_history_csv(
    investigations: list[Investigation],
    output_path: Path,
) -> Path:
    """
    Write `investigations` to `output_path` as CSV, per PD-08-P5.1
    Parts 6-8.

    - Encoding: explicit UTF-8 (matches the legacy exporter).
    - Newlines: `newline=""` on the file handle, letting `csv.writer`
      own line-ending behavior (`\\r\\n` per RFC 4180) -- the same
      convention the legacy exporter and every `app/reporting/*_exporter.py`
      module already use, avoiding the doubled-blank-line bug that
      omitting `newline=""` causes on Windows.
    - Quoting/escaping: `csv.writer`'s default `QUOTE_MINIMAL`, which
      already correctly handles embedded commas, quotes (doubled per
      RFC 4180), and embedded newlines -- no manual string
      concatenation (Part 6).
    - Row order: whatever order `investigations` arrives in. The
      command handler passes it `InvestigationService.list_all()`'s
      result unchanged (id DESC, per
      `InvestigationRepository.list_all`'s `ORDER BY id DESC`) --
      deterministic, and consistent with `list_investigations`'s own
      ordering.
    - Empty `investigations`: writes a header-only CSV (Part 8) -- this
      is a valid, successful export, not an error; the caller
      distinguishes "empty result" from "export failure" by whether
      this function returns or raises.

    Raises:
        RuntimeError: if the file cannot be written (mirrors every
            `app/reporting/*_exporter.py` module's own
            `except OSError -> raise RuntimeError` convention, so
            `app.application.errors.code_for_exception`'s existing
            fallback -- INTERNAL_ERROR, since RuntimeError is not a
            SOCIQError subclass -- applies identically here).
    """

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with output_path.open(
            mode="w",
            newline="",
            encoding="utf-8",
        ) as csv_file:

            writer = csv.writer(csv_file)

            writer.writerow(CSV_HEADERS)

            for investigation in investigations:

                writer.writerow(
                    [
                        (
                            investigation.investigation_id
                            if investigation.investigation_id is not None
                            else ""
                        ),
                        _sanitize_csv_field(investigation.report_name or ""),
                        _sanitize_csv_field(investigation.severity or ""),
                        (
                            investigation.risk_score
                            if investigation.risk_score is not None
                            else ""
                        ),
                        _sanitize_csv_field(investigation.status or ""),
                        _format_analyzed_at(investigation),
                    ]
                )

        return output_path

    except OSError as error:
        raise RuntimeError(
            f"Failed to export investigation history CSV: {error}"
        ) from error
