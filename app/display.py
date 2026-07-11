from rich.console import Console
from rich.table import Table

from app.config import (
    APP_NAME,
    APP_VERSION,
    APP_AUTHOR,
    APP_DESCRIPTION,
)

console: Console = Console()


def print_banner() -> None:
    """
    Display the SOC-IQ application banner.
    """

    console.rule(f"[bold cyan]{APP_NAME}[/bold cyan]")

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


def display_summary(
    results: dict[str, list[str]]
) -> None:
    """
    Display a summary table showing the number of
    extracted IOCs for each IOC category.
    """

    summary_table = Table(title="IOC Analysis Summary")

    summary_table.add_column(
        "IOC Type",
        style="cyan",
    )

    summary_table.add_column(
        "Count",
        justify="right",
        style="green",
    )

    total_iocs: int = 0

    for ioc_type, values in results.items():

        count: int = len(values)

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

    console.print(summary_table)


def display_iocs(
    results: dict[str, list[str]]
) -> None:
    """
    Display each IOC category in its own Rich table.
    """

    for ioc_type, values in results.items():

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

        console.print(table)