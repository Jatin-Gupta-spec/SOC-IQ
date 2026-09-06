"""
HTML exporter for SOC-IQ.

Exports an InvestigationReport as a professional HTML report.

Architecture (Phase 4L-P2): the previous implementation hand-built the
entire HTML/CSS/JS document as Python f-strings (1,861 LOC). This module
now does only data assembly -- turning an `InvestigationReport` into a
plain template context -- and delegates all presentation markup to the
Jinja2 template at `app/reporting/templates/report.html.j2`. Report
content, structure, and behavior are unchanged; only how the HTML is
produced has changed.
"""

from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.reporting.atomic_write import atomic_write
from app.reporting.models import InvestigationReport

_TEMPLATE_DIR = Path(__file__).parent / "templates"

# HTML autoescaping is always on: every value interpolated into the
# template via `{{ ... }}` is escaped unless explicitly marked `|safe`.
# Only the pre-serialized JSON blobs handed to the inline <script> are
# marked safe (see `_build_context`) -- everything else in the template
# relies on this environment's autoescaping instead of the previous
# manual `html.escape()` calls.
_ENV = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(
        enabled_extensions=("html", "j2"),
        default_for_string=True,
    ),
    trim_blocks=True,
    lstrip_blocks=True,
)

_TEMPLATE = _ENV.get_template("report.html.j2")


class HTMLReportExporter:
    """
    Exports InvestigationReport objects
    as HTML files.
    """

    # Canonical mapping of each enrichable TI category (as stored on
    # `report.threat_intelligence`) to the record field holding the
    # indicator's value and a display label for the "Type" column.
    # Hashes stay first so existing hash-only reports render
    # identically to before Phase 3E (see `_build_context`).
    _TI_CATEGORIES: tuple[tuple[str, str, str], ...] = (
        ("hashes", "sha256", "SHA256"),
        ("ips", "ip", "IPv4"),
        ("domains", "domain", "Domain"),
        ("urls", "url", "URL"),
    )

    @staticmethod
    def export(
        report: InvestigationReport,
        output_path: Path,
    ) -> Path:
        """
        Export an investigation report to HTML.

        MAX-21B-3 Part 2: written atomically via `atomic_write` (see
        `json_exporter.py` for the rationale) -- closes MAX-21A F3
        for the HTML format.

        Returns:
            Path to the generated HTML file.
        """

        try:
            context = HTMLReportExporter._build_context(report)

            html = _TEMPLATE.render(**context)

            def _write(tmp_path: Path) -> None:
                tmp_path.write_text(
                    html,
                    encoding="utf-8",
                )

            atomic_write(output_path, _write)

            return output_path

        except OSError as error:
            raise RuntimeError(
                f"Failed to export HTML report: {error}"
            ) from error

    @staticmethod
    def _build_ioc_rows(
        report: InvestigationReport,
    ) -> list[dict[str, object]]:
        """
        Build the presentation-facing rows for the IOC summary table,
        one per IOC type, in `report.iocs`' own (insertion) order --
        identical iteration order to the pre-refactor implementation.
        """

        return [
            {
                "raw_type": ioc_type,
                "label": ioc_type.replace("_", " ").title(),
                "count": len(values),
            }
            for ioc_type, values in report.iocs.items()
        ]

    @staticmethod
    def _build_threat_rows(
        report: InvestigationReport,
    ) -> list[dict[str, str]]:
        """
        Build the presentation-facing rows for the Threat Intelligence
        summary table, spanning all four TI categories in
        `_TI_CATEGORIES` order (hashes, ips, domains, urls) -- the same
        order and flattening the pre-refactor implementation used.
        """

        rows: list[dict[str, str]] = []

        for category, value_field, type_label in (
            HTMLReportExporter._TI_CATEGORIES
        ):
            records = (
                report.threat_intelligence.get(category, [])
                or []
            )

            for item in records:
                value = item.get(value_field, "")

                rows.append(
                    {
                        "value": str(value),
                        "type_label": type_label,
                        "verdict": item.get("verdict", "Unknown"),
                        "detection": str(
                            item.get("detection_ratio", "N/A")
                        ),
                    }
                )

        return rows

    @staticmethod
    def _build_context(
        report: InvestigationReport,
    ) -> dict[str, object]:
        """
        Assemble the Jinja2 template context for `report`.

        This is the slim data-assembly layer the template renders
        from -- it prepares presentation-facing values (badge/risk
        classes, formatted percentages, table rows) but performs no
        aggregation beyond what the pre-refactor `_build_html` /
        `_build_ioc_summary` / `_build_threat_summary` already did.
        """

        generated_at = str(report.analyzed_at)

        version = "1.0.0"

        severity_class = {
            "LOW": "badge-low",
            "MEDIUM": "badge-medium",
            "HIGH": "badge-high",
            "CRITICAL": "badge-critical",
        }.get(
            report.severity.upper(),
            "badge-medium",
        )

        if report.risk_score < 30:
            risk_class = "risk-low"
            risk_label = "Low Risk"
        elif report.risk_score < 60:
            risk_class = "risk-medium"
            risk_label = "Medium Risk"
        elif report.risk_score < 80:
            risk_class = "risk-high"
            risk_label = "High Risk"
        else:
            risk_class = "risk-critical"
            risk_label = "Critical Risk"

        status_class = {
            "COMPLETED": "status-success",
            "FAILED": "status-danger",
            "PENDING": "status-warning",
        }.get(
            report.status.upper(),
            "",
        )

        confidence_percent = f"{report.confidence * 100:.0f}"

        investigation_id_display = (
            str(report.investigation_id)
            if report.investigation_id is not None
            else "N/A"
        )

        ioc_rows = HTMLReportExporter._build_ioc_rows(report)
        threat_rows = HTMLReportExporter._build_threat_rows(report)

        threat_entries_count = sum(
            len(report.threat_intelligence.get(category, []) or [])
            for category, _, _ in HTMLReportExporter._TI_CATEGORIES
        )

        # JSON blobs consumed by the inline <script> (Chart.js data +
        # per-IOC-type value lookup). These are marked `|safe` in the
        # template because they are JSON/JS literals, not HTML -- the
        # `</` escape below (unchanged from the pre-refactor
        # implementation) keeps a literal "</script>" inside IOC/TI
        # data from prematurely closing the surrounding <script> tag.
        ioc_labels_json = json.dumps(
            [row["label"] for row in ioc_rows]
        )

        ioc_counts_json = json.dumps(
            [row["count"] for row in ioc_rows]
        )

        ioc_data_json = (
            json.dumps(
                report.iocs,
                ensure_ascii=False,
            )
            .replace("</", "<\\/")
        )

        return {
            "report": report,
            "generated_at": generated_at,
            "version": version,
            "severity_class": severity_class,
            "risk_class": risk_class,
            "risk_label": risk_label,
            "status_class": status_class,
            "confidence_percent": confidence_percent,
            "investigation_id_display": investigation_id_display,
            "ioc_rows": ioc_rows,
            "threat_rows": threat_rows,
            "ioc_type_count": len(ioc_rows),
            "total_ioc_count": sum(row["count"] for row in ioc_rows),
            "threat_entries_count": threat_entries_count,
            "ioc_labels_json": ioc_labels_json,
            "ioc_counts_json": ioc_counts_json,
            "ioc_data_json": ioc_data_json,
        }
