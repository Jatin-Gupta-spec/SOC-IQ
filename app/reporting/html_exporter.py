"""
HTML exporter for SOC-IQ.

Exports an InvestigationReport as a
professional HTML report.
"""

from __future__ import annotations

from html import escape
from pathlib import Path
import shutil

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
        data-ioc-type="{escape(ioc_type)}"
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
        <tr
            class="clickable-threat-row"
            data-sha256="{escape(item.get('sha256', ''))}"
            data-verdict="{escape(item.get('verdict', 'Unknown'))}"
            data-detection="{escape(str(item.get('detection_ratio', 'N/A')))}"
        >
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

        generated_at = escape(str(report.analyzed_at))

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

        ioc_data = (
            json.dumps(
                report.iocs,
                ensure_ascii=False,
            )
            .replace("</", "<\\/")
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

        <style>

        body {{
            font-family: "Segoe UI", Arial, Helvetica, sans-serif;
            scroll-behavior: smooth;
            background:
                radial-gradient(circle at top left,
                #1e3a8a 0%,
                #0f172a 30%,
                #020617 100%);

            min-height:100vh;
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
            background:rgba(15,23,42,.82);
            border-radius:22px;
            padding: 40px;
            backdrop-filter:blur(18px);

            border:1px solid rgba(255,255,255,.08);

            box-shadow:
            0 25px 80px rgba(0,0,0,.45);

            animation: fadeIn .8s ease;
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

        .report-name {{
            margin: 10px 0 6px;
            color: #f8fafc;
            font-size: 20px;
            font-weight: 600;
            word-break: break-word;
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
            background:rgba(255,255,255,.03);
            border:1px solid #334155;
            border-radius: 12px;
            padding: 22px;
            text-align: center;

             opacity: 0;
            transform: translateY(25px);
            animation: cardFade .6s ease forwards;
            
            transition:
                transform .35s cubic-bezier(.2,.8,.2,1),
                box-shadow .35s cubic-bezier(.2,.8,.2,1),
                border-color .35s ease,
                background .35s ease;
            }}

            .summary-card:nth-child(1) {{
            animation-delay: .10s;
        }}

        .summary-card:nth-child(2) {{
            animation-delay: .20s;
        }}

        .summary-card:nth-child(3) {{
            animation-delay: .30s;
        }}

        .summary-card:nth-child(4) {{
            animation-delay: .40s;
        }}

        .summary-card:hover {{

            transform:
                translateY(-10px)
                scale(1.04);

            background:
                linear-gradient(
                    145deg,
                    rgba(37,99,235,.28),
                    rgba(15,23,42,.92)
                );

            border-color:#60a5fa;

            box-shadow:
                0 30px 70px rgba(37,99,235,.35);

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
            text-shadow:
                0 0 18px rgba(56,189,248,.45);
        }}

        .summary-subtitle {{
            margin-top: 8px;
            font-size: 12px;
            color: #94a3b8;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}

        .badge {{
            display: inline-block;
            padding: 8px 18px;
            border-radius: 999px;
            font-size: 13px;
            font-weight: 700;
            letter-spacing: 0.8px;
            text-transform: uppercase;
            transition:
                transform .3s ease,
                box-shadow .3s ease;
        }}

        .badge:hover {{

            transform: scale(1.08);

            box-shadow:
                0 0 20px rgba(255,255,255,.18);

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
            background:rgba(15,23,42,.65);
            backdrop-filter:blur(10px);
            border:1px solid rgba(255,255,255,.05);
            border-radius: 12px;
            overflow: hidden;
        }}

        .detail-row {{

            display: flex;

            justify-content: space-between;

            padding: 14px 20px;

            border-bottom: 1px solid #334155;

            transition:
                background .25s ease,
                padding-left .25s ease;

        }}

        .detail-row:hover {{

            background:#172554;

            padding-left:28px;

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

        .details-panel a {{

            display: block;
            width: 100%;

            color: #38bdf8;

            text-decoration: none;

            transition:
                color .25s ease,
                padding-left .25s ease;

        }}

        .details-panel a:hover {{

            color: white;

            padding-left: 12px;

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
            transition:
            transform .3s ease,
            box-shadow .3s ease;
        }}

        table:hover {{

            transform: translateY(-2px);

            box-shadow:
                0 15px 40px rgba(0,0,0,.30);

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

            background:
                linear-gradient(
                    90deg,
                    rgba(37,99,235,.25),
                    rgba(30,41,59,.95)
                );

            transition:
                background .25s ease,
                transform .25s ease;

        }}

        .clickable-row {{
            cursor: pointer;

            transition:
                background .25s ease,
                transform .25s ease;
        }}

        .clickable-row:hover {{

            background:#1e40af;

            transform:scale(1.01);

        }}

        .clickable-row.active {{
            background: #2563eb;
            color: white;
        }}

        .clickable-row.active td {{
            color: white;
        }}

        .clickable-threat-row {{
            cursor: pointer;
            transition:
                background .25s ease,
                transform .25s ease;
        }}

        .clickable-threat-row:hover {{

            background:#1e40af;

            transform:scale(1.01);

        }}

        .clickable-threat-row.active {{
            background: #2563eb;
        }}

        .clickable-threat-row.active td {{
            color: white;
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
                all .3s ease;
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

        .copyable-ioc {{

            cursor:pointer;

            transition:
                color .2s ease,
                padding-left .2s ease;

        }}

        .copyable-ioc:hover {{

            color:#38bdf8;

            text-decoration:none;

            padding-left:8px;

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

        #sortType,
        #sortCount {{
            cursor: pointer;
        }}
        
        .chart-container {{
            position: relative;
            height: 350px;
            width: 100%;
            margin-top: 20px;
        }}

        .floating-actions {{

            position: fixed;

            right: 30px;
            bottom: 30px;

            display: flex;
            flex-direction: column;

            gap: 12px;

            z-index: 1000;

        }}

        #printReport {{

            border: none;

            padding: 12px 18px;

            border-radius: 10px;

            background: #16a34a;

            color: white;

            font-size: 14px;

            font-weight: 600;

            cursor: pointer;

            box-shadow:
                0 4px 12px rgba(0,0,0,.35);

            transition:
                transform .2s ease,
                background .2s ease;

        }}

        #printReport:hover {{

            background:#15803d;

            transform:translateY(-2px);

        }}

        .floating-actions {{

            position: fixed;

            right: 30px;

            bottom: 30px;

            display: flex;

            flex-direction: column;

            gap: 12px;

        }}

        #backToTop {{

            width: 48px;
            height: 48px;

            border: none;
            border-radius: 50%;

            background: #2563eb;
            color: white;

            font-size: 22px;
            cursor: pointer;

            display: none;

            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.35);

            transition:
                opacity 0.2s ease,
                transform 0.2s ease;
        }}

        #backToTop:hover {{
            transform: translateY(-3px);
            background: #1d4ed8;
        }}

        @media print {{       

            body {{
                background: white !important;
                color: black !important;
                padding: 0;
            }}

            .container {{
                background: white !important;
                color: black !important;
                box-shadow: none !important;
                border: none !important;
            }}

            .search-box,
            #backToTop,
            #printReport {{
                display: none !important;
            }}

            table,
            .summary-card,
            .details-panel {{
                page-break-inside: avoid;
                break-inside: avoid;
                box-shadow: none !important;
            }}

            a {{
                color: black !important;
                text-decoration: none;
            }}

            * {{
                animation: none !important;
                transition: none !important;
            }}

        }}

        @keyframes fadeIn {{

            from {{
                opacity: 0;
                transform: translateY(20px);
            }}

            to {{
                opacity: 1;
                transform: translateY(0);
            }}

        }}

        

        </style>

        <script
            src="https://cdn.jsdelivr.net/npm/chart.js"
            defer
        ></script>

        </head>

        <body>

        <div class="page">

        <div class="container">

        <div class="report-header">

        <div class="report-brand">

        <h1>SOC-IQ</h1>

        <h3 class="report-name">
            {escape(report.report_name)}
        </h3>

        <p>
        Security Operations & Intelligence Platform
        </p>

        </div>

        <div class="report-meta">

        <div>
        <strong>Version:</strong> {version}
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

            <div class="summary-subtitle">
                {risk_label}
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

        <div class="section" id="statistics">

        <h2>Report Statistics</h2>

        <div class="summary-grid">

        <div class="summary-card">
        <div class="summary-title">
        IOC Types
        </div>
        <div class="summary-value">
        {len(report.iocs)}
        </div>
        </div>

        <div class="summary-card">
        <div class="summary-title">
        Total IOCs
        </div>
        <div class="summary-value">
        {sum(len(values) for values in report.iocs.values())}
        </div>
        </div>

        <div class="summary-card">
        <div class="summary-title">
        Threat Entries
        </div>
        <div class="summary-value">
        {len(report.threat_intelligence.get("hashes", []))}
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

        </div>

        </div>

        <div class="section">

        <h2>Quick Navigation</h2>

        <div class="details-panel">

        <div class="detail-row">
        <a href="#statistics">📊 Report Statistics</a>
        </div>

        <div class="detail-row">
        <a href="#details">📄 Investigation Details</a>
        </div>

        <div class="detail-row">
        <a href="#distribution">📈 IOC Distribution</a>
        </div>

        <div class="detail-row">
        <a href="#ioc-summary">🛡 IOC Summary</a>
        </div>

        <div class="detail-row">
        <a href="#threat-summary">🧠 Threat Intelligence</a>
        </div>

        </div>

        </div>

       <div class="section" id="details">

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

        <div class="section" id="distribution">  

        <h2>IOC Distribution</h2>

        <div class="chart-container">

        <canvas
            id="iocChart"
            width="1000"
            height="350"
        ></canvas>

        </div>

        </div>

        <div class="section" id="ioc-summary">

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
        <th id="sortType">
            IOC Type ▲▼
        </th>

        <th id="sortCount">
            Count ▲▼
        </th>
        </tr>

        </thead>

        <tbody id="iocTableBody">

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

        <div class="section" id="threat-summary">

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

        <div
            id="threatDetails"
            class="ioc-details-panel"
        >
            <h3>Threat Intelligence Details</h3>

            <p>
                Click a threat intelligence entry above to view its details.
            </p>
        </div>

        </div>

        <div class="footer">

        <strong>SOC-IQ</strong><br>

        Security Operations & Intelligence Platform<br>

        Version {version}<br>

        Generated automatically by SOC-IQ.<br>

        Generated on:
        {generated_at}<br>

        Confidential - For authorized personnel only.

        </div>

        </div>

        </div>

        <div class="floating-actions">

            <button
                id="printReport"
                title="Print Report"
            >
                🖨 Print
            </button>

            <button
                id="backToTop"
                title="Back to Top"
            >
                ↑
            </button>

        </div>

        <script>

        document.addEventListener(
            "DOMContentLoaded",
            function () {{
            
             try {{

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

        if (canvas && window.Chart) {{
        
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

        const rows = Array.from(
            document.querySelectorAll(
                ".clickable-row"
            )
        );

        rows.forEach((row) => {{

            row.addEventListener("click", function () {{
            
                rows.forEach((item) => {{
                    item.classList.remove("active");
                }});

                row.classList.add("active");

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
                                /\\b\\w/g,
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
                            "<li class='copyable-ioc'>" +
                            escapeHtml(value) +
                            "</li>";

                    }});

                    html += "</ul>";
                }}

                ui.detailsPanel.innerHTML = html;

                ui.detailsPanel
                    .querySelectorAll(".copyable-ioc")
                    .forEach((item) => {{

                        item.addEventListener("click", function () {{

                            navigator.clipboard
                                .writeText(item.textContent)
                                .catch(function (error) {{
                                    console.error(
                                        "Failed to copy IOC:",
                                        error
                                    );
                                }});

                            item.style.color = "#22c55e";

                            const badge = document.createElement(
                                "span"
                            );

                            badge.textContent = " ✓ Copied!";
                            badge.style.color = "#22c55e";
                            badge.style.fontWeight = "bold";
                            badge.style.marginLeft = "10px";

                            item.appendChild(
                                badge
                            );

                            setTimeout(function () {{

                                badge.remove();

                                item.style.color = "";

                            }}, 800);

                        }});

                    }});

            }});

        }});

        const ui = {{
            searchBox: document.getElementById("iocSearch"),
            noResultsMessage: document.getElementById("noResultsMessage"),
            threatDetails: document.getElementById("threatDetails"),
            detailsPanel: document.getElementById("iocDetails"),
            tableBody: document.getElementById("iocTableBody"),
            backToTop: document.getElementById("backToTop"),
            printReport: document.getElementById("printReport"),
            sortType: document.getElementById("sortType"),
            sortCount: document.getElementById("sortCount"),
        }};

        ui.searchBox.addEventListener(
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
                    ui.noResultsMessage.style.display = "block";
                }}
                else {{
                    ui.noResultsMessage.style.display = "none";
                }}

            }}
        );

        let typeAscending = true;

        ui.sortType.addEventListener("click", function () {{

                rows.sort(function (a, b) {{

                    const first =
                        a.cells[0].textContent.trim();

                    const second =
                        b.cells[0].textContent.trim();

                    if (typeAscending) {{
                        return first.localeCompare(second);
                    }}

                    return second.localeCompare(first);

                }});

                rows.forEach(function (row) {{
                    ui.tableBody.appendChild(row);
                }});

                typeAscending = !typeAscending;

                ui.sortType.textContent =
                    typeAscending
                        ? "IOC Type ▼"
                        : "IOC Type ▲";

                }});

            let countAscending = true;

            ui.sortCount.addEventListener("click", function () {{
                
                    rows.sort(function (a, b) {{
                    
                        const first =
                            parseInt(
                                a.cells[1].textContent,
                                10,
                            );

                        const second =
                            parseInt(
                                b.cells[1].textContent,
                                10,
                            );

                            if (countAscending) {{
                                return first - second;
                            }}

                            return second - first;

                        }});

                        rows.forEach(function (row) {{
                            ui.tableBody.appendChild(row);
                        }});

                        countAscending = !countAscending;

                        ui.sortCount.textContent =
                            countAscending
                                ? "Count ▼"
                                : "Count ▲";

                        }});
                
        const threatRows =
            document.querySelectorAll(
                ".clickable-threat-row"
            );

        threatRows.forEach((row) => {{

            row.addEventListener("click", function () {{
            
                threatRows.forEach((item) => {{
                    item.classList.remove("active");
                }});

                row.classList.add("active");

                const sha256 =
                    row.dataset.sha256;

                const verdict =
                    row.dataset.verdict;

                const detection =
                    row.dataset.detection;

                ui.threatDetails.innerHTML = `
                <h3>Threat Intelligence Analysis</h3>

                <div class="details-panel">

                <div class="detail-row">
                <span class="detail-label">SHA256</span>
                <span class="detail-value">
                ${{escapeHtml(sha256)}}
                </span>
                </div>

                <div class="detail-row">
                <span class="detail-label">Verdict</span>
                <span class="detail-value">
                ${{escapeHtml(verdict)}}
                </span>
                </div>

                <div class="detail-row">
                <span class="detail-label">
                Detection Ratio
                </span>
                <span class="detail-value">
                ${{escapeHtml(detection)}}
                </span>
                </div>

                <div class="detail-row">
                <span class="detail-label">
                Threat Level
                </span>

                <span class="detail-value">

                ${{
                verdict.toLowerCase() === "malicious"
                ? "<span class='badge badge-critical'>HIGH</span>"
                : verdict.toLowerCase() === "suspicious"
                ? "<span class='badge badge-medium'>MEDIUM</span>"
                : "<span class='badge badge-low'>LOW</span>"
                }}

                </span>

                </div>

                <div class="detail-row">

                <span class="detail-label">
                Recommendation
                </span>

                <span class="detail-value">

                ${{
                verdict.toLowerCase() === "malicious"
                ? "Immediate investigation recommended."
                : verdict.toLowerCase() === "suspicious"
                ? "Manual analyst review recommended."
                : "No immediate action required."
                }}

                </span>

                </div>

                </div>
                `;

            }});

        }});

        window.addEventListener(
            "scroll",
            function () {{

                if (window.scrollY > 300) {{
                    ui.backToTop.style.display = "block";
                }}
                else {{
                    ui.backToTop.style.display = "none";
                }}

            }}
        );

        ui.printReport.addEventListener("click", function () {{

            window.print();

        }});

    if (ui.backToTop) {{

        ui.backToTop.addEventListener("click", function () {{

            window.scrollTo({{
                top: 0,
                behavior: "smooth",
            }});

        }});

    }}

        }} catch (error) {{
            console.error(
                "SOC-IQ HTML initialization failed:",
                error
            );
        }}

        }});

        </script>

        </body>

        </html>
        """