"""
HTML exporter for SOC-IQ.

Exports an InvestigationReport as a
professional HTML report.
"""

from __future__ import annotations

from pathlib import Path

from app.reporting.models import InvestigationReport


class HTMLReportExporter:
    """
    Exports InvestigationReport objects
    as HTML files.
    """

    @staticmethod
    def export(
        report: InvestigationReport,
        output_path: Path,
    ) -> Path:
        """
        Export an investigation report to HTML.

        Returns:
            Path to the generated HTML file.
        """

        html = HTMLReportExporter._build_html(
            report,
        )

        output_path.write_text(
            html,
            encoding="utf-8",
        )

        return output_path

    @staticmethod
    def _build_ioc_summary(
        report: InvestigationReport,
    ) -> str:
        """
        Build the IOC summary table.
        """

        rows: list[str] = []

        for ioc_type, values in report.iocs.items():

            rows.append(
                f"""
<tr>
<td>{ioc_type.replace("_", " ").title()}</td>
<td>{len(values)}</td>
</tr>
"""
            )

        return "".join(
            rows,
        )

    @staticmethod
    def _build_threat_summary(
        report: InvestigationReport,
    ) -> str:
        """
        Build the Threat Intelligence summary table.
        """

        rows: list[str] = []

        hashes = (
            report.threat_intelligence.get(
                "hashes",
                [],
            )
        )

        for item in hashes:

            rows.append(
                f"""
<tr>
<td>{item.get("sha256", "")}</td>
<td>{item.get("verdict", "Unknown")}</td>
<td>{item.get("detection_ratio", "N/A")}</td>
</tr>
"""
            )

        if not rows:

            rows.append(
                """
<tr>
<td colspan="3">
No threat intelligence available.
</td>
</tr>
"""
            )

        return "".join(
            rows,
        )

    @staticmethod
    def _build_html(
        report: InvestigationReport,
    ) -> str:
        """
        Build the HTML document.
        """

        ioc_summary = (
            HTMLReportExporter._build_ioc_summary(
                report,
            )
        )

        threat_summary = (
            HTMLReportExporter._build_threat_summary(
                report,
            )
        )

        return f"""<!DOCTYPE html>
<html lang="en">

<head>

<meta charset="UTF-8">

<title>SOC-IQ Investigation Report</title>

<style>

body {{
    font-family: Arial, Helvetica, sans-serif;
    background: #f4f6f8;
    color: #222;
    margin: 40px;
}}

.container {{
    background: white;
    border-radius: 10px;
    padding: 30px;
    box-shadow: 0 0 12px rgba(0,0,0,0.15);
}}

h1 {{
    color: #1f4e79;
    border-bottom: 2px solid #ddd;
    padding-bottom: 10px;
}}

.section {{
    margin-top: 25px;
}}

table {{
    width: 100%;
    border-collapse: collapse;
}}

th,
td {{
    border: 1px solid #ccc;
    padding: 10px;
    text-align: left;
}}

th {{
    background: #1f4e79;
    color: white;
}}

</style>

</head>

<body>

<div class="container">

<h1>SOC-IQ Investigation Report</h1>

<div class="section">

<h2>{report.report_name}</h2>

<table>

<tr>
<th>Report Name</th>
<td>{report.report_name}</td>
</tr>

<tr>
<th>Analyzed At</th>
<td>{report.analyzed_at}</td>
</tr>

<tr>
<th>Status</th>
<td>{report.status}</td>
</tr>

<tr>
<th>Severity</th>
<td>{report.severity}</td>
</tr>

<tr>
<th>Risk Score</th>
<td>{report.risk_score}</td>
</tr>

<tr>
<th>Confidence</th>
<td>{report.confidence * 100:.0f}%</td>
</tr>

<tr>
<th>IOC Score</th>
<td>{report.ioc_score}</td>
</tr>

<tr>
<th>Threat Intelligence Score</th>
<td>{report.threat_intel_score}</td>
</tr>

<tr>
<th>CVE Score</th>
<td>{report.cve_score}</td>
</tr>

</table>

</div>

<div class="section">

<h2>IOC Summary</h2>

<table>

<tr>
<th>IOC Type</th>
<th>Count</th>
</tr>

{ioc_summary}

</table>

</div>

<div class="section">

<h2>Threat Intelligence Summary</h2>

<table>

<tr>
<th>SHA256</th>
<th>Verdict</th>
<th>Detection Ratio</th>
</tr>

{threat_summary}

</table>

</div>

</div>

</body>

</html>
"""