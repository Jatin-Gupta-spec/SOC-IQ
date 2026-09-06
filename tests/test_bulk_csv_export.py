"""
PD-08-P5.1: tests for the `export_investigations_csv` command --
`ExportInvestigationsCsvRequest` (app/application/dto.py),
`ExportInvestigationsCsvCommandHandler` (app/application/handlers.py),
and `app.services.investigation_csv_export`.

Written with stdlib `unittest`, mirroring
`tests/test_application_layer.py::ExportReportCommandHandlerTests`'
own isolated-temp-file-database pattern (see `IsolatedServiceTestCase`,
imported from that module rather than duplicated here).
"""

from __future__ import annotations

import csv
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from app.application.dto import CommandValidationError, ExportInvestigationsCsvRequest
from app.application.errors import code_for_exception
from app.application.handlers import ExportInvestigationsCsvCommandHandler, dispatch
from app.database.models import Investigation
from app.database.service import InvestigationService
from app.services.investigation_csv_export import (
    CSV_HEADERS,
    export_investigations_history_csv,
    filter_investigations_by_search_text,
)
from tests.test_application_layer import IsolatedServiceTestCase, make_investigation


def _read_csv_rows(path: Path) -> list[list[str]]:
    with path.open(newline="", encoding="utf-8") as csv_file:
        return list(csv.reader(csv_file))


# ---------------------------------------------------------------------------
# Request DTO validation
# ---------------------------------------------------------------------------


class ExportInvestigationsCsvRequestTests(unittest.TestCase):
    def test_rejects_blank_output_path(self) -> None:
        with self.assertRaises(CommandValidationError):
            ExportInvestigationsCsvRequest("")
        with self.assertRaises(CommandValidationError):
            ExportInvestigationsCsvRequest("   ")

    def test_rejects_non_string_output_path(self) -> None:
        with self.assertRaises(CommandValidationError):
            ExportInvestigationsCsvRequest(12345)  # type: ignore[arg-type]

    def test_rejects_relative_output_path(self) -> None:
        # Same threat model as ExportReportRequest.output_path -- see
        # that DTO's docstring. A legitimate caller (the native save
        # dialog) never produces a relative path.
        with self.assertRaises(CommandValidationError):
            ExportInvestigationsCsvRequest("investigations.csv")
        with self.assertRaises(CommandValidationError):
            ExportInvestigationsCsvRequest("../investigations.csv")
        with self.assertRaises(CommandValidationError):
            ExportInvestigationsCsvRequest("reports/../../investigations.csv")

    def test_accepts_absolute_output_path(self) -> None:
        request = ExportInvestigationsCsvRequest(
            str(Path(tempfile.gettempdir()) / "investigations.csv")
        )
        self.assertTrue(Path(request.output_path).is_absolute())

    def test_search_defaults_to_none(self) -> None:
        request = ExportInvestigationsCsvRequest(
            str(Path(tempfile.gettempdir()) / "investigations.csv")
        )
        self.assertIsNone(request.search)

    def test_rejects_non_string_search(self) -> None:
        with self.assertRaises(CommandValidationError):
            ExportInvestigationsCsvRequest(
                str(Path(tempfile.gettempdir()) / "investigations.csv"),
                search=123,  # type: ignore[arg-type]
            )

    def test_accepts_string_search(self) -> None:
        request = ExportInvestigationsCsvRequest(
            str(Path(tempfile.gettempdir()) / "investigations.csv"),
            search="critical",
        )
        self.assertEqual(request.search, "critical")


# ---------------------------------------------------------------------------
# filter_investigations_by_search_text -- reconstructed
# InvestigationTableModel.filter semantics
# ---------------------------------------------------------------------------


