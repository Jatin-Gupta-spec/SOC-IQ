from typing import Any

from rich.console import Console
from rich.table import Table

from app.config import (
    APP_AUTHOR,
    APP_DESCRIPTION,
    APP_NAME,
    APP_VERSION,
)

console: Console = Console()


def print_banner() -> None:
    """
    Display the SOC-IQ application banner.
    """

    console.rule(
        f"[bold cyan]{APP_NAME}[/bold cyan]"
    )

    console.print(
        f"[bold white]{APP_DESCRIPTION}[/bold white]"
    )

    console.print(
        f"[green]Version:[/green] {APP_VERSION}"
    )

    console.print(
        f"[green]Author:[/green] {APP_AUTHOR}"
    )

    console.rule()


def _extract_ioc_results(
    results: dict[str, Any],
) -> dict[str, list[str]]:
    """
    Return IOC dictionary regardless of
    analyzer result structure.
    """

    if "iocs" in results:
        return results["iocs"]

    return results


def _extract_threat_results(
    results: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Extract threat intelligence hash results.
    """

    threat_intelligence = results.get(
        "threat_intelligence",
        {},
    )

    return threat_intelligence.get(
        "hashes",
        [],
    )


def display_summary(
    results: dict[str, Any],
) -> None:
    """
    Display IOC and threat intelligence summary.
    """

    ioc_results = _extract_ioc_results(
        results
    )

    summary_table = Table(
        title="IOC Analysis Summary"
    )

    summary_table.add_column(
        "IOC Type",
        style="cyan",
    )

    summary_table.add_column(
        "Count",
        justify="right",
        style="green",
    )

    total_iocs = 0

    for ioc_type, values in ioc_results.items():

        count = len(values)

        total_iocs += count

        summary_table.add_row(
            ioc_type,
            str(count),
        )

    summary_table.add_section()

    summary_table.add_row(
        "[bold]Total[/bold]",
        f"[bold]{total_iocs}[/bold]",
    )

    console.print(
        summary_table
    )

    threat_results = _extract_threat_results(
        results
    )

    if threat_results:

        threat_table = Table(
            title="Threat Intelligence Summary"
        )

        threat_table.add_column(
            "Provider",
            style="cyan",
        )

        threat_table.add_column(
            "Hashes Enriched",
            style="green",
        )

        threat_table.add_row(
            "VirusTotal",
            str(len(threat_results)),
        )

        console.print(
            threat_table
        )


def display_iocs(
    results: dict[str, Any],
) -> None:
    """
    Display IOC tables and threat intelligence.
    """

    ioc_results = _extract_ioc_results(
        results
    )

    for ioc_type, values in ioc_results.items():

        table = Table(
            title=f"{ioc_type} ({len(values)})"
        )

        table.add_column(
            "No.",
            style="cyan",
            width=6,
        )

        table.add_column(
            "IOC Value",
            style="green",
        )

        if values:

            for index, value in enumerate(
                values,
                start=1,
            ):

                table.add_row(
                    str(index),
                    value,
                )

        else:

            table.add_row(
                "-",
                "[red]No IOCs Found[/red]",
            )

        console.print(
            table
        )

    threat_results = _extract_threat_results(
        results
    )

    if not threat_results:
        return

    vt_table = Table(
        title="VirusTotal Results"
    )

    vt_table.add_column(
        "SHA256",
        style="cyan",
        overflow="fold",
    )

    vt_table.add_column(
        "Malicious",
        justify="right",
        style="red",
    )

    vt_table.add_column(
        "Suspicious",
        justify="right",
        style="yellow",
    )

    vt_table.add_column(
        "Harmless",
        justify="right",
        style="green",
    )

    for result in threat_results:

        vt_table.add_row(
            result.get(
                "sha256",
                "-",
            ),
            str(
                result.get(
                    "malicious",
                    "-",
                )
            ),
            str(
                result.get(
                    "suspicious",
                    "-",
                )
            ),
            str(
                result.get(
                    "harmless",
                    "-",
                )
            ),
        )

    console.print(
        vt_table
    )