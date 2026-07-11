from app.initializer import initialize_application

from app.display import print_banner

from app.analyzer import analyze_report

from app.logger import logger


def main() -> None:
    """
    Main entry point for the SOC-IQ application.
    """

    try:
        initialize_application()

        logger.info("Application started.")

        print_banner()

        analyze_report()

    except Exception:
        logger.exception(
            "Application terminated unexpectedly."
        )
        raise


if __name__ == "__main__":
    main()