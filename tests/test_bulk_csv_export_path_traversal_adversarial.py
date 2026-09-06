"""
MAX-10 export security remediation (MAX-AUDIT-02) -- adversarial
path-security parity tests for `export_investigations_csv`.

`tests/test_export_path_traversal_adversarial.py` independently
verified the absolute-path boundary for `export_report`. That
verification never covered `export_investigations_csv`
(`app/application/dto.py::ExportInvestigationsCsvRequest`,
`app/application/handlers.py::ExportInvestigationsCsvCommandHandler`)
even though it shares the identical validation rule and the identical
threat model: the only legitimate source of `output_path` is a native
OS save dialog (`frontend/src/pages/investigations/
investigationsCsvExportPath.ts::pickInvestigationsCsvSavePath`), so a
request reaching the sidecar's local HTTP command endpoint with a
relative or traversal-shaped path is not a shape a legitimate caller
ever produces.

This suite closes that parity gap using the same adversarial
technique: every "rejected" case is proven at the filesystem level
(no file created anywhere under the temp root), not merely by
catching an exception. It intentionally does not re-derive the full
matrix `test_export_path_traversal_adversarial.py` already
established (dot-normalization edge cases, repeated separators, UNC
strings, etc.) -- those are shape-of-input properties of Python's
`Path.is_absolute()`, already proven format-agnostic there. What this
suite adds is the same proof for the *other* production caller of
that check.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.application.dto import CommandValidationError, ExportInvestigationsCsvRequest
from app.application.handlers import ExportInvestigationsCsvCommandHandler

from tests.test_application_layer import IsolatedServiceTestCase, make_investigation


class BulkCsvExportPathTraversalAdversarialTests(IsolatedServiceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self._export_tmpdir = tempfile.TemporaryDirectory()
        self._root = Path(self._export_tmpdir.name)

    def tearDown(self) -> None:
        self._export_tmpdir.cleanup()
        super().tearDown()

    def _assert_payload_rejected_and_nothing_written(self, payload: str) -> None:
        before = sorted(p.relative_to(self._root) for p in self._root.rglob("*"))
        with self.assertRaises(CommandValidationError):
            ExportInvestigationsCsvRequest(payload)
        after = sorted(p.relative_to(self._root) for p in self._root.rglob("*"))
        self.assertEqual(before, after, f"payload {payload!r} altered the filesystem")

    # -- relative / traversal-shaped payloads are rejected -----------------

    def test_parent_traversal_variants_rejected(self) -> None:
        for payload in (
            "../outside.csv",
            "../../outside.csv",
            "foo/../../outside.csv",
            "..\\outside.csv",
            "foo\\..\\..\\outside.csv",
        ):
            self._assert_payload_rejected_and_nothing_written(payload)

    def test_bare_relative_filename_rejected(self) -> None:
        # No ".." at all, still relative -> still rejected. Proves this
        # isn't a naive ".." string filter (same property established
        # for export_report).
        self._assert_payload_rejected_and_nothing_written("history.csv")

    def test_rejected_traversal_payload_cannot_overwrite_a_planted_target(self) -> None:
        planted = self._root.parent / "planted-outside.csv"
        planted.write_text("must not be overwritten", encoding="utf-8")
        try:
            with self.assertRaises(CommandValidationError):
                ExportInvestigationsCsvRequest("../planted-outside.csv")
            self.assertEqual(planted.read_text(encoding="utf-8"), "must not be overwritten")
        finally:
            planted.unlink()

    # -- absolute paths are accepted, including through the real handler ---

    def test_absolute_path_is_accepted(self) -> None:
        target = self._root / "legit.csv"
        request = ExportInvestigationsCsvRequest(str(target))
        self.assertEqual(request.output_path, str(target))

    def test_full_export_writes_to_exact_absolute_destination_only(self) -> None:
        self.service.save(make_investigation())
        handler = ExportInvestigationsCsvCommandHandler(self.service)

        target = self._root / "history.csv"
        sibling = self._root / "sibling.csv"
        sibling.write_text("sibling content must survive untouched", encoding="utf-8")

        response = handler.handle(ExportInvestigationsCsvRequest(str(target)))

        self.assertTrue(response["success"])
        self.assertTrue(target.exists())
        self.assertEqual(
            sibling.read_text(encoding="utf-8"),
            "sibling content must survive untouched",
        )
        created = sorted(p for p in self._root.rglob("*") if p.is_file())
        self.assertEqual(created, sorted([target, sibling]))

    def test_absolute_path_through_symlink_writes_to_resolved_target(self) -> None:
        real_dir = self._root / "real_target"
        real_dir.mkdir()
        link_dir = self._root / "link_to_real"
        try:
            link_dir.symlink_to(real_dir, target_is_directory=True)
        except OSError:
            self.skipTest("ENVIRONMENT BLOCKED: symlink creation not permitted here")

        self.service.save(make_investigation())
        handler = ExportInvestigationsCsvCommandHandler(self.service)
        output_path = link_dir / "via-symlink.csv"

        response = handler.handle(ExportInvestigationsCsvRequest(str(output_path)))

        self.assertTrue(response["success"])
        self.assertTrue((real_dir / "via-symlink.csv").exists())


if __name__ == "__main__":
    unittest.main()
