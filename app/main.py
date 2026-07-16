"""
Main entry point for the SOC-IQ application.
"""

from __future__ import annotations

from pathlib import Path

from app.analyzer import analyze_report
from app.cli import parse_arguments
from app.database.service import InvestigationService
from app.display import (
    display_investigation_details,
    display_investigation_history,
    display_iocs,
    display_summary,
    print_banner,
)
from app.exceptions import SOCIQError
from app.exporters import (
    export_to_csv,
    export_to_json,
)
from app.initializer import initialize_application
from app.logger import (
    configure_logger,
    logger,
)


def main() -> None:
    """
    Main application entry point.
    """

    try:

        initialize_application()

        arguments = parse_arguments()

        configure_logger(
            verbose=arguments.verbose,
        )

        logger.info(
            "Application started."
        )

        print_banner()

        service = InvestigationService()

        # ----------------------------------
        # Investigation History
        # ----------------------------------

        if arguments.history:

            investigations = service.list_all()

            display_investigation_history(
                investigations,
            )

            return

        # ----------------------------------
        # Investigation by ID
        # ----------------------------------

        if arguments.history_id is not None:

            investigation = service.get_by_id(
                arguments.history_id,
            )

            if investigation is None:

                logger.warning(
                    "Investigation %d not found.",
                    arguments.history_id,
                )

                return

            display_investigation_details(
                investigation,
            )

            return

        # ----------------------------------
        # Malware Analysis
        # ----------------------------------

        logger.info(
            "Analyzing report: %s",
            arguments.input,
        )

        analysis = analyze_report(
            Path(arguments.input),
        )

        display_summary(
            analysis,
        )

        display_iocs(
            analysis,
        )

        export_json = (
            arguments.json
            or (
                not arguments.json
                and not arguments.csv
            )
        )

        export_csv = (
            arguments.csv
            or (
                not arguments.json
                and not arguments.csv
            )
        )

        if export_json:

            export_to_json(
                analysis,
            )

        if export_csv:

            export_to_csv(
                analysis,
            )

        logger.info(
            "Application completed successfully."
        )

    except SOCIQError as error:

        logger.error(
            str(error),
        )

    except Exception:

        logger.exception(
            "Application terminated unexpectedly.",
        )

        raise


if __name__ == "__main__":
    main()