class FilterInvestigationsBySearchTextTests(unittest.TestCase):
    def setUp(self) -> None:
        self.investigations = [
            make_investigation(report_name="malware.exe", severity="HIGH", status="COMPLETED"),
            make_investigation(report_name="clean.txt", severity="LOW", status="COMPLETED"),
            make_investigation(report_name="phish.eml", severity="MEDIUM", status="FAILED"),
        ]

    def test_none_returns_all_unchanged(self) -> None:
        result = filter_investigations_by_search_text(self.investigations, None)
        self.assertEqual(result, self.investigations)

    def test_blank_returns_all_unchanged(self) -> None:
        result = filter_investigations_by_search_text(self.investigations, "   ")
        self.assertEqual(result, self.investigations)

    def test_matches_report_name_case_insensitively(self) -> None:
        result = filter_investigations_by_search_text(self.investigations, "MALWARE")
        self.assertEqual([i.report_name for i in result], ["malware.exe"])

    def test_matches_severity(self) -> None:
        result = filter_investigations_by_search_text(self.investigations, "medium")
        self.assertEqual([i.report_name for i in result], ["phish.eml"])

    def test_matches_status(self) -> None:
        result = filter_investigations_by_search_text(self.investigations, "failed")
        self.assertEqual([i.report_name for i in result], ["phish.eml"])

    def test_no_match_returns_empty_list(self) -> None:
        result = filter_investigations_by_search_text(self.investigations, "nonexistent")
        self.assertEqual(result, [])

    def test_none_valued_fields_do_not_raise(self) -> None:
        investigation = make_investigation(
            report_name=None, severity=None, status=None  # type: ignore[arg-type]
        )
        result = filter_investigations_by_search_text([investigation], "anything")
        self.assertEqual(result, [])
        # Must not raise -- this is the assertion that matters here.
        filter_investigations_by_search_text([investigation], "")


# ---------------------------------------------------------------------------
# export_investigations_history_csv -- CSV correctness (Part 6/10)
# ---------------------------------------------------------------------------


class ExportInvestigationsHistoryCsvTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _output_path(self, filename: str = "history.csv") -> Path:
        return Path(self._tmpdir.name) / filename

    def test_header_row_matches_legacy_exporter_exactly(self) -> None:
        output_path = self._output_path()
        export_investigations_history_csv([], output_path)

        rows = _read_csv_rows(output_path)
        self.assertEqual(
            rows[0],
            [
                "Investigation ID",
                "Report Name",
                "Severity",
                "Risk Score",
                "Status",
                "Analyzed At",
            ],
        )
        self.assertEqual(list(CSV_HEADERS), rows[0])

    def test_empty_investigations_writes_header_only_csv(self) -> None:
        output_path = self._output_path()
        result = export_investigations_history_csv([], output_path)

        self.assertEqual(result, output_path)
        self.assertTrue(output_path.exists())
        rows = _read_csv_rows(output_path)
        self.assertEqual(len(rows), 1)

    def test_representative_row(self) -> None:
        investigation = make_investigation(
            investigation_id=42,
            report_name="malware.exe",
            severity="HIGH",
            risk_score=87,
            status="COMPLETED",
            analyzed_at=datetime(2026, 1, 15, 12, 30, 45, tzinfo=UTC),
        )
        output_path = self._output_path()
        export_investigations_history_csv([investigation], output_path)

        rows = _read_csv_rows(output_path)
        self.assertEqual(
            rows[1],
            ["42", "malware.exe", "HIGH", "87", "COMPLETED", "2026-01-15 12:30:45 UTC"],
        )

    def test_multiple_investigations_preserve_input_order(self) -> None:
        investigations = [
            make_investigation(investigation_id=1, report_name="a.txt"),
            make_investigation(investigation_id=2, report_name="b.txt"),
            make_investigation(investigation_id=3, report_name="c.txt"),
        ]
        output_path = self._output_path()
        export_investigations_history_csv(investigations, output_path)

        rows = _read_csv_rows(output_path)
        self.assertEqual([row[1] for row in rows[1:]], ["a.txt", "b.txt", "c.txt"])

    def test_null_analyzed_at_exports_as_empty_field_not_a_crash(self) -> None:
        # Legacy exporter (app/gui/utils/csv_exporter.py) called
        # `.strftime(...)` unconditionally and would raise AttributeError
        # here -- see module docstring's documented deviation.
        investigation = make_investigation(analyzed_at=None)  # type: ignore[arg-type]
        output_path = self._output_path()

        export_investigations_history_csv([investigation], output_path)

        rows = _read_csv_rows(output_path)
        self.assertEqual(rows[1][-1], "")

    def test_null_investigation_id_exports_as_empty_field(self) -> None:
        investigation = make_investigation(investigation_id=None)
        output_path = self._output_path()

        export_investigations_history_csv([investigation], output_path)

        rows = _read_csv_rows(output_path)
        self.assertEqual(rows[1][0], "")

    def test_null_string_fields_export_as_empty_not_a_crash(self) -> None:
        investigation = make_investigation(
            report_name=None,  # type: ignore[arg-type]
            severity=None,  # type: ignore[arg-type]
            status=None,  # type: ignore[arg-type]
        )
        output_path = self._output_path()

        export_investigations_history_csv([investigation], output_path)

        rows = _read_csv_rows(output_path)
        self.assertEqual(rows[1][1:3] + [rows[1][4]], ["", "", ""])

    def test_embedded_comma_is_quoted_and_round_trips(self) -> None:
        investigation = make_investigation(report_name="report, v2 final.txt")
        output_path = self._output_path()

        export_investigations_history_csv([investigation], output_path)

        rows = _read_csv_rows(output_path)
        self.assertEqual(rows[1][1], "report, v2 final.txt")

    def test_embedded_quote_is_escaped_and_round_trips(self) -> None:
        investigation = make_investigation(report_name='the "final" report.txt')
        output_path = self._output_path()

        export_investigations_history_csv([investigation], output_path)

        raw = output_path.read_text(encoding="utf-8")
        self.assertIn('""final""', raw)  # RFC 4180 doubled-quote escaping

        rows = _read_csv_rows(output_path)
        self.assertEqual(rows[1][1], 'the "final" report.txt')

    def test_embedded_newline_is_quoted_and_round_trips(self) -> None:
        investigation = make_investigation(report_name="line one\nline two.txt")
        output_path = self._output_path()

        export_investigations_history_csv([investigation], output_path)

        rows = _read_csv_rows(output_path)
        self.assertEqual(rows[1][1], "line one\nline two.txt")
        # Exactly one data row parsed despite the embedded newline --
        # proves it was quoted, not split into a bogus extra row.
        self.assertEqual(len(rows), 2)

    def test_unicode_is_preserved(self) -> None:
        investigation = make_investigation(report_name="ドキュメント_отчёт_📄.txt")
        output_path = self._output_path()

        export_investigations_history_csv([investigation], output_path)

        rows = _read_csv_rows(output_path)
        self.assertEqual(rows[1][1], "ドキュメント_отчёт_📄.txt")

    def test_file_is_utf8_encoded(self) -> None:
        investigation = make_investigation(report_name="café.txt")
        output_path = self._output_path()

        export_investigations_history_csv([investigation], output_path)

        # Decoding strictly as UTF-8 must succeed without error.
        output_path.read_bytes().decode("utf-8")

    # -- CSV formula-injection mitigation (Part 6) ------------------------

    def test_leading_equals_sign_is_neutralized(self) -> None:
        investigation = make_investigation(report_name="=cmd|'/c calc'!A1")
        output_path = self._output_path()

        export_investigations_history_csv([investigation], output_path)

        rows = _read_csv_rows(output_path)
        self.assertEqual(rows[1][1], "'=cmd|'/c calc'!A1")

    def test_leading_plus_minus_at_are_neutralized(self) -> None:
        for trigger, field_overrides in (
            ("+", {"report_name": "+1+1"}),
            ("-", {"severity": "-2+3"}),
            ("@", {"status": "@SUM(A1:A2)"}),
        ):
            with self.subTest(trigger=trigger):
                investigation = make_investigation(**field_overrides)
                output_path = self._output_path(f"trigger_{trigger}.csv")

                export_investigations_history_csv([investigation], output_path)

                raw = output_path.read_text(encoding="utf-8")
                self.assertIn(f"'{trigger}", raw)

    def test_numeric_fields_are_never_sanitized(self) -> None:
        # risk_score/investigation_id are always backend-generated
        # integers -- sanitization must never touch them (nor could a
        # negative-looking risk score be legitimately mistaken for a
        # formula-injection payload; it's a plain int either way).
        investigation = make_investigation(investigation_id=7, risk_score=-5)
        output_path = self._output_path()

        export_investigations_history_csv([investigation], output_path)

        rows = _read_csv_rows(output_path)
        self.assertEqual(rows[1][0], "7")
        self.assertEqual(rows[1][3], "-5")

    def test_non_triggering_values_are_left_untouched(self) -> None:
        investigation = make_investigation(report_name="normal_report.txt")
        output_path = self._output_path()

        export_investigations_history_csv([investigation], output_path)

        rows = _read_csv_rows(output_path)
        self.assertEqual(rows[1][1], "normal_report.txt")

    # -- write failure ------------------------------------------------------

    def test_write_failure_raises_runtime_error(self) -> None:
        # Mirrors every app/reporting/*_exporter.py module's own
        # OSError -> RuntimeError convention exactly (see
        # test_export_report_translates_exporter_write_failure).
        investigation = make_investigation()
        # A path whose parent is a *file*, not a directory: mkdir(parents=True)
        # will raise NotADirectoryError (an OSError subclass).
        blocking_file = Path(self._tmpdir.name) / "blocking_file"
        blocking_file.write_text("x")
        bogus_path = blocking_file / "history.csv"

        with self.assertRaises(RuntimeError):
            export_investigations_history_csv([investigation], bogus_path)

    def test_write_failure_creates_no_partial_file(self) -> None:
        investigation = make_investigation()
        blocking_file = Path(self._tmpdir.name) / "blocking_file"
        blocking_file.write_text("x")
        bogus_path = blocking_file / "history.csv"

        with self.assertRaises(RuntimeError):
            export_investigations_history_csv([investigation], bogus_path)

        self.assertFalse(bogus_path.exists())


