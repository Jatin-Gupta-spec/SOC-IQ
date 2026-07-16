"""
Command-line interface for the SOC-IQ application.
"""

from __future__ import annotations

from argparse import (
    ArgumentParser,
    Namespace,
)

from app.config import (
    APP_DESCRIPTION,
    APP_NAME,
    APP_VERSION,
    SAMPLE_REPORT,
)


def parse_arguments() -> Namespace:
    """
    Parse command-line arguments for the
    SOC-IQ application.
    """

    parser = ArgumentParser(
        prog=APP_NAME,
        description=APP_DESCRIPTION,
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {APP_VERSION}",
        help="Display the application version and exit.",
    )

    parser.add_argument(
        "--input",
        type=str,
        default=str(SAMPLE_REPORT),
        metavar="FILE",
        help="Path to the malware report to analyze.",
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Export results as JSON.",
    )

    parser.add_argument(
        "--csv",
        action="store_true",
        help="Export results as CSV.",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Display detailed runtime logging in the terminal.",
    )

    parser.add_argument(
        "--history",
        action="store_true",
        help="Display all previous investigations.",
    )

    parser.add_argument(
        "--history-id",
        type=int,
        metavar="ID",
        help="Display a specific investigation by ID.",
    )

    return parser.parse_args()