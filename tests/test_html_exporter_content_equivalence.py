"""
Phase 4L-P2: content-equivalence regression tests for the Jinja2-based
HTML exporter.

These lock in the structural/content guarantees verified against the
pre-refactor (hand-built-string) HTML exporter during the P2 audit:
same IOC/threat-intel table rows (including the `data-*` attributes
the report's client-side JS relies on), same embedded Chart.js JSON
data, same escaping behavior, and the same empty-state messaging.
Unlike `tests/test_reporting.py`'s substring checks, these assert on
row *structure*, not just presence of a value somewhere in the page.
"""

from __future__ import annotations

import json
import re

from app.reporting.html_exporter import HTMLReportExporter
from app.reporting.models import InvestigationReport


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
                {"sha256": "a" * 64, "verdict": "Malicious", "detection_ratio": "10/70"}
            ],
            "ips": [
                {"ip": "203.0.113.7", "verdict": "Malicious", "detection_ratio": "8/70"}
            ],
            "domains": [
                {"domain": "evilcorp.example", "verdict": "Suspicious", "detection_ratio": "4/70"}
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


def test_ioc_row_has_expected_data_attribute_and_label(tmp_path):
    report = make_report(
        iocs={"ipv4": ["1.2.3.4", "5.6.7.8"]},
        threat_intelligence={"status": "ok", "hashes": []},
    )
    output_path = tmp_path / "report.html"

    HTMLReportExporter.export(report, output_path)
    content = output_path.read_text(encoding="utf-8")

    # The clickable row's data-ioc-type must carry the *raw* key
    # (used by client JS to look up ioc_data), while the visible <td>
    # shows the humanized label -- these are deliberately different.
    assert 'data-ioc-type="ipv4"' in content
    assert "<td>Ipv4</td>" in content
    assert "<td>2</td>" in content


def test_threat_row_carries_all_four_data_attributes(tmp_path):
    report = make_report()
    output_path = tmp_path / "report.html"

    HTMLReportExporter.export(report, output_path)
    content = output_path.read_text(encoding="utf-8")

    assert f'data-indicator="{"a" * 64}"' in content
    assert 'data-type="SHA256"' in content
    assert 'data-verdict="Malicious"' in content
    assert 'data-detection="5/70"' in content


def test_multi_type_ti_rows_preserve_category_order(tmp_path):
    report = make_multi_type_ti_report()
    output_path = tmp_path / "multi.html"

    HTMLReportExporter.export(report, output_path)
    content = output_path.read_text(encoding="utf-8")

    # hashes, ips, domains, urls -- same order _TI_CATEGORIES defines.
    hash_idx = content.find("a" * 64)
    ip_idx = content.find("203.0.113.7")
    domain_idx = content.find("evilcorp.example")
    url_idx = content.find("evilcorp.example/payload.exe")

    assert hash_idx < ip_idx < domain_idx < url_idx


def test_empty_threat_intelligence_uses_colspan_four_message(tmp_path):
    report = make_report(iocs={}, threat_intelligence={})
    output_path = tmp_path / "empty.html"

    HTMLReportExporter.export(report, output_path)
    content = output_path.read_text(encoding="utf-8")

    assert '<td colspan="4">' in content
    assert "No threat intelligence available." in content


def test_ioc_type_names_escaped_in_both_attribute_and_text(tmp_path):
    report = make_report(
        iocs={"<script>alert(1)</script>": ["x"]},
        threat_intelligence={"status": "ok", "hashes": []},
    )
    output_path = tmp_path / "xss.html"

    HTMLReportExporter.export(report, output_path)
    content = output_path.read_text(encoding="utf-8")

    assert "<script>alert(1)</script>" not in content
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in content


def test_embedded_chart_json_matches_ioc_data(tmp_path):
    iocs = {"ipv4": ["1.2.3.4"], "sha256": ["a" * 64, "b" * 64]}
    report = make_report(iocs=iocs, threat_intelligence={"status": "ok", "hashes": []})
    output_path = tmp_path / "chart.html"

    HTMLReportExporter.export(report, output_path)
    content = output_path.read_text(encoding="utf-8")

    labels_match = re.search(r"const labels = (.*?);", content)
    counts_match = re.search(r"const counts = (.*?);", content)
    data_match = re.search(r"const iocData = (.*?);", content)

    assert json.loads(labels_match.group(1)) == ["Ipv4", "Sha256"]
    assert json.loads(counts_match.group(1)) == [1, 2]
    assert json.loads(data_match.group(1)) == iocs


def test_confidence_percent_rounds_same_as_pre_refactor_format_spec(tmp_path):
    # 0.845 * 100 = 84.5 -> Python's "{:.0f}" banker's-rounds this to
    # "84" (round-half-to-even), same as the pre-refactor f-string did.
    report = make_report(confidence=0.845)
    output_path = tmp_path / "confidence.html"

    HTMLReportExporter.export(report, output_path)
    content = output_path.read_text(encoding="utf-8")

    assert "84%" in content
