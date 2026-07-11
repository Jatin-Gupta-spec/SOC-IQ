from app.config import (
    APP_NAME,
    APP_VERSION,
    APP_AUTHOR,
    APP_DESCRIPTION,
    SAMPLE_REPORT_FILE,
)

from app.initializer import initialize_application

from app.extractor import (
    IOC_PATTERNS,
    read_report,
    extract_iocs,
)

from app.display import (
    print_banner,
    display_summary,
    display_iocs,
)

from app.exporters import (
    export_to_json,
    export_to_csv,
)

from app.logger import logger


def main():
    """
    Main entry point for the SOC-IQ application.
    """

    try:
        # Prepare the application environment
        initialize_application()

        logger.info("Application started.")

        # Display application information
        print_banner()

        logger.info("Reading malware report...")
        report_text = read_report(SAMPLE_REPORT_FILE)

        logger.info("Extracting IOCs...")
        extracted_iocs = extract_iocs(
            report_text,
            IOC_PATTERNS,
        )

        logger.info("Displaying results...")
        display_summary(extracted_iocs)
        display_iocs(extracted_iocs)

        logger.info("Exporting JSON report...")
        export_to_json(extracted_iocs)

        logger.info("JSON report exported successfully.")

        logger.info("Exporting CSV report...")
        export_to_csv(extracted_iocs)

        logger.info("CSV report exported successfully.")

        logger.info("IOC extraction completed successfully.")

    except Exception:
        logger.exception("Application terminated unexpectedly.")
        raise


if __name__ == "__main__":
    main()