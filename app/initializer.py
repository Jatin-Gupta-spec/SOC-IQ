from app.config import LOGS_DIR, OUTPUT_DIR


def initialize_application() -> None:
    """
    Prepare the application environment before execution.
    Creates required directories if they do not already exist.
    """

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)