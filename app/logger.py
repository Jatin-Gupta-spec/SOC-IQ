import logging

from app.config import LOG_FILE

logger: logging.Logger = logging.getLogger("SOC-IQ")


def configure_logger(verbose: bool = False) -> None:
    """
    Configure application logging.

    Safe to call more than once (e.g. toggling verbose mode): any
    previously attached handlers are flushed and closed before being
    replaced, instead of just dropped, which would otherwise leak
    open file descriptors on the old log file each time this runs.
    """

    logger.setLevel(logging.INFO)

    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)

    # LOG_FILE's parent is normally created by initialize_application()
    # during startup, but logging should not depend on that ordering --
    # a caller that configures logging before app init (or a directory
    # that was removed at runtime) would otherwise hit an unhandled
    # FileNotFoundError here.
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

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