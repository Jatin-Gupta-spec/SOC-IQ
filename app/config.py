from pathlib import Path

# ==========================================================
# Application Information
# ==========================================================

APP_NAME = "SOC-IQ"
APP_VERSION = "1.0.0"
APP_AUTHOR = "Himanshu Gupta"
APP_DESCRIPTION = (
    "Security Operations Center Intelligence & IOC Analysis Tool"
)

# ==========================================================
# Project Directories
# ==========================================================

BASE_DIR = Path(__file__).resolve().parent.parent

SAMPLES_DIR = BASE_DIR / "samples"
OUTPUT_DIR = BASE_DIR / "output"
LOGS_DIR = BASE_DIR / "logs"

# ==========================================================
# Default Files
# ==========================================================

SAMPLE_REPORT_FILE = SAMPLES_DIR / "malware_report.txt"

JSON_EXPORT_FILE = OUTPUT_DIR / "ioc_report.json"
CSV_EXPORT_FILE = OUTPUT_DIR / "ioc_report.csv"

LOG_FILE = LOGS_DIR / "soc_iq.log"

# ==========================================================
# Supported IOC Types
# ==========================================================

IOC_TYPES = (
    "IPv4",
    "Domains",
    "URLs",
    "Emails",
    "MD5",
    "SHA1",
    "SHA256",
    "CVE",
    "Windows File Paths",
    "Windows Registry Keys",
)