"""
§20 Part 2C-2 -- report-ingestion size-cap security control.

Threat: `app.extractor.read_report()` previously read a report file fully
into memory with an uncapped `file.read()`, before any of the IOC-extraction
regex passes ran, over the IPC-reachable `analyze_report` command as well
as the local GUI/CLI paths -- an unbounded local resource-exhaustion
vector (docs/security/report-ingestion-security-model.md TARGET STATE,
"Explicit input size limits are enforced ... before a report reaches the
extraction pipeline"; threat-model.md's "Oversized report / regex DoS"
row).

Security invariant under test: a report above
`app.extractor.MAX_REPORT_SIZE_BYTES` is rejected via the existing
`ReportReadError` channel, based on a `stat()` size check performed
*before* the file is opened for reading -- proven here by asserting the
rejection happens without ever calling `Path.open()` for the oversized
file, not merely by catching the resulting exception.

This suite is deliberately independent of tests/test_extractor.py's own
coverage: it exercises the security boundary itself (the size check) with
real files on a real filesystem, plus one full round trip through the real
production entrypoint (AnalyzeReportCommandHandler), mirroring the
structure tests/test_export_path_traversal_adversarial.py established for
the previous §20 control.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.exceptions import ReportReadError
from app.extractor import MAX_REPORT_SIZE_BYTES, read_report


class ReportSizeCapUnitTests(unittest.TestCase):
    """Direct tests against the real production function, real files."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._root = Path(self._tmpdir.name)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    # -- negative: oversized reports are rejected --------------------

    def test_oversized_report_is_rejected(self) -> None:
        path = self._root / "oversized.txt"
        path.write_bytes(b"A" * (MAX_REPORT_SIZE_BYTES + 1))

        with self.assertRaises(ReportReadError):
            read_report(path)

    def test_oversized_report_rejection_message_states_the_limit(self) -> None:
        path = self._root / "oversized.txt"
        path.write_bytes(b"A" * (MAX_REPORT_SIZE_BYTES + 1))

        with self.assertRaises(ReportReadError) as ctx:
            read_report(path)

        message = str(ctx.exception)
        self.assertIn(str(MAX_REPORT_SIZE_BYTES), message)

    def test_oversized_report_is_rejected_without_ever_opening_the_file(self) -> None:
        """The core adversarial assertion: rejection must come from the
        stat()-based size check, not from reading (part of) the file and
        discarding it -- i.e. the file is never opened for reading at
        all. Proven by patching Path.open to fail the test if called,
        not by inspecting internals."""

        path = self._root / "oversized.txt"
        path.write_bytes(b"A" * (MAX_REPORT_SIZE_BYTES + 1))

        real_open = Path.open

        def _fail_if_called(self: Path, *args: object, **kwargs: object) -> object:
            if self == path:
                raise AssertionError(
                    "read_report() opened the oversized file for reading; "
                    "the size check must reject before any read."
                )
            return real_open(self, *args, **kwargs)

        with mock.patch.object(Path, "open", _fail_if_called):
            with self.assertRaises(ReportReadError):
                read_report(path)

    def test_massively_oversized_report_is_rejected_cheaply(self) -> None:
        """A sparse file far above the cap must be rejected via stat()
        alone -- if read_report() ever fell back to reading the file,
        this test would hang/exhaust memory rather than complete."""

        path = self._root / "sparse_huge.txt"
        with path.open("wb") as file:
            file.seek(200 * 1024 * 1024)  # 200 MB, sparse -- no real disk write
            file.write(b"\0")

        with self.assertRaises(ReportReadError):
            read_report(path)

    # -- positive: legitimate reports are unaffected ------------------

    def test_report_exactly_at_the_cap_is_accepted(self) -> None:
        path = self._root / "at_cap.txt"
        path.write_bytes(b"A" * MAX_REPORT_SIZE_BYTES)

        content = read_report(path)

        self.assertEqual(len(content), MAX_REPORT_SIZE_BYTES)

    def test_report_just_under_the_cap_is_accepted(self) -> None:
        path = self._root / "under_cap.txt"
        path.write_bytes(b"A" * (MAX_REPORT_SIZE_BYTES - 1))

        content = read_report(path)

        self.assertEqual(len(content), MAX_REPORT_SIZE_BYTES - 1)

    def test_small_legitimate_report_is_unaffected(self) -> None:
        path = self._root / "normal.txt"
        text = "Malicious IP observed: 10.0.0.1\nDomain: evil.example.com\n"
        path.write_text(text, encoding="utf-8")

        self.assertEqual(read_report(path), text)

    def test_empty_report_is_still_accepted(self) -> None:
        """The size cap must not introduce a new lower-bound rejection --
        empty-report handling (if any) is out of scope for this control."""

        path = self._root / "empty.txt"
        path.write_text("", encoding="utf-8")

        self.assertEqual(read_report(path), "")

    # -- regression: existing read-failure behavior is preserved ------

    def test_missing_file_still_raises_report_read_error(self) -> None:
        path = self._root / "does_not_exist.txt"

        with self.assertRaises(ReportReadError):
            read_report(path)

    def test_non_utf8_file_under_the_cap_still_raises_report_read_error(self) -> None:
        path = self._root / "binary.bin"
        path.write_bytes(b"\xff\xfe\x00\x01not-utf8")

        with self.assertRaises(ReportReadError):
            read_report(path)