# ---------------------------------------------------------------------------
# ExportInvestigationsCsvCommandHandler -- vertical slice
# ---------------------------------------------------------------------------


class ExportInvestigationsCsvCommandHandlerTests(IsolatedServiceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self._export_tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self._export_tmpdir.cleanup()
        super().tearDown()

    def _output_path(self, filename: str = "investigations.csv") -> Path:
        return Path(self._export_tmpdir.name) / filename

    def test_exports_all_investigations(self) -> None:
        self.service.save(make_investigation(report_name="a.txt"))
        self.service.save(make_investigation(report_name="b.txt"))
        handler = ExportInvestigationsCsvCommandHandler(self.service)
        output_path = self._output_path()

        response = handler.handle(
            ExportInvestigationsCsvRequest(str(output_path))
        )

        self.assertTrue(response["success"], msg=response.get("error"))
        self.assertIsNone(response["error"])
        self.assertEqual(response["data"]["output_path"], str(output_path))
        self.assertEqual(response["data"]["row_count"], 2)
        self.assertTrue(output_path.exists())

        rows = _read_csv_rows(output_path)
        self.assertEqual({row[1] for row in rows[1:]}, {"a.txt", "b.txt"})

    def test_deterministic_row_ordering_matches_id_desc(self) -> None:
        # InvestigationRepository.list_all orders ORDER BY id DESC --
        # the same ordering list_investigations already exposes. This
        # handler must reuse it unchanged, not re-sort.
        first_id = self.service.save(make_investigation(report_name="first.txt"))
        second_id = self.service.save(make_investigation(report_name="second.txt"))
        third_id = self.service.save(make_investigation(report_name="third.txt"))
        handler = ExportInvestigationsCsvCommandHandler(self.service)
        output_path = self._output_path()

        handler.handle(ExportInvestigationsCsvRequest(str(output_path)))

        rows = _read_csv_rows(output_path)
        ids_in_file = [int(row[0]) for row in rows[1:]]
        self.assertEqual(ids_in_file, sorted([first_id, second_id, third_id], reverse=True))

    def test_empty_history_returns_success_with_zero_rows(self) -> None:
        # Part 8: an empty result is a valid, predictable export, never
        # an application error.
        handler = ExportInvestigationsCsvCommandHandler(self.service)
        output_path = self._output_path()

        response = handler.handle(
            ExportInvestigationsCsvRequest(str(output_path))
        )

        self.assertTrue(response["success"], msg=response.get("error"))
        self.assertEqual(response["data"]["row_count"], 0)
        self.assertTrue(output_path.exists())
        rows = _read_csv_rows(output_path)
        self.assertEqual(len(rows), 1)  # header only

    def test_search_filters_the_exported_rows(self) -> None:
        self.service.save(make_investigation(report_name="malware.exe", severity="HIGH"))
        self.service.save(make_investigation(report_name="clean.txt", severity="LOW"))
        handler = ExportInvestigationsCsvCommandHandler(self.service)
        output_path = self._output_path()

        response = handler.handle(
            ExportInvestigationsCsvRequest(str(output_path), search="malware")
        )

        self.assertTrue(response["success"], msg=response.get("error"))
        self.assertEqual(response["data"]["row_count"], 1)
        rows = _read_csv_rows(output_path)
        self.assertEqual([row[1] for row in rows[1:]], ["malware.exe"])

    def test_search_matching_nothing_still_succeeds_with_header_only_csv(self) -> None:
        self.service.save(make_investigation(report_name="clean.txt"))
        handler = ExportInvestigationsCsvCommandHandler(self.service)
        output_path = self._output_path()

        response = handler.handle(
            ExportInvestigationsCsvRequest(str(output_path), search="nonexistent")
        )

        self.assertTrue(response["success"], msg=response.get("error"))
        self.assertEqual(response["data"]["row_count"], 0)
        rows = _read_csv_rows(output_path)
        self.assertEqual(len(rows), 1)

    def test_blank_search_behaves_as_no_filter(self) -> None:
        self.service.save(make_investigation(report_name="a.txt"))
        self.service.save(make_investigation(report_name="b.txt"))
        handler = ExportInvestigationsCsvCommandHandler(self.service)
        output_path = self._output_path()

        response = handler.handle(
            ExportInvestigationsCsvRequest(str(output_path), search="   ")
        )

        self.assertEqual(response["data"]["row_count"], 2)

    def test_dispatched_via_command_name(self) -> None:
        self.service.save(make_investigation(report_name="a.txt"))
        output_path = self._output_path()

        with patch(
            "app.application.handlers.InvestigationService",
            return_value=self.service,
        ):
            response = dispatch(
                "export_investigations_csv",
                {"output_path": str(output_path)},
            )

        self.assertTrue(response["success"], msg=response.get("error"))
        self.assertEqual(response["data"]["row_count"], 1)


# ---------------------------------------------------------------------------
# Error translation (mirrors DispatchErrorTranslationTests' own pattern)
# ---------------------------------------------------------------------------


class ExportInvestigationsCsvErrorTranslationTests(IsolatedServiceTestCase):
    def test_repository_failure_translates_to_database_error(self) -> None:
        from app.exceptions import DatabaseError

        with patch.object(
            InvestigationService, "list_all", side_effect=DatabaseError("disk gone")
        ):
            response = dispatch(
                "export_investigations_csv",
                {"output_path": str(Path(tempfile.gettempdir()) / "out.csv")},
            )

        self.assertFalse(response["success"])
        self.assertEqual(response["error"]["code"], "DATABASE_ERROR")

    def test_serialization_write_failure_translates_to_internal_error(self) -> None:
        # Pins the same real, source-verified fallback
        # test_export_report_translates_exporter_write_failure pins for
        # export_report: RuntimeError is not a SOCIQError subclass and
        # not in errors.py's exception-code map, so it falls through to
        # INTERNAL_ERROR via dispatch()'s generic exception boundary.
        self.service.save(make_investigation(report_name="a.txt"))

        with patch(
            "app.application.handlers.InvestigationService",
            return_value=self.service,
        ):
            with patch(
                "app.application.handlers.export_investigations_history_csv",
                side_effect=RuntimeError(
                    "Failed to export investigation history CSV: disk full"
                ),
            ):
                response = dispatch(
                    "export_investigations_csv",
                    {"output_path": str(Path(tempfile.gettempdir()) / "out.csv")},
                )

        self.assertFalse(response["success"])
        self.assertEqual(response["error"]["code"], "INTERNAL_ERROR")

    def test_invalid_payload_translates_to_invalid_command_payload(self) -> None:
        response = dispatch("export_investigations_csv", {"output_path": "relative.csv"})

        self.assertFalse(response["success"])
        self.assertEqual(response["error"]["code"], "INVALID_COMMAND_PAYLOAD")

    def test_missing_output_path_translates_to_invalid_command_payload(self) -> None:
        response = dispatch("export_investigations_csv", {})

        self.assertFalse(response["success"])
        self.assertEqual(response["error"]["code"], "INVALID_COMMAND_PAYLOAD")


if __name__ == "__main__":
    unittest.main()
