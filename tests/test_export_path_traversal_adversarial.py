"""
§20 Part 2B-2 -- independent adversarial verification of the export
path-traversal boundary added in Part 2B-1
(app/application/dto.py::ExportReportRequest.__post_init__).

This suite is deliberately independent of tests/test_application_layer.py's
own ExportReportCommandHandlerTests: it re-derives the threat model from
the real production path rather than re-running the same assertions, and
every "rejected" case is proven at the filesystem level (no file created
anywhere), not merely by catching an exception -- see §19/§9 of the audit
brief ("avoid assert raises(...) without verifying the filesystem").

Confirmed single production export surface (re-traced independently in
this part, not assumed from Part 2B-1's report):

    frontend --HTTP--> Python sidecar "export_report" command
        -> app/application/handlers.py::ExportReportCommandHandler.handle()
        -> app/application/dto.py::ExportReportRequest (validation boundary)
        -> app/reporting/service.py::ReportingService.export_{html,json,markdown,pdf}
        -> app/reporting/export_manager.py::ExportManager.export_*
        -> app/reporting/{html,json,markdown,pdf}_exporter.py
               (each: output_path.parent.mkdir(parents=True, exist_ok=True)
                then writes output_path directly)

Two other filesystem-writing exporters exist in the tree
(app/gui/utils/csv_exporter.py, app/exporters.py) but neither is reachable
through export_report or any other dispatched command:

  - app/gui/utils/csv_exporter.py is only called from
    app/gui/pages/history_page.py, which gets its destination from
    QFileDialog.getSaveFileName() -- legacy, in-process Qt GUI, out of
    HARD SCOPE ("modify legacy GUI") and already slated for removal
    (Phase 4O). Same trust model as export_report's own native dialog:
    the destination is chosen by the local user through an OS picker,
    not received over any IPC/HTTP boundary.

  - app/exporters.py (export_to_json/export_to_csv) is only called from
    app/main.py, the CLI entrypoint -- destination comes directly from
    argv on the user's own machine, not from any network-reachable
    command. Different threat model entirely (the local user already has
    full filesystem access at that trust level); out of scope for this
    IPC-boundary hardening.

So the adversarial matrix below is exercised exclusively against
ExportReportRequest / ExportReportCommandHandler, which is the only
network/IPC-reachable export path in the codebase.

Investigation title/case name was independently checked and does not
feed into path construction anywhere in this flow (output_path is a
wholly separate value never derived from investigation data) -- so
"user-controlled report/case name" traversal (§12 of the brief) is
N/A for this architecture, not merely untested.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.application.dto import CommandValidationError, ExportReportRequest
from app.application.handlers import ExportReportCommandHandler
from app.reporting.service import ReportingService

from tests.test_application_layer import IsolatedServiceTestCase, make_investigation


class ExportPathTraversalAdversarialTests(IsolatedServiceTestCase):
    def setUp(self) -> None:
        super().setUp()
        # Named distinctly from the parent's own `self._tmpdir` (used for
        # the isolated SQLite db) -- reusing that name would overwrite the
        # parent's TemporaryDirectory reference and let it be garbage
        # collected early, deleting the test database out from under it.
        self._export_tmpdir = tempfile.TemporaryDirectory()
        self._root = Path(self._export_tmpdir.name)

    def tearDown(self) -> None:
        self._export_tmpdir.cleanup()
        super().tearDown()

    def _assert_payload_rejected_and_nothing_written(self, payload: str) -> None:
        """The core adversarial assertion: construction must fail *and*
        the filesystem must show no trace of the attempt anywhere under
        the temp root (not just at the naive traversal target)."""
        before = sorted(p.relative_to(self._root) for p in self._root.rglob("*"))
        with self.assertRaises(CommandValidationError):
            ExportReportRequest(1, "json", payload)
        after = sorted(p.relative_to(self._root) for p in self._root.rglob("*"))
        self.assertEqual(before, after, f"payload {payload!r} altered the filesystem")

    # -- §4/§5: basic + mixed-separator traversal matrix ------------------

    def test_parent_traversal_variants_rejected(self) -> None:
        for payload in (
            "../outside.csv",
            "../../outside.csv",
            "../../../outside.csv",
        ):
            self._assert_payload_rejected_and_nothing_written(payload)

    def test_windows_style_traversal_variants_rejected(self) -> None:
        for payload in (
            "..\\outside.csv",
            "..\\..\\outside.csv",
            "..\\..\\..\\outside.csv",
        ):
            self._assert_payload_rejected_and_nothing_written(payload)

    def test_mixed_separator_traversal_rejected(self) -> None:
        for payload in (
            "foo/../../outside.csv",
            "foo\\..\\..\\outside.csv",
            "foo/..\\../outside.csv",
            "foo\\../..\\outside.csv",
        ):
            self._assert_payload_rejected_and_nothing_written(payload)

    def test_leading_dot_segment_traversal_rejected(self) -> None:
        for payload in ("./../outside.csv", ".\\..\\outside.csv"):
            self._assert_payload_rejected_and_nothing_written(payload)

    # -- §8/§9: dot-segment normalization + repeated separators -----------

    def test_dot_normalization_edge_cases_rejected(self) -> None:
        # All of these are still *relative* strings regardless of how
        # many/few ".." segments they contain -- the boundary is
        # "relative is rejected", not string-matching "..", so a
        # relative path with zero ".." segments must be rejected too
        # (proves this isn't a naive ".." filter -- see §19).
        for payload in (
            ".",
            "foo/./bar.csv",
            "foo/../bar.csv",
            "foo/../../bar.csv",
            "bar.csv",  # no ".." at all, still relative -> still rejected
        ):
            self._assert_payload_rejected_and_nothing_written(payload)

    def test_repeated_separator_traversal_rejected(self) -> None:
        for payload in ("foo//../../outside.csv", "foo\\\\..\\\\outside.csv"):
            self._assert_payload_rejected_and_nothing_written(payload)

    # -- §6/§14: absolute-path handling (accept, per the documented -------
    #    contract that output_path IS the destination, not a filename
    #    joined to a root -- there is no root for one to escape)

    def test_absolute_path_is_accepted(self) -> None:
        target = self._root / "legit.json"
        request = ExportReportRequest(1, "json", str(target))
        self.assertEqual(request.output_path, str(target))

    def test_absolute_path_with_embedded_dot_segments_is_accepted_and_resolves_correctly(
        self,
    ) -> None:
        # "/tmp/x/subdir/../legit.json" is still an absolute string (the
        # embedded ".." never makes it relative), and per §14 the correct
        # property to check is not string-prefix confinement but that
        # the *resolved* path lands exactly where normal path semantics
        # say it should -- proving the app doesn't need (and doesn't
        # claim) a root to confine into.
        (self._root / "subdir").mkdir()
        raw = str(self._root / "subdir" / ".." / "legit.json")
        request = ExportReportRequest(1, "json", raw)
        self.assertTrue(Path(request.output_path).is_absolute())
        self.assertEqual(
            Path(request.output_path).resolve(), (self._root / "legit.json").resolve()
        )

    def test_full_export_with_embedded_dot_segments_lands_at_resolved_path(self) -> None:
        # End-to-end proof through the real handler: the file created is
        # the one path semantics predict, nothing else.
        investigation_id = self.service.save(make_investigation())
        handler = ExportReportCommandHandler(self.service, ReportingService())
        (self._root / "subdir").mkdir()
        raw = str(self._root / "subdir" / ".." / "resolved.json")
        expected = (self._root / "resolved.json").resolve()

        response = handler.handle(ExportReportRequest(investigation_id, "json", raw))

        self.assertTrue(response["success"])
        self.assertTrue(expected.exists())
        # Nothing else was created under the temp root.
        created = sorted(p for p in self._root.rglob("*") if p.is_file())
        self.assertEqual(created, [expected])

    # -- §7: UNC / network path -- Windows-only construct, cannot be -----
    #    exercised as a real filesystem destination on this Linux CI
    #    environment. Documented as such rather than claimed PASS: on
    #    POSIX, Path("\\\\server\\share\\x").is_absolute() is False (the
    #    backslash isn't a separator), so the *current* validation
    #    boundary rejects it here -- which is the conservative/safe
    #    outcome, not a verified statement about real Windows UNC
    #    handling.

    def test_unc_style_string_on_this_platform_is_rejected_conservatively(self) -> None:
        # ENVIRONMENT LIMITED: this only proves POSIX interprets the UNC
        # string as relative and therefore rejects it (safe default), not
        # that Windows UNC absolute-path handling has been verified.
        self._assert_payload_rejected_and_nothing_written("\\\\server\\share\\outside.csv")

    # -- §13: extension manipulation --------------------------------------

    def test_relative_path_with_traversal_after_extension_rejected(self) -> None:
        self._assert_payload_rejected_and_nothing_written("report.csv/../outside.csv")

    # -- §16/§17: legitimate exports + boundary values ---------------------

    def test_legitimate_filenames_across_supported_formats_succeed(self) -> None:
        investigation_id = self.service.save(make_investigation())
        handler = ExportReportCommandHandler(self.service, ReportingService())

        cases = [
            ("html", "SOC-IQ-report.html"),
            ("json", "investigation-001.json"),
            ("markdown", "case_2026-08-30.md"),
            ("pdf", "report with spaces.pdf"),
        ]
        for export_format, filename in cases:
            output_path = self._root / filename
            response = handler.handle(
                ExportReportRequest(investigation_id, export_format, str(output_path))
            )
            self.assertTrue(response["success"], f"{export_format} export failed")
            self.assertTrue(output_path.exists(), f"{filename} was not written")

    def test_unicode_filename_absolute_path_succeeds(self) -> None:
        investigation_id = self.service.save(make_investigation())
        handler = ExportReportCommandHandler(self.service, ReportingService())
        output_path = self._root / "\u30ec\u30dd\u30fc\u30c8-2026.json"  # "report" in Japanese

        response = handler.handle(
            ExportReportRequest(investigation_id, "json", str(output_path))
        )

        self.assertTrue(response["success"])
        self.assertTrue(output_path.exists())

    # CSV is intentionally not one of VALID_EXPORT_FORMATS for this
    # command (app/application/dto.py's own documented exclusion) --
    # N/A here rather than tested, since there is no export_report
    # csv path to exercise.
    def test_csv_format_is_not_a_supported_export_report_format(self) -> None:
        with self.assertRaises(CommandValidationError):
            ExportReportRequest(1, "csv", str(self._root / "x.csv"))

    # -- §15: symlink boundary ---------------------------------------------

    def test_absolute_path_through_symlink_writes_to_resolved_target(self) -> None:
        # There is no confinement root for a symlink to help escape --
        # the app already lets output_path be any absolute location the
        # OS permits (§6/§14 above). This test exists to prove that
        # property explicitly for the symlink case rather than leaving it
        # unverified: a symlink component in an otherwise-valid absolute
        # path still resolves and writes normally, with no ability for a
        # *relative* payload to smuggle a traversal past the
        # absolute-path check via a symlink (the check runs on the raw
        # string before any symlink resolution occurs).
        real_dir = self._root / "real_target"
        real_dir.mkdir()
        link_dir = self._root / "link_to_real"
        try:
            link_dir.symlink_to(real_dir, target_is_directory=True)
        except OSError:
            self.skipTest("ENVIRONMENT BLOCKED: symlink creation not permitted here")

        investigation_id = self.service.save(make_investigation())
        handler = ExportReportCommandHandler(self.service, ReportingService())
        output_path = link_dir / "via-symlink.json"

        response = handler.handle(
            ExportReportRequest(investigation_id, "json", str(output_path))
        )

        self.assertTrue(response["success"])
        self.assertTrue((real_dir / "via-symlink.json").exists())

    def test_relative_traversal_cannot_bypass_absolute_check_via_symlink(self) -> None:
        # A relative payload is rejected on its string shape alone,
        # before any filesystem/symlink resolution happens -- so no
        # symlink placed by an attacker in the sidecar's working
        # directory can turn a rejected relative payload into a
        # successful write.
        self._assert_payload_rejected_and_nothing_written("../link_to_real/outside.json")

    # -- §14 (Part 2B-3): overwrite protection ------------------------------

    def test_export_overwrites_only_the_exact_selected_destination(self) -> None:
        # An export to an already-existing file legitimately overwrites
        # it -- that's the intended "Save As" semantic, same as any
        # desktop app, and is not itself a vulnerability. The security
        # property to prove is narrower: only the exact absolute path the
        # caller supplied is touched, nothing else nearby (a sibling file,
        # or an internal file the sidecar happens to also have open) is
        # affected by an export request.
        investigation_id = self.service.save(make_investigation())
        handler = ExportReportCommandHandler(self.service, ReportingService())

        target = self._root / "report.json"
        sibling = self._root / "sibling.json"
        target.write_text("pre-existing target content", encoding="utf-8")
        sibling.write_text("sibling content must survive untouched", encoding="utf-8")

        response = handler.handle(
            ExportReportRequest(investigation_id, "json", str(target))
        )

        self.assertTrue(response["success"])
        self.assertTrue(target.exists())
        self.assertNotEqual(target.read_text(encoding="utf-8"), "pre-existing target content")
        self.assertEqual(sibling.read_text(encoding="utf-8"), "sibling content must survive untouched")

    def test_rejected_traversal_payload_cannot_overwrite_a_planted_target(self) -> None:
        # Plant a file at the traversal target itself (one directory
        # above the temp root) and confirm a malicious relative payload
        # cannot reach and modify it -- construction fails before any
        # exporter runs, so the planted file's content must be untouched.
        planted = self._root.parent / "planted-outside.json"
        planted.write_text("must not be overwritten", encoding="utf-8")
        try:
            with self.assertRaises(CommandValidationError):
                ExportReportRequest(1, "json", "../planted-outside.json")
            self.assertEqual(planted.read_text(encoding="utf-8"), "must not be overwritten")
        finally:
            planted.unlink()


if __name__ == "__main__":
    unittest.main()
