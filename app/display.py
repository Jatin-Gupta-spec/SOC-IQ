"""
SOC-IQ console presentation layer.

This module formats and renders system execution data, indicators of compromise,
threat intelligence enrichment payloads, and multi-vector risk breakdowns.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Collection, Iterable, Mapping, Sequence, TypeAlias

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from app.config import (
    APP_AUTHOR,
    APP_DESCRIPTION,
    APP_NAME,
    APP_VERSION,
)
from app.database.models import Investigation
from app.scoring.models import RiskScore

__all__ = [
    "print_banner",
    "display_summary",
    "display_iocs",
    "display_risk_summary",
    "display_investigation_history",
    "display_investigation_details",
]

console = Console()

# ====================================================
# Type Aliases (Better Type Safety)
# ====================================================
ThreatIntelDataMap: TypeAlias = Mapping[str, Any]
IOCCollectionMap: TypeAlias = Mapping[
    str,
    Mapping[str, Collection[str]],
]
RiskMapping: TypeAlias = Mapping[str, Any]
GenericAnalysisPayload: TypeAlias = Mapping[str, Any]

# ====================================================
# Configuration & Constants
# ====================================================
_DATE_FORMAT: str = "%Y-%m-%d %H:%M"
_MAX_IOC_PREVIEW: int = 5

TITLE_BANNER: str = "SOC-IQ System Banner"
TITLE_ANALYSIS_SUMMARY: str = "=== Analysis Summary ==="
TITLE_EXECUTION_SUMMARY: str = "Execution Summary"
TITLE_IOC_HEADER: str = "=== Extracted Indicators of Compromise (IOCs) ==="
TITLE_IOC_OBSERVED: str = "Observed Indicators"
TITLE_RISK_HEADER: str = "=== Risk Assessment Breakdown ==="
TITLE_RISK_METRICS: str = "Risk Metrics"
TITLE_CONTRIBUTING_VECTORS: str = "Contributing Vectors"
TITLE_CONTEXT_RULES: str = "Analysis & Context Rules Triggered"
TITLE_HISTORY_HEADER: str = "=== Historic Investigation Log ==="
TITLE_HISTORY_LEDGER: str = "Historical Ledger"
TITLE_DETAILS_HEADER: str = "=== Investigation Detail Map ==="
TITLE_METADATA_PARAMS: str = "Metadata System Parameters"
TITLE_INTEL_HEADER: str = "=== Threat Intelligence Enrichment ==="
TITLE_PROVIDER_PREFIX: str = "Threat Intel Provider"

# Reusable Alert and Empty Data State Strings
MSG_NO_IOCS: str = "[yellow]No IOCs discovered in report.[/yellow]"
MSG_NO_INTEL: str = "[yellow]No threat intelligence details available.[/yellow]"
MSG_NO_HISTORY: str = "[yellow]No local historic investigation ledger entries found.[/yellow]"
TEXT_LOGIC_SUMMARY: str = "Logic / Context Breakdown Summary"

RISK_VECTOR_LABELS: Mapping[str, str] = {
    "ioc_score": "Indicator Score",
    "threat_intel_score": "Threat Intel Score",
    "cve_score": "CVE Score",
}

_SEVERITY_COLORS: Mapping[str, str] = {
    "CRITICAL": "bold red",
    "HIGH": "red",
    "MEDIUM": "yellow",
    "LOW": "green",
    "INFO": "cyan",
    "UNKNOWN": "bold white on red",
}

# ====================================================
# Reusable Style & Structural Helpers (DRY Implementation)
# ====================================================
def _make_table(title: str) -> Table:
    """
    Create a consistently styled, dashboard-ready Rich table.
    """
    return Table(
        title=title,
        box=box.ROUNDED,
        header_style="bold cyan",
        border_style="bright_black",
        title_style="bold white",
        pad_edge=False,
    )


def _severity_text(severity: Any) -> str:
    """
    Return severity with Rich color, gracefully defaulting to UNKNOWN.
    """
    sev_str = str(severity).strip().upper() if severity else "UNKNOWN"
    color = _SEVERITY_COLORS.get(sev_str, _SEVERITY_COLORS["UNKNOWN"])
    return f"[{color}]{sev_str}[/{color}]"


def _format_datetime(value: datetime | None) -> str:
    """
    Format datetime safely.
    """
    if value is None:
        return "-"
    return value.strftime(_DATE_FORMAT)


def _format_confidence(value: Any) -> str:
    """
    Robust confidence level formatting supporting fraction (0.85) and percentage (85).
    """
    if value is None:
        return "-"
    try:
        val_float = float(value)
        if val_float <= 1.0:
            return f"{val_float * 100:.1f}%"
        return f"{val_float:.1f}%"
    except (ValueError, TypeError):
        return str(value)


def _truncate_iocs(items: Any) -> str:
    """
    Format IOC elements from sets, tuples, generators, or lists by previewing 
    only the first N items to preserve clear terminal alignments and prevent wraps.
    """
    if items is None:
        return "-"
        
    try:
        # Materialize generators, sets, or tuples safely into flat string representations
        normalized_list = [str(item) for item in items]
    except TypeError:
        return str(items)

    if not normalized_list:
        return "-"
        
    preview_items = normalized_list[:_MAX_IOC_PREVIEW]
    joined_preview = ", ".join(preview_items)
    
    if len(normalized_list) > _MAX_IOC_PREVIEW:
        joined_preview += f" (+{len(normalized_list) - _MAX_IOC_PREVIEW} more)"
    return joined_preview


# ====================================================
# Data Extraction & Preparation Helpers (GUI-Ready)
# ====================================================
def _prepare_summary_data(analysis: GenericAnalysisPayload) -> RiskMapping:
    """
    Extracts summary parameters without mutating business logic.
    """
    summary_data: dict[str, Any] = {
        "Investigation ID": analysis.get("investigation_id", "-"),
        "Status": analysis.get("status", "-"),
    }
    risk_data = analysis.get("risk")
    if isinstance(risk_data, dict):
        summary_data["Risk Score"] = risk_data.get("score", "-")
        summary_data["Severity"] = _severity_text(risk_data.get("severity"))
    return summary_data


def _prepare_risk_data(risk: RiskScore | RiskMapping) -> RiskMapping:
    """
    Unifies RiskScore models and dictionaries into a structured metadata map.
    """
    if isinstance(risk, RiskScore):
        return {
            "score": risk.score,
            "severity": risk.severity,
            "confidence": risk.confidence,
            "vectors": {
                RISK_VECTOR_LABELS["ioc_score"]: risk.ioc_score,
                RISK_VECTOR_LABELS["threat_intel_score"]: risk.threat_intel_score,
                RISK_VECTOR_LABELS["cve_score"]: risk.cve_score,
            },
            "reasons": risk.reasons,
        }
    
    vectors = risk.get("vectors")
    if isinstance(vectors, dict):
        resolved_vectors = vectors
    else:
        resolved_vectors: dict[str, Any] = {}
    
    if "ioc_score" in risk:
        resolved_vectors[
            RISK_VECTOR_LABELS["ioc_score"]
        ] = risk["ioc_score"]

    if "threat_intel_score" in risk:
        resolved_vectors[
            RISK_VECTOR_LABELS["threat_intel_score"]
        ] = risk["threat_intel_score"]

    if "cve_score" in risk:
        resolved_vectors[
            RISK_VECTOR_LABELS["cve_score"]
        ] = risk["cve_score"]

    return {
        "score": risk.get("score", None),
        "severity": risk.get("severity", None),
        "confidence": risk.get("confidence", None),
        "vectors": resolved_vectors,
        "reasons": risk.get("reasons", []),
    }


def _extract_risk_from_investigation(
    investigation: Investigation,
) -> RiskMapping:
    """
    Extract only the risk information that actually exists on an
    Investigation record.

    The presentation layer should never invent missing values.
    """

    risk_data: dict[str, Any] = {
        "score": investigation.risk_score,
        "severity": investigation.severity,
    }

    if hasattr(investigation, "confidence"):
        risk_data["confidence"] = investigation.confidence

    vectors: dict[str, Any] = {}

    if hasattr(investigation, "ioc_score"):
        vectors[RISK_VECTOR_LABELS["ioc_score"]] = investigation.ioc_score

    if hasattr(investigation, "threat_intel_score"):
        vectors[RISK_VECTOR_LABELS["threat_intel_score"]] = (
            investigation.threat_intel_score
        )

    if hasattr(investigation, "cve_score"):
        vectors[RISK_VECTOR_LABELS["cve_score"]] = investigation.cve_score

    if vectors:
        risk_data["vectors"] = vectors

    if hasattr(investigation, "reasons"):
        risk_data["reasons"] = investigation.reasons

    return risk_data


def _prepare_metadata_params(investigation: Investigation) -> RiskMapping:
    """
    Extracts system parameters from an Investigation model.
    """
    return {
        "Report Name": investigation.report_name,
        "Execution Timestamp": _format_datetime(investigation.analyzed_at),
        "Status State": investigation.status if investigation.status else "-",
        "Risk Score": investigation.risk_score,
        "Severity Classification": _severity_text(investigation.severity),
    }


# ====================================================
# Component Rendering Helpers (Modular Render Layouts)
# ====================================================
def _render_key_value_table(title: str, data: RiskMapping) -> Table:
    """
    Renders standard property tables dynamically with strict dashboard column definitions.
    """
    table = _make_table(title)
    table.add_column("Property", style="bold magenta", width=28, overflow="ellipsis")
    table.add_column("Value", style="white", overflow="fold")
    
    for key, val in data.items():
        formatted_key = str(key).replace("_", " ").title()
        if isinstance(val, (dict, list)) and not val:
            formatted_val = "None"
        elif isinstance(val, (list, tuple, set)):
            formatted_val = _truncate_iocs(val)
        else:
            formatted_val = "-" if val is None else str(val)
        table.add_row(formatted_key, formatted_val)
    return table


def _render_nested_dict(data: Mapping[str, Any], ident: int = 0) -> str:
    """
    Recursively formats complex nested dictionaries to strings.
    """
    padding = "  " * ident
    lines = []
    for key, value in data.items():
        formatted_key = str(key).replace("_", " ").title()
        if isinstance(value, dict):
            lines.append(f"{padding}[bold cyan]{formatted_key}:[/bold cyan]")
            lines.append(_render_nested_dict(value, ident + 1))
        elif isinstance(value, (list, tuple, set)):
            lines.append(f"{padding}[bold cyan]{formatted_key}:[/bold cyan]")
            lines.append(_render_list(list(value), ident + 1))
        else:
            lines.append(f"{padding}[bold cyan]{formatted_key}:[/bold cyan] {value}")
    return "\n".join(lines)


def _render_list(data: Sequence[Any], ident: int = 0) -> str:
    """
    Recursively formats arrays or sub-items to strings.
    """
    padding = "  " * ident
    if not data:
        return f"{padding}None"
    if all(not isinstance(i, (dict, list, tuple, set)) for i in data):
        return f"{padding}{_truncate_iocs(data)}"
    
    lines = []
    for index, item in enumerate(data):
        lines.append(f"{padding}[bold yellow]- Item #{index + 1}:[/bold yellow]")
        if isinstance(item, dict):
            lines.append(_render_nested_dict(item, ident + 1))
        elif isinstance(item, (list, tuple, set)):
            lines.append(_render_list(list(item), ident + 1))
        else:
            lines.append(f"{padding}{item}")
    return "\n".join(lines)


def _render_provider_table(title: str, items: Sequence[Mapping[str, Any]]) -> Table:
    """
    Renders rows of flat structural dictionary elements cleanly.
    """
    table = _make_table(title)
    if not items:
        return table
    
    columns = list(items[0].keys())
    for col in columns:
        table.add_column(col.replace("_", " ").title(), style="white", overflow="fold")
    for item in items:
        table.add_row(*(str(item.get(c, "-")) for c in columns))
    return table


def _render_provider_panel(title: str, details: Any) -> Panel:
    """
    Renders highly variable configurations inside dynamic view containers.
    """
    if isinstance(details, dict):
        content = _render_nested_dict(details)
    elif isinstance(details, (list, tuple, set)):
        content = _render_list(list(details))
    else:
        content = str(details)
    return Panel(content, title=title, border_style="bright_black", expand=False)


def _render_provider(provider: str, details: Any) -> None:
    """
    Dispatches and renders threat intelligence telemetry content depending on internal structural layout.
    """
    provider_name = str(provider).replace("_", " ").upper()
    title = f"{TITLE_PROVIDER_PREFIX}: {provider_name}"
    
    if isinstance(details, list) and details and isinstance(details[0], dict):
        console.print(_render_provider_table(title, details))
    else:
        console.print(_render_provider_panel(title, details))


def _render_threat_intel(intel_data: ThreatIntelDataMap) -> None:
    """
    Provider-independent, future-proof Threat Intelligence dispatcher.
    Matches data payloads for any current or future external intelligence engines.
    """
    if not intel_data:
        console.print(MSG_NO_INTEL)
        return

    for provider, details in intel_data.items():
        _render_provider(provider, details)


# ====================================================
# Public Core API
# ====================================================
def print_banner() -> None:
    """
    Display the SOC-IQ application banner.
    """
    console.print(
        Panel.fit(
            (
                f"[bold cyan]{APP_NAME}[/bold cyan]\n"
                f"{APP_DESCRIPTION}\n\n"
                f"Version : {APP_VERSION}\n"
                f"Author  : {APP_AUTHOR}"
            ),
            border_style="cyan",
            title=TITLE_BANNER,
        )
    )


def display_summary(analysis: GenericAnalysisPayload) -> None:
    """
    Display top-level summary of the execution context analysis.
    """
    console.print(f"\n[bold green]{TITLE_ANALYSIS_SUMMARY}[/bold green]\n")
    summary_data = _prepare_summary_data(analysis)
    console.print(_render_key_value_table(TITLE_EXECUTION_SUMMARY, summary_data))
    
    risk_data = analysis.get("risk")
    if risk_data:
        display_risk_summary(risk_data)


def display_iocs(analysis: IOCCollectionMap) -> None:
    """
    Make IOC rendering completely generic, robust, and cleanly formatted.
    """
    console.print(f"\n[bold green]{TITLE_IOC_HEADER}[/bold green]\n")
    iocs = analysis.get("iocs", {})
    if not iocs:
        console.print(MSG_NO_IOCS)
        return

    table = _make_table(TITLE_IOC_OBSERVED)
    table.add_column("Type", style="bold magenta", width=16, overflow="ellipsis")
    table.add_column("Count", style="bold green", justify="right", width=10, no_wrap=True)
    table.add_column("Indicators (Preview)", style="white", overflow="fold")

    for ioc_type, items in iocs.items():
        if items is not None:
            # Cast to list exactly once to prevent double-exhaustion on generators/iterators
            materialized_items = list(items)
            table.add_row(str(ioc_type).upper(), str(len(materialized_items)), _truncate_iocs(materialized_items))
    console.print(table)


def display_risk_summary(risk: RiskScore | RiskMapping) -> None:
    """
    Display complex scoring breakdown handling both classes and dicts safely.
    """
    console.print(f"\n[bold green]{TITLE_RISK_HEADER}[/bold green]\n")
    parsed = _prepare_risk_data(risk)

    score_val = "-" if parsed['score'] is None else parsed['score']
    panel_content = (
        f"Overall Score: [bold]{score_val}[/bold]\n"
        f"Severity:      {_severity_text(parsed['severity'])}\n"
        f"Confidence:    {_format_confidence(parsed['confidence'])}"
    )
    console.print(Panel(panel_content, title=TITLE_RISK_METRICS, border_style="cyan", expand=False))
    console.print(_render_key_value_table(TITLE_CONTRIBUTING_VECTORS, parsed["vectors"]))

    reasons = parsed["reasons"]
    if reasons:
        reasons_table = _make_table(TITLE_CONTEXT_RULES)
        reasons_table.add_column(TEXT_LOGIC_SUMMARY, style="yellow", overflow="fold")
        for reason in reasons:
            reasons_table.add_row(str(reason))
        console.print(reasons_table)


def display_investigation_history(investigations: Iterable[Investigation]) -> None:
    """
    Display structured historical list table.
    """
    console.print(f"\n[bold green]{TITLE_HISTORY_HEADER}[/bold green]\n")
    table = _make_table(TITLE_HISTORY_LEDGER)
    table.add_column("ID", style="bold cyan", justify="right", width=6, no_wrap=True)
    table.add_column("Timestamp", style="white", width=18, no_wrap=True)
    table.add_column("Report Target", style="white", overflow="fold")
    table.add_column("IOC Count", style="bold magenta", justify="right", width=12, no_wrap=True)
    table.add_column("Risk", style="white", justify="right", width=8, no_wrap=True)
    table.add_column("Severity", style="white", width=16, no_wrap=True)
    table.add_column("Status", style="bold green", width=14, no_wrap=True)

    has_records = False
    for inv in investigations:
        has_records = True
        
        ioc_count = 0
        if isinstance(inv.iocs, dict):
            for items in inv.iocs.values():
                if items is not None:
                    ioc_count += len(list(items))

        table.add_row(
            str(inv.investigation_id) if inv.investigation_id is not None else "-",
            _format_datetime(inv.analyzed_at),
            inv.report_name,
            str(ioc_count),
            "-" if inv.risk_score is None else str(inv.risk_score),
            _severity_text(inv.severity),
            str(inv.status) if inv.status else "-",
        )

    if not has_records:
        console.print(MSG_NO_HISTORY)
        return
    console.print(table)


def display_investigation_details(investigation: Investigation) -> None:
    """
    Display exhaustive metadata summary layout for deep historical inspections.
    """
    console.print(f"\n[bold green]{TITLE_DETAILS_HEADER}: #{investigation.investigation_id} ===[/bold green]\n")
    metadata = _prepare_metadata_params(investigation)
    console.print(_render_key_value_table(TITLE_METADATA_PARAMS, metadata))

    display_iocs({"iocs": investigation.iocs})

    console.print(f"\n[bold green]{TITLE_INTEL_HEADER}[/bold green]\n")
    _render_threat_intel(investigation.threat_intelligence)

    # Resolves type parsing mismatch by mapping investigation metrics explicitly[cite: 6]
    risk_payload = _extract_risk_from_investigation(investigation)
    display_risk_summary(risk_payload)