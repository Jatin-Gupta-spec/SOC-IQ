import re

from app.exceptions import (
    IOCExtractionError,
    ReportReadError,
)


IOC_PATTERNS = {
    "IPv4": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",

    "Domains": (
        r"\b(?:[a-zA-Z0-9-]+\.)+"
        r"(?:com|net|org|io|co|ru|xyz|info|biz|edu|gov)\b"
    ),

    "URLs": (
        r"https?://"
        r"[^\s\"'<>]+"
    ),

    "Emails": (
        r"\b[a-zA-Z0-9._%+-]+@"
        r"[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"
    ),

    "MD5": (
        r"\b[a-fA-F0-9]{32}\b"
    ),

    "SHA1": (
        r"\b[a-fA-F0-9]{40}\b"
    ),

    "SHA256": (
        r"\b[a-fA-F0-9]{64}\b"
    ),

    "CVE": (
        r"\bCVE-\d{4}-\d{4,7}\b"
    ),

    "Windows File Paths": (
        r"[A-Za-z]:\\(?:[^\\/:*?\"<>|\r\n]+\\)*"
        r"[^\\/:*?\"<>|\r\n]*"
    ),

    "Windows Registry Keys": (
        r"\b(?:HKLM|HKCU|HKCR|HKU|HKCC)"
        r"\\[^\n\r]+"
    ),
}


COMPILED_PATTERNS = {
    name: re.compile(
        pattern,
        re.IGNORECASE,
    )
    for name, pattern in IOC_PATTERNS.items()
}


def read_report(report_path) -> str:
    """
    Read the malware report and return its contents.
    """

    try:

        with report_path.open(
            "r",
            encoding="utf-8",
        ) as file:

            return file.read()

    except OSError as error:

        raise ReportReadError(
            f"Failed to read report: {report_path}"
        ) from error


def extract_iocs(
    report: str,
    patterns: dict,
) -> dict:
    """
    Extract every IOC type from the report.

    Returns:
        Dictionary where:
            key = IOC type
            value = Sorted list of unique IOCs.
    """

    try:

        extracted = {}

        for ioc_type, pattern in patterns.items():

            matches = pattern.findall(report)

            extracted[ioc_type] = sorted(
                set(matches)
            )

        return extracted

    except Exception as error:

        raise IOCExtractionError(
            "Failed to extract IOCs from report."
        ) from error