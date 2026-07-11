from app.initializer import initialize_application

from app.display import print_banner

from app.analyzer import analyze_report

from app.logger import logger

from app.exceptions import SOCIQError

from app.cli import parse_arguments


def main() -> None:
    """
    Main entry point for the SOC-IQ application.
    """

    try:
        initialize_application()

        logger.info("Application started.")

        parse_arguments()

        print_banner()

        analyze_report()

    except SOCIQError as error:
        logger.error(str(error))

    except Exception:
        logger.exception(
            "Application terminated unexpectedly."
        )
        raise


if __name__ == "__main__":
    main()