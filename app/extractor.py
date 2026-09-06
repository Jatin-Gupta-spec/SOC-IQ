"""
IOC extraction engine for SOC-IQ.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from app.exceptions import (
    IOCExtractionError,
    ReportReadError,
)

# ==========================================================
# Ingestion Limits
# ==========================================================

#: §20 security hardening (docs/security/report-ingestion-security-model.md
#: TARGET STATE: "Explicit input size limits are enforced ... before a
#: report reaches the extraction pipeline"): read_report() previously read
#: an uncapped file fully into memory before any of the regex passes below
#: ran, over an IPC-reachable command (analyze_report) as well as the local
#: GUI/CLI paths -- an unbounded local resource-exhaustion vector. No prior
#: document or config anywhere in this project specifies a concrete ceiling,
#: so this value is a deliberate, documented choice rather than a spec
#: citation: real malware/threat-intel text reports this tool is designed
#: to ingest are realistically well under a few hundred KB to low single-digit
#: MB; 10 MB leaves generous headroom for a legitimate large report while
#: still bounding worst-case memory use and regex-pass cost to a fixed,
#: small multiple of that figure. Revisit if a legitimate report format
#: this tool needs to support routinely exceeds it.
MAX_REPORT_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB

# ==========================================================
# IOC Regular Expressions
# ==========================================================

IOC_PATTERNS: dict[str, str] = {
    "ipv4": (
        r"\b(?:\d{1,3}\.){3}\d{1,3}\b"
    ),

    "domains": (
        r"\b(?:[a-zA-Z0-9-]+\.)+"
        r"(?:com|net|org|io|co|ru|xyz|info|biz|edu|gov)\b"
    ),

    "urls": (
        r"https?://"
        r"[^\s\"'<>]+"
    ),

    "emails": (
        r"\b[a-zA-Z0-9._%+-]+@"
        r"[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"
    ),

    "md5": (
        r"\b[a-fA-F0-9]{32}\b"
    ),

    "sha1": (
        r"\b[a-fA-F0-9]{40}\b"
    ),

    "sha256": (
        r"\b[a-fA-F0-9]{64}\b"
    ),

    "cves": (
        r"\bCVE-\d{4}-\d{4,7}\b"
    ),

    "windows_file_paths": (
        r"[A-Za-z]:\\(?:[^\\/:*?\"<>|\r\n]+\\)*"
        r"[^\\/:*?\"<>|\r\n]*"
    ),

    "windows_registry_keys": (
        r"\b(?:HKLM|HKCU|HKCR|HKU|HKCC)"
        r"\\[^\n\r]+"
    ),
}

# ==========================================================
# Precompiled Patterns
# ==========================================================

COMPILED_PATTERNS: dict[
    str,
    re.Pattern[str],
] = {
    name: re.compile(
        pattern,
        re.IGNORECASE,
    )
    for name, pattern in IOC_PATTERNS.items()
}

# ==========================================================
# Report Reader
# ==========================================================


def _stat_size_or_raise(
    report_path: Path,
) -> int:
    """
    Return `report_path`'s size in bytes via `stat()`, without ever
    opening the file for reading.

    Shared by `read_report()` and `compute_source_provenance()` so the
    §20 pre-open size-cap invariant (proven by
    `tests/test_report_ingestion_size_cap.py`'s
    `test_oversized_report_is_rejected_without_ever_opening_the_file`)
    has exactly one implementation instead of two that could drift.

    Raises:
        ReportReadError:
            If `stat()` fails, or the file exceeds
            MAX_REPORT_SIZE_BYTES.
    """

    try:

        size = report_path.stat().st_size

    except OSError as error:

        raise ReportReadError(
            f"Failed to read report: {report_path}"
        ) from error

    if size > MAX_REPORT_SIZE_BYTES:

        raise ReportReadError(
            f"Report exceeds the maximum allowed size of "
            f"{MAX_REPORT_SIZE_BYTES} bytes "
            f"(got {size} bytes): {report_path}"
        )

    return size


def read_report(
    report_path: Path,
) -> str:
    """
    Read a malware report.

    Args:
        report_path:
            Path to the malware report.

    Returns:
        Report contents.

    Raises:
        ReportReadError:
            If the report cannot be read, or exceeds
            MAX_REPORT_SIZE_BYTES.
    """

    _stat_size_or_raise(report_path)

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

    except UnicodeDecodeError as error:

        # `UnicodeDecodeError` is a `ValueError` subclass, not an
        # `OSError` subclass, so it was previously NOT caught by the
        # clause above. A report that isn't valid UTF-8 (binary
        # content, a different source encoding, etc.) is a
        # realistic, not hypothetical, input for a malware-report
        # reader, and letting the raw decode error escape means the
        # pipeline fails with an unhandled exception instead of the
        # documented `ReportReadError`.
        raise ReportReadError(
            f"Failed to read report: {report_path} "
            "(not valid UTF-8 text)"
        ) from error


# ==========================================================
# Source Provenance
# ==========================================================


@dataclass(frozen=True, slots=True)
class SourceProvenance:
    """
    The result of reading a source report while also establishing its
    integrity identity (A4-P1 evidence provenance).

    `sha256` is computed over `raw_bytes` -- the exact bytes accepted
    by the §20 size cap and read from disk -- never over `text` (the
    decoded string), a filename, or any reconstructed/normalized
    representation. This is the distinction Phase A4-P1's design
    deliberately calls out: the primary source hash must correspond
    to the bytes supplied to the analysis pipeline, not to anything
    derived from them.
    """

    text: str
    sha256: str
    size_bytes: int


def compute_source_provenance(
    report_path: Path,
) -> SourceProvenance:
    """
    Read a malware report exactly once, returning both its decoded
    text and its integrity identity (SHA-256 + size) in a single pass.

    This is the ingestion entry point `app.analyzer.analyze_report`
    uses in place of a bare `read_report()` call: it reuses the same
    pre-open, stat()-based size check (`_stat_size_or_raise`) so the
    existing §20 report-size protection is not weakened, then reads
    the file's raw bytes exactly once and hashes those same bytes --
    never a second read, and never a hash of anything other than the
    actual accepted input.

    Args:
        report_path:
            Path to the malware report.

    Returns:
        A `SourceProvenance` with the decoded report text, its
        SHA-256 hex digest, and its size in bytes.

    Raises:
        ReportReadError:
            If the report cannot be read, exceeds
            MAX_REPORT_SIZE_BYTES, or is not valid UTF-8 text --
            identical failure modes to `read_report()`.
    """

    _stat_size_or_raise(report_path)

    try:

        raw_bytes = report_path.read_bytes()

    except OSError as error:

        raise ReportReadError(
            f"Failed to read report: {report_path}"
        ) from error

    digest = hashlib.sha256(raw_bytes).hexdigest()

    try:

        text = raw_bytes.decode("utf-8")

    except UnicodeDecodeError as error:

        raise ReportReadError(
            f"Failed to read report: {report_path} "
            "(not valid UTF-8 text)"
        ) from error

    return SourceProvenance(
        text=text,
        sha256=digest,
        size_bytes=len(raw_bytes),
    )


# ==========================================================
# IOC Extraction
# ==========================================================


def extract_iocs(
    report: str,
    patterns: dict[
        str,
        re.Pattern[str],
    ],
) -> dict[
    str,
    list[str],
]:
    """
    Extract Indicators of Compromise (IOCs)
    from a malware report.

    Args:
        report:
            Malware report text.

        patterns:
            Compiled IOC regex patterns.

    Returns:
        Dictionary mapping IOC type to
        sorted unique IOC values.

    Raises:
        IOCExtractionError:
            If extraction fails.
    """

    try:

        extracted: dict[
            str,
            list[str],
        ] = {}

        for ioc_type, pattern in patterns.items():

            matches = pattern.findall(
                report,
            )

            extracted[ioc_type] = sorted(
                set(matches)
            )

        return extracted

    except Exception as error:

        raise IOCExtractionError(
            "Failed to extract IOCs from report."
        ) from error