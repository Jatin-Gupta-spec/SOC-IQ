"""
HTML exporter for SOC-IQ.

Exports an InvestigationReport as a
professional HTML report.
"""

from __future__ import annotations

from html import escape
from pathlib import Path

from app.reporting.models import InvestigationReport

import json

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

        try:
            html = HTMLReportExporter._build_html(
                report,
            )

            output_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            output_path.write_text(
                html,
                encoding="utf-8",
            )

            return output_path

        except OSError as error:
            raise RuntimeError(
                f"Failed to export HTML report: {error}"
            ) from error

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
    <tr
        class="clickable-row"
        data-ioc-type="{ioc_type}"
    >
    <td>{escape(ioc_type.replace("_", " ").title())}</td>
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
        <tr class="clickable-threat-row">
        <td>{escape(item.get("sha256", ""))}</td>
       <td>{escape(item.get("verdict", "Unknown"))}</td>
       <td>{escape(str(item.get("detection_ratio", "N/A")))}</td>
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

        return "".join(rows)

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

        generated_at = str(report.analyzed_at)

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
        elif report.risk_score < 60:
            risk_class = "risk-medium"
        elif report.risk_score < 80:
            risk_class = "risk-high"
        else:
            risk_class = "risk-critical"

        ioc_labels = json.dumps(
            [
                ioc_type.replace("_", " ").title()
                for ioc_type in report.iocs
            ]
        )

        ioc_counts = json.dumps(
            [
                len(values)
                for values in report.iocs.values()
            ]
        )

        ioc_data = json.dumps(
            report.iocs,
            ensure_ascii=False,
        )

        status_class = {
            "COMPLETED": "status-success",
            "FAILED": "status-danger",
            "PENDING": "status-warning",
        }.get(
            report.status.upper(),
            "",
        )

        return f"""<!DOCTYPE html>
        

        <html lang="en">

        <head>

        <meta charset="UTF-8">

        <meta
            name="viewport"
            content="width=device-width, initial-scale=1.0"
        >

        <meta
            name="author"
            content="SOC-IQ"
        >

        <meta
            name="generator"
            content="SOC-IQ Investigation Report"
        >

        <meta
            name="description"
            content="Cybersecurity Investigation Report"
        >

       <title>
        SOC-IQ - {escape(report.report_name)}
        </title>

        <link
            rel="icon"
            href="soc_iq.ico"
            type="image/x-icon"
        >

        <style>

        body {{
            font-family: "Segoe UI", Arial, Helvetica, sans-serif;
            background: #0f172a;
            color: #e2e8f0;
            margin: 0;
            padding: 40px;
        }}

        .page {{
            display: flex;
            justify-content: center;
        }}

        .container {{
            width: 100%;
            max-width: 1200px;
            background: #1e293b;
            border-radius: 14px;
            padding: 40px;
            box-shadow: 0 10px 35px rgba(0,0,0,0.45);
        }}

        .report-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 35px;
            padding-bottom: 20px;
            border-bottom: 2px solid #334155;
        }}

        .report-brand h1 {{
            margin: 0;
            border: none;
            padding: 0;
        }}

        .report-brand p {{
            margin-top: 8px;
            color: #94a3b8;
            font-size: 14px;
        }}

        .report-meta {{
            text-align: right;
            color: #94a3b8;
            font-size: 14px;
        }}

        .report-meta strong {{
            color: #f8fafc;
        }}

        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 18px;
            margin: 30px 0;
        }}

        .summary-card {{
            background: #0f172a;
            border: 1px solid #334155;
            border-radius: 12px;
            padding: 22px;
            text-align: center;
            transition: transform 0.2s ease,
                        box-shadow 0.2s ease;
        }}

        .summary-card:hover {{
            transform: translateY(-4px);
            box-shadow: 0 8px 20px rgba(0,0,0,0.35);
        }}

        .summary-title {{
            color: #94a3b8;
            font-size: 13px;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 10px;
        }}

        .summary-value {{
            color: #38bdf8;
            font-size: 28px;
            font-weight: 700;
        }}

        .badge {{
            display: inline-block;
            padding: 8px 18px;
            border-radius: 999px;
            font-size: 13px;
            font-weight: 700;
            letter-spacing: 0.8px;
            text-transform: uppercase;
        }}

        .badge-low {{
            background: #14532d;
            color: #86efac;
        }}

        .badge-medium {{
            background: #78350f;
            color: #fde68a;
        }}

        .badge-high {{
            background: #7c2d12;
            color: #fdba74;
        }}

        .badge-critical {{
            background: #7f1d1d;
            color: #fca5a5;
        }}

        .risk-low {{
            color: #22c55e;
        }}

        .risk-medium {{
            color: #facc15;
        }}

        .risk-high {{
            color: #fb923c;
        }}

        .risk-critical {{
            color: #ef4444;
        }}

        .details-panel {{
            background: #0f172a;
            border: 1px solid #334155;
            border-radius: 12px;
            overflow: hidden;
        }}

        .detail-row {{
            display: flex;
            justify-content: space-between;
            padding: 14px 20px;
            border-bottom: 1px solid #334155;
        }}

        .detail-row:last-child {{
            border-bottom: none;
        }}

        .detail-label {{
            color: #94a3b8;
            font-weight: 600;
        }}

        .detail-value {{
            color: #f8fafc;
        }}

        h1 {{
            margin: 0;
            padding-bottom: 18px;
            font-size: 34px;
            font-weight: 700;
            color: #38bdf8;
            border-bottom: 2px solid #334155;
            letter-spacing: 1px;
        }}

        .section {{
            margin-top: 30px;
        }}

        h2 {{
            margin-bottom: 18px;
            color: #f8fafc;
            font-size: 22px;
            font-weight: 600;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            overflow: hidden;
            border-radius: 10px;
            background: #0f172a;
        }}

        th,
        td {{
            padding: 14px 18px;
            text-align: left;
            border-bottom: 1px solid #334155;
        }}

        th {{
            background: #2563eb;
            color: white;
            font-weight: 600;
            text-transform: uppercase;
            font-size: 13px;
            letter-spacing: 0.8px;
        }}

        tr {{
            transition: background-color 0.2s ease;
        }}

        tbody tr:hover {{
            background: #1e293b;
        }}

        .clickable-row {{
            cursor: pointer;
            transition: background-color 0.2s ease;
        }}

        .clickable-row:hover {{
            background: #334155;
        }}

        .clickable-threat-row {{
            cursor: pointer;
        }}

        .clickable-threat-row:hover {{
            background: #334155;
        }}

        .search-box {{
            width: 100%;
            box-sizing: border-box;
            margin-bottom: 16px;
            padding: 12px 16px;

            background: #0f172a;
            color: #e2e8f0;

            border: 1px solid #334155;
            border-radius: 8px;

            font-size: 14px;

            transition:
                border-color 0.2s ease,
                box-shadow 0.2s ease;
        }}

        .search-box:focus {{
            outline: none;
            border-color: #38bdf8;
            box-shadow: 0 0 0 3px rgba(56, 189, 248, 0.25);
        }}

        .search-box::placeholder {{
            color: #94a3b8;
        }}

        .no-results {{
            display: none;
            margin-bottom: 16px;
            color: #94a3b8;
            font-style: italic;
        }}

        .ioc-details-panel {{
            margin-top: 20px;
            padding: 20px;
            background: #0f172a;
            border: 1px solid #334155;
            border-radius: 10px;
        }}

        .ioc-details-panel h3 {{
            margin-top: 0;
            color: #38bdf8;
        }}

        .ioc-details-panel p {{
            color: #94a3b8;
            margin-bottom: 0;
        }}

        .ioc-details-panel ul {{
            margin: 10px 0 0;
            padding-left: 20px;
        }}

        .ioc-details-panel li {{
            margin-bottom: 6px;
            color: #e2e8f0;
            word-break: break-word;
        }}

        .footer {{
            margin-top: 50px;
            padding-top: 20px;
            border-top: 1px solid #334155;
            text-align: center;
            color: #94a3b8;
            font-size: 13px;
            line-height: 1.8;
        }}

        .footer strong {{
            color: #38bdf8;
        }}

        td {{
            color: #e2e8f0;
        }}

        .status-success {{
            color: #22c55e;
        }}

        .status-warning {{
            color: #facc15;
        }}

        .status-danger {{
            color: #ef4444;
        }}
        
        .chart-container {{
            height: 350px;
            margin-top: 20px;
        }}

        </style>

        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

        </head>

        <body>

        <div class="page">

        <div class="container">

        <div class="report-header">

        <div class="report-brand">

        <h1>SOC-IQ</h1>

        <p>
        Security Operations & Intelligence Platform
        </p>

        </div>

        <div class="report-meta">

        <div>
        <strong>Version:</strong> 1.0.0
        </div>

        <div>
        <strong>Generated:</strong>
        {generated_at}
        </div>

        </div>

        </div>

        <div class="summary-grid">

        <div class="summary-card">
        <div class="summary-title">
        Risk Score
        </div>

        <div class="summary-value {risk_class}">
        {report.risk_score}
        </div>

        </div>

        <div class="summary-card">
        <div class="summary-title">
        Severity
        </div>

        <div class="summary-value">

        <span class="badge {severity_class}">
        {escape(report.severity)}
        </span>

        </div>

        </div>

        <div class="summary-card">
        <div class="summary-title">
        Confidence
        </div>
        <div class="summary-value">
        {report.confidence * 100:.0f}%
        </div>
        </div>

        <div class="summary-card">
        <div class="summary-title">
        Status
        </div>
       <div class="summary-value {status_class}">
            {escape(report.status)}
        </div>
        </div>

        </div>

        <div class="section">

        <h2>Investigation Details</h2>

        <div class="details-panel">

        <div class="detail-row">
        <span class="detail-label">Report Name</span>
        <span class="detail-value">
        {escape(report.report_name)}
        </span>
        </div>

        <div class="detail-row">
        <span class="detail-label">Analyzed At</span>
        <span class="detail-value">
        {generated_at}
        </span>
        </div>

        <div class="detail-row">
        <span class="detail-label">IOC Score</span>
        <span class="detail-value">{report.ioc_score}</span>
        </div>

        <div class="detail-row">
        <span class="detail-label">Threat Intelligence Score</span>
        <span class="detail-value">{report.threat_intel_score}</span>
        </div>

        <div class="detail-row">
        <span class="detail-label">CVE Score</span>
        <span class="detail-value">{report.cve_score}</span>
        </div>

        </div>

        </div>

        <div class="section">

        <h2>IOC Distribution</h2>

        <div class="chart-container">

        <canvas id="iocChart"></canvas>

        </div>

        </div>

        <div class="section">

        <h2>IOC Summary</h2>

        <input
            id="iocSearch"
            type="text"
            placeholder="Search IOC types..."
            class="search-box"
        >

        <p
            id="noResultsMessage"
            class="no-results"
            style="display: none;"
        >
            No matching IOC types found.
        </p>

        <table>

        <thead>

        <tr>
        <th>IOC Type</th>
        <th>Count</th>
        </tr>

        </thead>

        <tbody>

        {ioc_summary}

        </tbody>

        </table>

        <div
            id="iocDetails"
            class="ioc-details-panel"
        >
            <h3>IOC Details</h3>

            <p>
                Click an IOC type above to view its values.
            </p>
        </div>

        </div>

        <div class="section">

        <h2>Threat Intelligence Summary</h2>

        <table>

        <thead>

        <tr>
        <th>SHA256</th>
        <th>Verdict</th>
        <th>Detection Ratio</th>
        </tr>

        </thead>

        <tbody>

        {threat_summary}

        </tbody>

        </table>

        </div>

        <div class="footer">

        <strong>SOC-IQ</strong><br>

        Security Operations & Intelligence Platform<br>

        Version 1.0.0<br>

        Generated automatically by SOC-IQ.<br>

        Generated on:
        {generated_at}<br>

        Confidential - For authorized personnel only.

        </div>

        </div>

        </div>

        <script>

        function escapeHtml(text) {{

            const div = document.createElement(
                "div"
            );

            div.textContent = text;

            return div.innerHTML;

        }}

        const labels = {ioc_labels};

        const counts = {ioc_counts};

        const iocData = {ioc_data};

        const canvas = document.getElementById(
            "iocChart"
        );

        if (canvas) {{
        
                const context = canvas.getContext(
            "2d"
        );

        const gradient = context.createLinearGradient(
            0,
            0,
            0,
            400,
        );

        gradient.addColorStop(
            0,
            "#38bdf8",
        );

        gradient.addColorStop(
            1,
            "#2563eb",
        );

            new Chart(
                canvas,
                {{
                    type: "bar",

                    data: {{
                        labels: labels,

                        datasets: [
                            {{
                                label: "IOC Count",

                                data: counts,

                                backgroundColor: gradient,

                                borderColor: "#0ea5e9",

                                borderWidth: 1,

                                borderRadius: 6,

                                hoverBackgroundColor: "#60a5fa",

                                hoverBorderColor: "#93c5fd",

                                hoverBorderWidth: 2,
                            }},
                        ],
                    }},

                    options: {{
                        responsive: true,

                        maintainAspectRatio: false,

                        animation: {{
                            duration: 1000,
                            easing: "easeOutQuart",
                        }},

                        plugins: {{
                            legend: {{
                                display: false,
                            }},

                            tooltip: {{
                                backgroundColor: "#0f172a",

                                titleColor: "#f8fafc",

                                bodyColor: "#e2e8f0",

                                borderColor: "#38bdf8",

                                borderWidth: 1,

                                padding: 12,

                                displayColors: false,

                                callbacks: {{
                                    label: function(context) {{
                                        return "Count: " + context.raw;
                                    }}
                                }}
                            }},
                        }},

                        scales: {{
                            x: {{
                                ticks: {{
                                    color: "#e2e8f0",
                                }},

                                grid: {{
                                    color: "#334155",
                                }},
                            }},

                            y: {{
                                beginAtZero: true,

                                ticks: {{
                                    color: "#e2e8f0",
                                    precision: 0,
                                }},

                                grid: {{
                                    color: "#334155",
                                }},
                            }},
                        }},
                    }},
                }}
            );

        }}

        const rows = document.querySelectorAll(".clickable-row");

        const detailsPanel =
            document.getElementById("iocDetails");

        rows.forEach((row) => {{

            row.onclick = function () {{

                const iocType =
                    row.dataset.iocType;

                const values =
                    iocData[iocType] || [];

                let html =
                    "<h3>IOC Details</h3>";

                html +=
                    "<strong>" +
                    escapeHtml(
                        iocType
                            .replaceAll("_", " ")
                            .replace(
                                /\b\w/g,
                                (character) => character.toUpperCase()
                            )
                    ) +
                    "</strong>";

                if (values.length === 0) {{

                    html +=
                        "<p>No IOC values available.</p>";

                }}
                else {{

                    html += "<ul>";

                    values.forEach((value) => {{

                        html +=
                            "<li>" +
                            escapeHtml(value) +
                            "</li>";

                    }});

                    html += "</ul>";
                }}

                detailsPanel.innerHTML = html;

            }};

        }});

        const searchBox = document.getElementById(
            "iocSearch"
        );

        const noResultsMessage = document.getElementById(
            "noResultsMessage"
        );

        searchBox.addEventListener(
            "input",
            function () {{

                const filter = this.value
                    .toLowerCase()
                    .trim();

                let visibleRows = 0;

                rows.forEach((row) => {{

                    const text = row.textContent
                        .toLowerCase();

                    if (text.includes(filter)) {{
                        row.style.display = "";
                        visibleRows++;
                    }}
                    else {{
                        row.style.display = "none";
                    }}

                }});

                if (visibleRows === 0) {{
                    noResultsMessage.style.display = "block";
                }}
                else {{
                    noResultsMessage.style.display = "none";
                }}

            }}
        );

        const threatRows =
            document.querySelectorAll(
                ".clickable-threat-row"
            );

        threatRows.forEach((row) => {{
            row.onclick = function () {{
                alert(
                    "Detailed Threat Intelligence view will be available in a future SOC-IQ release."
                );
            }};
        }});

        </script>

        </body>

        </html>
        """