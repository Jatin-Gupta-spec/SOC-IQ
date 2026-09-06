"""
Phase 3E -- Backend Parity Closeout: end-to-end acceptance test.

Builds a single synthetic investigation with:
  * NO malicious SHA256 hash
  * at least one malicious IPv4
  * at least one malicious domain
  * at least one malicious URL

and proves the non-hash threat-intelligence is not silently lost
anywhere in the pipeline: scoring, correlation, risk explanation,
the GUI (display + selection), and every human-readable report
format (HTML, Markdown, PDF).

Before Phase 3E, every one of these consumers only read
`threat_intelligence["hashes"]`, so a report with only malicious
IPs/domains/URLs and no malicious hash would have scored as
low-risk, shown no correlation link, explained itself as "nothing
malicious found", and omitted the indicators from every export --
despite VirusTotal having flagged them. This test is the guard
against that regression coming back.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.database.models import Investigation
from app.gui.pages.investigation_workspace import InvestigationWorkspacePage
from app.reporting.builder import ReportBuilder
from app.reporting.html_exporter import HTMLReportExporter
from app.reporting.markdown_exporter import MarkdownReportExporter
from app.scoring.engine import RiskScoringEngine
from app.services.correlation_models import RELATIONSHIP_THREAT_INTEL_LINK
from app.services.correlation_service import CorrelationService
from app.services.risk_explanation_service import RiskExplanationService

try:
    from app.reporting.pdf_exporter import PDFReportExporter

    PDF_EXPORTER_AVAILABLE = True
except ImportError:
    PDF_EXPORTER_AVAILABLE = False


MALICIOUS_IP = "203.0.113.99"
MALICIOUS_DOMAIN = "definitely-evil.example"
MALICIOUS_URL = "https://definitely-evil.example/dropper.exe"


def _no_hash_threat_intelligence() -> dict:
    """
    Threat intelligence with NO malicious/present SHA256 hash, but
    a malicious IPv4, domain, and URL.
    """

    return {
        "status": "ok",
        "hashes": [],
        "ips": [
            {
                "ip": MALICIOUS_IP,
                "verdict": "Malicious",
                "malicious": 12,
                "suspicious": 0,
                "detection_ratio": "12/70",
            }
        ],
        "domains": [
            {
                "domain": MALICIOUS_DOMAIN,
                "verdict": "Malicious",
                "malicious": 9,
                "suspicious": 0,
                "detection_ratio": "9/70",
            }
        ],
        "urls": [
            {
                "url": MALICIOUS_URL,
                "verdict": "Malicious",
                "malicious": 20,
                "suspicious": 0,
                "detection_ratio": "20/70",
            }
        ],
        "coverage": {
            "status": "ok",
            "requested": 3,
            "succeeded": 3,
            "failed": 0,
            "skipped_invalid": 0,
            "rate_limited": False,
            "invalid_api_key": False,
        },
    }


def _make_investigation() -> Investigation:
    return Investigation(
        report_name="no_hash_malicious_report.txt",
        iocs={
            "ipv4": [MALICIOUS_IP],
            "domains": [MALICIOUS_DOMAIN],
            "urls": [MALICIOUS_URL],
        },
        threat_intelligence=_no_hash_threat_intelligence(),
        risk_score=0,
        severity="LOW",
        confidence=0.0,
        ioc_score=0,
        threat_intel_score=0,
        cve_score=0,
        analyzed_at=datetime.now(UTC),
        investigation_id=99,
    )


@pytest.fixture()
def investigation() -> Investigation:
    return _make_investigation()


# --------------------------------------------------------------------
# A. SCORING
# --------------------------------------------------------------------


def test_a_scoring_non_hash_malicious_produces_nonzero_ti_contribution(
    investigation,
):
    engine = RiskScoringEngine()

    result = engine.calculate(
        investigation.iocs,
        investigation.threat_intelligence,
    )

    assert result.threat_intel_score > 0
    assert result.score > 0


# --------------------------------------------------------------------
# B. CORRELATION
# --------------------------------------------------------------------


def test_b_correlation_creates_ti_link_for_non_hash_indicators(investigation):
    service = CorrelationService()

    report = service.correlate(investigation)

    links = [
        r
        for r in report.results
        if r.relationship_type == RELATIONSHIP_THREAT_INTEL_LINK
    ]

    # One link each for the malicious IP, domain, and URL.
    assert len(links) == 3
    assert all("Malicious" in link.reason for link in links)


# --------------------------------------------------------------------
# C. RISK EXPLANATION
# --------------------------------------------------------------------


def test_c_risk_explanation_recognizes_malicious_non_hash_indicators(
    investigation,
):
    # Run scoring first so the explanation is being asked to explain
    # a score that actually reflects the non-hash TI contribution,
    # matching how the real pipeline (app/analyzer.py) wires these
    # services together.
    engine = RiskScoringEngine()
    risk_score = engine.calculate(
        investigation.iocs,
        investigation.threat_intelligence,
    )

    investigation.risk_score = risk_score.score
    investigation.severity = risk_score.severity
    investigation.confidence = risk_score.confidence
    investigation.ioc_score = risk_score.ioc_score
    investigation.threat_intel_score = risk_score.threat_intel_score
    investigation.cve_score = risk_score.cve_score

    correlation_report = CorrelationService().correlate(investigation)

    explanation = RiskExplanationService().explain(
        investigation,
        correlation_report=correlation_report,
        api_key_configured=True,
    )

    assert explanation.threat_intel_state == "enriched"
    assert explanation.threat_intel_malicious_hash_count == 3
    assert explanation.threat_intel_suspicious_hash_count == 0


# --------------------------------------------------------------------
# D. GUI DISPLAY / E. GUI SELECTION
# --------------------------------------------------------------------


def test_d_gui_workspace_ti_section_displays_non_hash_records(qapp, investigation):
    workspace = InvestigationWorkspacePage()

    workspace.load_investigation(investigation)

    table = workspace._threat_summary_widget._table

    assert table.rowCount() == 3

    type_labels = {table.item(row, 1).text() for row in range(table.rowCount())}

    assert type_labels == {"IPv4", "Domain", "URL"}


def test_e_gui_non_hash_indicator_can_be_selected(qapp, investigation):
    workspace = InvestigationWorkspacePage()

    workspace.load_investigation(investigation)

    assert workspace._threat_summary_widget.select_indicator(MALICIOUS_IP) is True
    assert (
        workspace._threat_summary_widget.select_indicator(MALICIOUS_DOMAIN) is True
    )
    assert workspace._threat_summary_widget.select_indicator(MALICIOUS_URL) is True

    # The drill-down entry point used by the rest of the workspace
    # (IOC details -> Threat Intelligence tab) must also work for a
    # non-hash indicator.
    workspace._on_threat_intel_requested(MALICIOUS_URL)

    assert workspace._tab_widget.currentIndex() == workspace._TAB_THREAT_INTEL
    assert workspace._threat_summary_widget._table.currentRow() != -1


# --------------------------------------------------------------------
# F. HTML / G. MARKDOWN / H. PDF
# --------------------------------------------------------------------


def test_f_html_report_includes_non_hash_ti(investigation, tmp_path):
    report = ReportBuilder.build(investigation)
    output_path = tmp_path / "acceptance.html"

    HTMLReportExporter.export(report, output_path)
    content = output_path.read_text(encoding="utf-8")

    assert MALICIOUS_IP in content
    assert MALICIOUS_DOMAIN in content
    assert MALICIOUS_URL in content


def test_g_markdown_report_includes_non_hash_ti(investigation, tmp_path):
    report = ReportBuilder.build(investigation)
    output_path = tmp_path / "acceptance.md"

    MarkdownReportExporter.export(report, output_path)
    content = output_path.read_text(encoding="utf-8")

    assert MALICIOUS_IP in content
    assert MALICIOUS_DOMAIN in content
    assert MALICIOUS_URL in content


@pytest.mark.skipif(
    not PDF_EXPORTER_AVAILABLE, reason="PDF exporter dependency unavailable"
)
def test_h_pdf_report_includes_non_hash_ti(investigation, tmp_path):
    pypdf = pytest.importorskip("pypdf")

    report = ReportBuilder.build(investigation)
    output_path = tmp_path / "acceptance.pdf"

    PDFReportExporter.export(report, output_path)

    assert output_path.exists()
    assert output_path.stat().st_size > 0

    reader = pypdf.PdfReader(str(output_path))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)

    assert MALICIOUS_IP in text
    assert MALICIOUS_DOMAIN in text
    # The URL column is truncated to 24 chars + "..." in the PDF
    # table, so check the truncated prefix instead of the full URL.
    assert MALICIOUS_URL[:24] in text