class ReportSizeCapHandlerIntegrationTests(unittest.TestCase):
    """One full round trip through the real production entrypoint,
    mirroring tests/test_application_layer.py's own
    AnalyzeReportCommandHandlerTests DB-snapshot pattern (analyze_report
    is not repository-injectable -- a pre-existing, documented gap, not
    something this test works around)."""

    def setUp(self) -> None:
        import shutil

        from app.config import DATABASE_PATH

        self._database_path = DATABASE_PATH
        self._db_backup: Path | None = None
        if DATABASE_PATH.exists():
            fd, backup_path = tempfile.mkstemp(suffix=".db")
            import os

            os.close(fd)
            shutil.copy2(DATABASE_PATH, backup_path)
            self._db_backup = Path(backup_path)

        self._tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        import shutil

        if self._db_backup is not None:
            shutil.copy2(self._db_backup, self._database_path)
            self._db_backup.unlink(missing_ok=True)
        self._tmpdir.cleanup()

    def test_analyze_report_command_rejects_an_oversized_report(self) -> None:
        from app.application.dto import AnalyzeReportRequest
        from app.application.handlers import AnalyzeReportCommandHandler

        oversized = Path(self._tmpdir.name) / "oversized_report.txt"
        oversized.write_bytes(b"A" * (MAX_REPORT_SIZE_BYTES + 1))

        handler = AnalyzeReportCommandHandler()
        response, collector = handler.handle(AnalyzeReportRequest(str(oversized)))

        self.assertFalse(response["success"])
        self.assertIsNone(response["data"])
        # No secret/credential/stack-trace/internal-path leakage beyond
        # the report_path the caller itself already supplied -- same
        # disclosure level as the existing REPORT_NOT_FOUND error.
        self.assertNotIn("Traceback", response["error"]["message"])

        # Same event shape as any other read failure (e.g. the existing
        # missing-report-path handling further up the pipeline): the
        # domain layer's own "Loading report..." progress tick fires
        # before read_report() runs, then the rejection ends the run --
        # analysis.completed must never appear.
        names = [event.event for event in collector.events]
        self.assertEqual(names[-1], "analysis.failed")
        self.assertNotIn("analysis.completed", names)

    def test_analyze_report_command_still_succeeds_for_a_normal_report(self) -> None:
        from app.application.dto import AnalyzeReportRequest
        from app.application.handlers import AnalyzeReportCommandHandler

        sample = Path("samples") / "report4.txt"
        self.assertTrue(sample.exists(), "fixture sample report must exist")
        self.assertLess(
            sample.stat().st_size,
            MAX_REPORT_SIZE_BYTES,
            "fixture must legitimately be under the cap for this test to mean anything",
        )

        handler = AnalyzeReportCommandHandler()
        response, collector = handler.handle(AnalyzeReportRequest(str(sample)))

        self.assertTrue(response["success"], msg=response.get("error"))
        names = [event.event for event in collector.events]
        self.assertEqual(names[0], "analysis.started")
        self.assertEqual(names[-1], "analysis.completed")


if __name__ == "__main__":
    unittest.main()
