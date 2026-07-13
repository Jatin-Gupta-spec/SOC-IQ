from pathlib import Path

from app.initializer import initialize_application

from app.display import (
    print_banner,
    display_summary,
    display_iocs,
)

from app.analyzer import analyze_report

from app.exporters import (
    export_to_json,
    export_to_csv,
)

from app.logger import (
    logger,
    configure_logger,
)

from app.exceptions import SOCIQError

from app.cli import parse_arguments


def main() -> None:
    """
    Main entry point for the SOC-IQ application.
    """

    try:
        initialize_application()

        arguments = parse_arguments()

        configure_logger(
            verbose=arguments.verbose,
        )

        logger.info("Application started.")

        print_banner()

        logger.info(
            "Analyzing report: %s",
            arguments.input,
        )

        extracted_iocs = analyze_report(
            Path(arguments.input),
        )

        logger.info(
            "IOC extraction completed successfully."
        )

        logger.info("Displaying results...")

        display_summary(
            extracted_iocs,
        )

        display_iocs(
            extracted_iocs,
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

            logger.info(
                "Exporting JSON report..."
            )

            export_to_json(
                extracted_iocs,
            )

            logger.info(
                "JSON report exported successfully."
            )

        if export_csv:

            logger.info(
                "Exporting CSV report..."
            )

            export_to_csv(
                extracted_iocs,
            )

            logger.info(
                "CSV report exported successfully."
            )

        logger.info(
            "Application completed successfully."
        )

    except SOCIQError as error:
        logger.error(str(error))

    except Exception:
        logger.exception(
            "Application terminated unexpectedly."
        )
        raise


if __name__ == "__main__":
    main()