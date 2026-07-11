from pathlib import Path

# ==========================================================
# Project Directories
# ==========================================================

BASE_DIR: Path = Path(__file__).resolve().parent.parent

SAMPLES_DIR: Path = BASE_DIR / "samples"
OUTPUT_DIR: Path = BASE_DIR / "output"
LOGS_DIR: Path = BASE_DIR / "logs"

# ==========================================================
# Default Files
# ==========================================================

SAMPLE_REPORT: Path = SAMPLES_DIR / "malware_report.txt"

JSON_EXPORT_FILE: Path = OUTPUT_DIR / "ioc_report.json"
CSV_EXPORT_FILE: Path = OUTPUT_DIR / "ioc_report.csv"

LOG_FILE: Path = LOGS_DIR / "soc_iq.log"

# ==========================================================
# Supported IOC Types
# ==========================================================

IOC_TYPES: tuple[str, ...] = (
    "IPv4",
    "Domain",
    "URL",
    "Email",
    "MD5",
    "SHA1",
    "SHA256",
    "CVE",
    "Windows File Path",
    "Windows Registry Key",
)

# ==========================================================
# Application Information
# ==========================================================

APP_NAME: str = "SOC-IQ"

APP_VERSION: str = "1.0.0"

APP_AUTHOR: str = "Himanshu Gupta"

APP_DESCRIPTION: str = (
    "Security Operations Center Intelligence & IOC Analysis Tool"
)