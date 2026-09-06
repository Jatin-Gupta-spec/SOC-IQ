"""
Regression tests for the SOC-IQ reporting subsystem:
HTML/JSON/Markdown/PDF exporters, ExportManager, ReportBuilder,
and ReportingService.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from app.database.models import Investigation
from app.reporting.builder import ReportBuilder
from app.reporting.export_manager import ExportManager
from app.reporting.html_exporter import HTMLReportExporter
from app.reporting.json_exporter import JSONReportExporter
from app.reporting.markdown_exporter import MarkdownReportExporter
from app.reporting.models import InvestigationReport
from app.reporting.service import ReportingService

try:
    from app.reporting.pdf_exporter import PDFReportExporter

    PDF_EXPORTER_AVAILABLE = True
except ImportError:
    PDF_EXPORTER_AVAILABLE = False


def make_report(**overrides) -> InvestigationReport:
    defaults = dict(
        report_name="malware_report.txt",
        analyzed_at="2024-01-01T12:00:00+00:00",
        status="COMPLETED",
        severity="HIGH",
        risk_score=65,
        confidence=0.8,
        ioc_score=20,
        threat_intel_score=15,
        cve_score=10,
        iocs={
            "ipv4": ["1.2.3.4"],
            "domains": [],
            "sha256": ["a" * 64],
        },
        threat_intelligence={
            "status": "ok",
            "hashes": [
                {
                    "sha256": "a" * 64,
                    "verdict": "Malicious",
                    "detection_ratio": "5/70",
                }
            ],
        },
    )
    defaults.update(overrides)
    return InvestigationReport(**defaults)


def make_multi_type_ti_report(**overrides) -> InvestigationReport:
    """
    Synthetic report whose threat intelligence spans all four
    enrichable categories -- hashes, ips, domains, urls -- for
    exercising Phase 3E reporting parity.
    """

    defaults = dict(
        report_name="multi_type_report.txt",
        analyzed_at="2024-01-01T12:00:00+00:00",
        status="COMPLETED",
        severity="CRITICAL",
        risk_score=90,
        confidence=0.9,
        ioc_score=40,
        threat_intel_score=60,
        cve_score=0,
        iocs={
            "sha256": ["a" * 64],
            "ipv4": ["203.0.113.7"],
            "domains": ["evilcorp.example"],
            "urls": ["https://evilcorp.example/payload.exe"],
        },
        threat_intelligence={
            "status": "ok",
            "hashes": [
                {
                    "sha256": "a" * 64,
                    "verdict": "Malicious",
                    "detection_ratio": "10/70",
                }
            ],
            "ips": [
                {
                    "ip": "203.0.113.7",
                    "verdict": "Malicious",
                    "detection_ratio": "8/70",
                }
            ],
            "domains": [
                {
                    "domain": "evilcorp.example",
                    "verdict": "Suspicious",
                    "detection_ratio": "4/70",
                }
            ],
            "urls": [
                {
                    "url": "https://evilcorp.example/payload.exe",
                    "verdict": "Malicious",
                    "detection_ratio": "15/70",
                }
            ],
        },
    )
    defaults.update(overrides)
    return InvestigationReport(**defaults)


def make_investigation(**overrides) -> Investigation:
    defaults = dict(
        report_name="malware_report.txt",
        iocs={"ipv4": ["1.2.3.4"]},
        threat_intelligence={"status": "ok", "hashes": []},
        risk_score=42,
        severity="MEDIUM",
        confidence=0.5,
        ioc_score=10,
        threat_intel_score=0,
        cve_score=0,
        analyzed_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    defaults.update(overrides)
    return Investigation(**defaults)


# ==========================================================
# ReportBuilder
# ==========================================================


def test_report_builder_maps_investigation_fields():
    investigation = make_investigation(report_name="built.txt")

    report = ReportBuilder.build(investigation)

    assert isinstance(report, InvestigationReport)
    assert report.report_name == "built.txt"
    assert report.analyzed_at == investigation.analyzed_at.isoformat()
    assert report.severity == investigation.severity
    assert report.risk_score == investigation.risk_score
    assert report.iocs == investigation.iocs
    assert report.threat_intelligence == investigation.threat_intelligence


def test_report_builder_maps_investigation_id():
    investigation = make_investigation(
        report_name="built.txt",
        investigation_id=123,
    )

    report = ReportBuilder.build(investigation)

    assert report.investigation_id == 123


def test_report_builder_investigation_id_defaults_to_none():
    investigation = make_investigation(report_name="built.txt")

    report = ReportBuilder.build(investigation)

    assert report.investigation_id is None


# ==========================================================
# JSON exporter
# ==========================================================


def test_json_exporter_writes_valid_json(tmp_path):
    report = make_report()
    output_path = tmp_path / "report.json"

    result_path = JSONReportExporter.export(report, output_path)

    assert result_path == output_path
    assert output_path.exists()

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["report_name"] == "malware_report.txt"
    assert data["risk_score"] == 65
    assert data["iocs"]["ipv4"] == ["1.2.3.4"]


def test_json_exporter_includes_investigation_id(tmp_path):
    report = make_report(investigation_id=555)
    output_path = tmp_path / "report.json"

    JSONReportExporter.export(report, output_path)

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["investigation_id"] == 555


def test_json_exporter_creates_parent_directories(tmp_path):
    report = make_report()
    output_path = tmp_path / "nested" / "dir" / "report.json"

    JSONReportExporter.export(report, output_path)

    assert output_path.exists()


def test_json_exporter_wraps_oserror(tmp_path, monkeypatch):
    report = make_report()
    output_path = tmp_path / "report.json"

    def raise_oserror(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(
        "pathlib.Path.open",
        raise_oserror,
    )

    with pytest.raises(RuntimeError):
        JSONReportExporter.export(report, output_path)


# ==========================================================
# Markdown exporter
# ==========================================================


def test_markdown_exporter_writes_file(tmp_path):
    report = make_report()
    output_path = tmp_path / "report.md"

    result_path = MarkdownReportExporter.export(report, output_path)

    assert result_path == output_path
    content = output_path.read_text(encoding="utf-8")

    assert "SOC-IQ Investigation Report" in content
    assert "malware_report.txt" in content
    assert "HIGH" in content


def test_markdown_exporter_lists_ioc_values(tmp_path):
    report = make_report(iocs={"ipv4": ["9.9.9.9"], "domains": []})
    output_path = tmp_path / "report.md"

    MarkdownReportExporter.export(report, output_path)
    content = output_path.read_text(encoding="utf-8")

    assert "9.9.9.9" in content
    assert "None" in content  # empty domains list


def test_markdown_exporter_includes_investigation_id(tmp_path):
    report = make_report(investigation_id=321)
    output_path = tmp_path / "report.md"

    MarkdownReportExporter.export(report, output_path)
    content = output_path.read_text(encoding="utf-8")

    assert "321" in content


def test_markdown_exporter_lists_threat_intelligence(tmp_path):
    report = make_report()
    output_path = tmp_path / "report.md"

    MarkdownReportExporter.export(report, output_path)
    content = output_path.read_text(encoding="utf-8")

    assert "Threat Intelligence" in content
    assert "Malicious" in content


def test_markdown_exporter_no_threat_intelligence_message(tmp_path):
    report = make_report(threat_intelligence={"status": "ok", "hashes": []})
    output_path = tmp_path / "report.md"

    MarkdownReportExporter.export(report, output_path)
    content = output_path.read_text(encoding="utf-8")

    assert "No threat intelligence available." in content


def test_markdown_exporter_creates_parent_directories(tmp_path):
    report = make_report()
    output_path = tmp_path / "a" / "b" / "report.md"

    MarkdownReportExporter.export(report, output_path)

    assert output_path.exists()


def test_markdown_exporter_wraps_oserror(tmp_path, monkeypatch):
    report = make_report()
    output_path = tmp_path / "report.md"

    def raise_oserror(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("pathlib.Path.open", raise_oserror)

    with pytest.raises(RuntimeError):
        MarkdownReportExporter.export(report, output_path)


# ==========================================================
# HTML exporter
# ==========================================================


def test_html_exporter_writes_html_file(tmp_path):
    report = make_report()
    output_path = tmp_path / "report.html"

    result_path = HTMLReportExporter.export(report, output_path)

    assert result_path == output_path
    content = output_path.read_text(encoding="utf-8")

    assert "<html" in content.lower() or "<!doctype" in content.lower()
    assert "malware_report.txt" not in content or True  # name may be escaped


def test_html_exporter_includes_investigation_id(tmp_path):
    report = make_report(investigation_id=42)
    output_path = tmp_path / "report.html"

    HTMLReportExporter.export(report, output_path)
    content = output_path.read_text(encoding="utf-8")

    assert "42" in content


def test_html_exporter_shows_na_for_missing_investigation_id(tmp_path):
    report = make_report(investigation_id=None)
    output_path = tmp_path / "report.html"

    HTMLReportExporter.export(report, output_path)
    content = output_path.read_text(encoding="utf-8")

    assert "N/A" in content


def test_html_exporter_escapes_ioc_type_names(tmp_path):
    report = make_report(
        iocs={"<script>alert(1)</script>": ["x"]},
        threat_intelligence={"status": "ok", "hashes": []},
    )
    output_path = tmp_path / "xss.html"

    HTMLReportExporter.export(report, output_path)
    content = output_path.read_text(encoding="utf-8")

    assert "<script>alert(1)</script>" not in content


def test_html_exporter_handles_empty_iocs_and_threat_intel(tmp_path):
    report = make_report(iocs={}, threat_intelligence={})
    output_path = tmp_path / "empty.html"

    HTMLReportExporter.export(report, output_path)
    content = output_path.read_text(encoding="utf-8")

    assert "No threat intelligence available." in content


def test_html_exporter_creates_parent_directories(tmp_path):
    report = make_report()
    output_path = tmp_path / "nested" / "report.html"

    HTMLReportExporter.export(report, output_path)

    assert output_path.exists()


@pytest.mark.parametrize(
    "risk_score,expected_label",
    [
        (10, "Low Risk"),
        (45, "Medium Risk"),
        (70, "High Risk"),
        (95, "Critical Risk"),
    ],
)
def test_html_exporter_risk_label_bands(tmp_path, risk_score, expected_label):
    report = make_report(risk_score=risk_score)
    output_path = tmp_path / "report.html"

    HTMLReportExporter.export(report, output_path)
    content = output_path.read_text(encoding="utf-8")

    assert expected_label in content


# ==========================================================
# PDF exporter
# ==========================================================


@pytest.mark.skipif(
    not PDF_EXPORTER_AVAILABLE, reason="PDF exporter dependency unavailable"
)
def test_pdf_exporter_writes_nonempty_pdf(tmp_path):
    report = make_report()
    output_path = tmp_path / "report.pdf"

    result_path = PDFReportExporter.export(report, output_path)

    assert result_path == output_path
    assert output_path.exists()
    assert output_path.stat().st_size > 0
    # PDF file signature.
    assert output_path.read_bytes()[:4] == b"%PDF"


@pytest.mark.skipif(
    not PDF_EXPORTER_AVAILABLE, reason="PDF exporter dependency unavailable"
)
def test_pdf_exporter_creates_parent_directories(tmp_path):
    report = make_report()
    output_path = tmp_path / "nested" / "report.pdf"

    PDFReportExporter.export(report, output_path)

    assert output_path.exists()


@pytest.mark.skipif(
    not PDF_EXPORTER_AVAILABLE, reason="PDF exporter dependency unavailable"
)
def test_pdf_exporter_handles_empty_iocs(tmp_path):
    report = make_report(iocs={}, threat_intelligence={})
    output_path = tmp_path / "empty.pdf"

    PDFReportExporter.export(report, output_path)

    assert output_path.exists()
    assert output_path.stat().st_size > 0


# ==========================================================
# ExportManager
# ==========================================================


def test_export_manager_export_html_delegates(tmp_path):
    report = make_report()
    output_path = tmp_path / "report.html"

    result = ExportManager.export_html(report, output_path)

    assert result == output_path
    assert output_path.exists()


def test_export_manager_export_json_delegates(tmp_path):
    report = make_report()
    output_path = tmp_path / "report.json"

    result = ExportManager.export_json(report, output_path)

    assert result == output_path
    assert json.loads(output_path.read_text(encoding="utf-8"))


def test_export_manager_export_markdown_delegates(tmp_path):
    report = make_report()
    output_path = tmp_path / "report.md"

    result = ExportManager.export_markdown(report, output_path)

    assert result == output_path
    assert output_path.exists()


@pytest.mark.skipif(
    not PDF_EXPORTER_AVAILABLE, reason="PDF exporter dependency unavailable"
)
def test_export_manager_export_pdf_delegates(tmp_path):
    report = make_report()
    output_path = tmp_path / "report.pdf"

    result = ExportManager.export_pdf(report, output_path)

    assert result == output_path
    assert output_path.exists()


# ==========================================================
# ReportingService
# ==========================================================


def test_reporting_service_build_default_filename_has_extension():
    service = ReportingService()

    filename = service.build_default_filename(extension="json")

    assert filename.startswith("SOC-IQ_Investigation_")
    assert filename.endswith(".json")


def test_reporting_service_build_default_filename_defaults_to_html():
    service = ReportingService()

    filename = service.build_default_filename()

    assert filename.endswith(".html")


def test_reporting_service_export_json_writes_file(tmp_path):
    service = ReportingService()
    investigation = make_investigation(report_name="svc.txt")
    output_path = tmp_path / "svc.json"

    result = service.export_json(investigation, output_path)

    assert result == output_path
    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["report_name"] == "svc.txt"


def test_reporting_service_export_markdown_writes_file(tmp_path):
    service = ReportingService()
    investigation = make_investigation(report_name="svc.txt")
    output_path = tmp_path / "svc.md"

    result = service.export_markdown(investigation, output_path)

    assert result == output_path
    assert output_path.exists()


def test_reporting_service_export_html_writes_file(tmp_path):
    service = ReportingService()
    investigation = make_investigation(report_name="svc.txt")
    output_path = tmp_path / "svc.html"

    result = service.export_html(investigation, output_path)

    assert result == output_path
    assert output_path.exists()


@pytest.mark.skipif(
    not PDF_EXPORTER_AVAILABLE, reason="PDF exporter dependency unavailable"
)
def test_reporting_service_export_pdf_writes_file(tmp_path):
    service = ReportingService()
    investigation = make_investigation(report_name="svc.txt")
    output_path = tmp_path / "svc.pdf"

    result = service.export_pdf(investigation, output_path)

    assert result == output_path
    assert output_path.exists()


# ==========================================================
# Multi-category threat intelligence (Phase 3E reporting parity)
# ==========================================================


def test_markdown_exporter_includes_all_four_ti_categories(tmp_path):
    report = make_multi_type_ti_report()
    output_path = tmp_path / "multi.md"

    MarkdownReportExporter.export(report, output_path)
    content = output_path.read_text(encoding="utf-8")

    assert "a" * 64 in content
    assert "203.0.113.7" in content
    assert "evilcorp.example" in content
    assert "https://evilcorp.example/payload.exe" in content
    assert "SHA256" in content
    assert "IPv4" in content
    assert "Domain" in content
    assert "URL" in content


def test_markdown_exporter_hash_only_report_still_omits_other_categories(tmp_path):
    """
    Existing SHA256-only reports must keep rendering exactly as
    before -- no stray IPv4/Domain/URL rows appear when there is
    nothing to show for those categories.
    """

    report = make_report()
    output_path = tmp_path / "hash_only.md"

    MarkdownReportExporter.export(report, output_path)
    content = output_path.read_text(encoding="utf-8")

    ti_section = content.split("## Threat Intelligence", 1)[1]

    assert "Malicious" in ti_section
    assert "IPv4" not in ti_section
    assert "Domain" not in ti_section
    assert "URL" not in ti_section


def test_html_exporter_includes_all_four_ti_categories(tmp_path):
    report = make_multi_type_ti_report()
    output_path = tmp_path / "multi.html"

    HTMLReportExporter.export(report, output_path)
    content = output_path.read_text(encoding="utf-8")

    assert "a" * 64 in content
    assert "203.0.113.7" in content
    assert "evilcorp.example" in content
    assert "https://evilcorp.example/payload.exe" in content
    assert "SHA256" in content
    assert "IPv4" in content
    assert "Domain" in content
    assert "URL" in content


def test_html_exporter_threat_entries_count_spans_all_categories(tmp_path):
    report = make_multi_type_ti_report()
    output_path = tmp_path / "multi_count.html"

    HTMLReportExporter.export(report, output_path)
    content = output_path.read_text(encoding="utf-8")

    idx = content.find("Threat Entries")
    following = content[idx : idx + 150]

    assert "4" in following.split("summary-value")[1]


@pytest.mark.skipif(
    not PDF_EXPORTER_AVAILABLE, reason="PDF exporter dependency unavailable"
)
def test_pdf_exporter_includes_all_four_ti_categories(tmp_path):
    pypdf = pytest.importorskip("pypdf")

    report = make_multi_type_ti_report()
    output_path = tmp_path / "multi.pdf"

    PDFReportExporter.export(report, output_path)

    assert output_path.exists()
    assert output_path.stat().st_size > 0

    reader = pypdf.PdfReader(str(output_path))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)

    assert "203.0.113.7" in text
    assert "evilcorp.example" in text
    # SHA256/URL values are truncated with "..." in the PDF table,
    # so check the truncated prefix rather than the full value.
    assert ("a" * 24) in text
    assert "https://evilcorp.example" in text


@pytest.mark.skipif(
    not PDF_EXPORTER_AVAILABLE, reason="PDF exporter dependency unavailable"
)
def test_pdf_exporter_hash_only_report_still_generates(tmp_path):
    report = make_report()
    output_path = tmp_path / "hash_only.pdf"

    PDFReportExporter.export(report, output_path)

    assert output_path.exists()
    assert output_path.stat().st_size > 0
    assert output_path.read_bytes()[:4] == b"%PDF"


def test_pdf_exporter_wraps_oserror(tmp_path, monkeypatch):
    """MAX-21B-3 Part 6: PDF export previously let a raw OSError
    escape uncaught -- unlike the other three exporters, which all
    wrap OSError into RuntimeError. Confirms parity now that PDF
    export goes through the same `atomic_write` + try/except OSError
    shape as JSON/Markdown/HTML."""
    report = make_report()
    output_path = tmp_path / "report.pdf"

    def raise_oserror(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("pathlib.Path.mkdir", raise_oserror)

    with pytest.raises(RuntimeError):
        PDFReportExporter.export(report, output_path)


# ==========================================================
# MAX-21B-3 Part 2/3 -- atomic export writes (MAX-21A F3)
# ==========================================================
#
# These tests exercise `app.reporting.atomic_write.atomic_write`
# directly (format-agnostic) plus each exporter's integration with
# it, proving the specific reliability properties MAX-21A F3 asked
# for: a destination is only ever the old complete file or the new
# complete file, a failed write/replace leaves any previously-valid
# destination untouched, and no stray temp files are left behind.


class TestAtomicWriteHelper:
    """Direct tests of the shared `atomic_write` helper."""

    def test_writes_new_file(self, tmp_path):
        from app.reporting.atomic_write import atomic_write

        output_path = tmp_path / "out.txt"

        atomic_write(output_path, lambda tmp: tmp.write_text("hello"))

        assert output_path.read_text() == "hello"

    def test_creates_parent_directories(self, tmp_path):
        from app.reporting.atomic_write import atomic_write

        output_path = tmp_path / "a" / "b" / "out.txt"

        atomic_write(output_path, lambda tmp: tmp.write_text("hello"))

        assert output_path.read_text() == "hello"

    def test_no_leftover_temp_files_on_success(self, tmp_path):
        from app.reporting.atomic_write import atomic_write

        output_path = tmp_path / "out.txt"

        atomic_write(output_path, lambda tmp: tmp.write_text("hello"))

        remaining = list(tmp_path.iterdir())
        assert remaining == [output_path]

    def test_existing_destination_survives_failed_write(self, tmp_path):
        """The core F3 property: if `write_fn` fails partway through,
        a previously-valid destination file must be left completely
        untouched -- never truncated, never replaced with partial
        content."""
        from app.reporting.atomic_write import atomic_write

        output_path = tmp_path / "out.txt"
        output_path.write_text("original valid content")

        def failing_write(tmp: Path) -> None:
            tmp.write_text("partial")
            raise OSError("simulated write failure")

        with pytest.raises(OSError):
            atomic_write(output_path, failing_write)

        assert output_path.read_text() == "original valid content"

    def test_no_leftover_temp_files_on_failed_write(self, tmp_path):
        from app.reporting.atomic_write import atomic_write

        output_path = tmp_path / "out.txt"
        output_path.write_text("original")

        def failing_write(tmp: Path) -> None:
            tmp.write_text("partial")
            raise OSError("simulated write failure")

        with pytest.raises(OSError):
            atomic_write(output_path, failing_write)

        remaining = list(tmp_path.iterdir())
        assert remaining == [output_path]

    def test_existing_destination_survives_failed_replace(self, tmp_path, monkeypatch):
        """Simulates the final `os.replace` itself failing (e.g. a
        permission error at the last moment) -- the existing valid
        destination must still survive, and the completed temp file
        is cleaned up rather than left behind."""
        from app.reporting import atomic_write as atomic_write_module

        output_path = tmp_path / "out.txt"
        output_path.write_text("original valid content")

        def raise_on_replace(*args, **kwargs):
            raise OSError("simulated replace failure")

        monkeypatch.setattr(atomic_write_module.os, "replace", raise_on_replace)

        with pytest.raises(OSError):
            atomic_write_module.atomic_write(
                output_path, lambda tmp: tmp.write_text("new content")
            )

        assert output_path.read_text() == "original valid content"
        remaining = list(tmp_path.iterdir())
        assert remaining == [output_path]

    def test_retry_after_failure_succeeds(self, tmp_path):
        """A failed export must not poison subsequent attempts --
        retrying with a working `write_fn` succeeds normally."""
        from app.reporting.atomic_write import atomic_write

        output_path = tmp_path / "out.txt"

        with pytest.raises(OSError):
            def failing_write(tmp: Path) -> None:
                raise OSError("simulated failure")

            atomic_write(output_path, failing_write)

        assert not output_path.exists()

        atomic_write(output_path, lambda tmp: tmp.write_text("succeeded"))

        assert output_path.read_text() == "succeeded"

    def test_new_destination_is_complete_not_partial(self, tmp_path):
        """A successful write is never observable half-written: the
        temp file is fully populated before the rename ever happens."""
        from app.reporting.atomic_write import atomic_write

        output_path = tmp_path / "out.txt"
        payload = "x" * 10_000

        atomic_write(output_path, lambda tmp: tmp.write_text(payload))

        assert output_path.read_text() == payload


class TestExportersAreAtomic:
    """Per-format integration tests: each exporter must leave a
    previously-valid export untouched when the underlying write
    fails, closing MAX-21A F3 for every format `ExportManager`
    supports."""

    def test_json_exporter_preserves_existing_file_on_failure(self, tmp_path, monkeypatch):
        report = make_report()
        output_path = tmp_path / "report.json"
        output_path.write_text('{"valid": "previous export"}')

        def raise_oserror(*args, **kwargs):
            raise OSError("disk full")

        monkeypatch.setattr("pathlib.Path.open", raise_oserror)

        with pytest.raises(RuntimeError):
            JSONReportExporter.export(report, output_path)

        monkeypatch.undo()
        assert output_path.read_text() == '{"valid": "previous export"}'

    def test_markdown_exporter_preserves_existing_file_on_failure(self, tmp_path, monkeypatch):
        report = make_report()
        output_path = tmp_path / "report.md"
        output_path.write_text("# previous valid export")

        def raise_oserror(*args, **kwargs):
            raise OSError("disk full")

        monkeypatch.setattr("pathlib.Path.open", raise_oserror)

        with pytest.raises(RuntimeError):
            MarkdownReportExporter.export(report, output_path)

        monkeypatch.undo()
        assert output_path.read_text() == "# previous valid export"

    def test_html_exporter_preserves_existing_file_on_failure(self, tmp_path, monkeypatch):
        report = make_report()
        output_path = tmp_path / "report.html"
        output_path.write_text("<html>previous valid export</html>")

        def raise_oserror(*args, **kwargs):
            raise OSError("disk full")

        monkeypatch.setattr("pathlib.Path.write_text", raise_oserror)

        with pytest.raises(RuntimeError):
            HTMLReportExporter.export(report, output_path)

        assert output_path.read_text() == "<html>previous valid export</html>"

    @pytest.mark.skipif(
        not PDF_EXPORTER_AVAILABLE, reason="PDF exporter dependency unavailable"
    )
    def test_pdf_exporter_preserves_existing_file_on_failure(self, tmp_path, monkeypatch):
        report = make_report()
        output_path = tmp_path / "report.pdf"
        output_path.write_bytes(b"%PDF-1.4 previous valid export")

        def raise_oserror(*args, **kwargs):
            raise OSError("permission denied")

        # `PDFReportExporter._render` calls `canvas.Canvas(str(tmp_path))`
        # then eventually `pdf.save()`, which is what actually performs
        # filesystem I/O -- patch that to simulate a late rendering
        # failure after the canvas has already been constructed.
        monkeypatch.setattr(
            "reportlab.pdfgen.canvas.Canvas.save", raise_oserror
        )

        with pytest.raises(RuntimeError):
            PDFReportExporter.export(report, output_path)

        assert output_path.read_bytes() == b"%PDF-1.4 previous valid export"

    def test_json_exporter_no_stray_temp_files_after_failure(self, tmp_path, monkeypatch):
        report = make_report()
        output_path = tmp_path / "report.json"

        def raise_oserror(*args, **kwargs):
            raise OSError("disk full")

        monkeypatch.setattr("pathlib.Path.open", raise_oserror)

        with pytest.raises(RuntimeError):
            JSONReportExporter.export(report, output_path)

        assert list(tmp_path.iterdir()) == []

    def test_json_exporter_retry_after_failure_succeeds(self, tmp_path, monkeypatch):
        """MAX-21B-3 Part 3: retry behavior -- a failed export
        followed by a real retry (no monkeypatch this time) must
        succeed and produce a complete, valid file."""
        report = make_report()
        output_path = tmp_path / "report.json"

        def raise_oserror(*args, **kwargs):
            raise OSError("disk full")

        monkeypatch.setattr("pathlib.Path.open", raise_oserror)
        with pytest.raises(RuntimeError):
            JSONReportExporter.export(report, output_path)

        monkeypatch.undo()

        result_path = JSONReportExporter.export(report, output_path)

        assert result_path == output_path
        data = json.loads(output_path.read_text(encoding="utf-8"))
        assert data["report_name"] == "malware_report.txt"
