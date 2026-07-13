import logging

from app.config import LOG_FILE

logger: logging.Logger = logging.getLogger("SOC-IQ")


def configure_logger(verbose: bool = False) -> None:
    """
    Configure application logging.
    """

    logger.setLevel(logging.INFO)

    logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s"
    )

    file_handler = logging.FileHandler(
        LOG_FILE,
        encoding="utf-8",
    )

    file_handler.setFormatter(formatter)

    logger.addHandler(file_handler)

    if verbose:
        console_handler = logging.StreamHandler()

        console_handler.setFormatter(formatter)

        logger.addHandler(console_handler)