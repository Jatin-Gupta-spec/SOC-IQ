from app.extractor import (
    COMPILED_PATTERNS,
    extract_iocs,
    read_report,
)

from tests.fixtures.sample_reports import (
    SAMPLE_REPORT,
    DUPLICATE_IPV4_REPORT,
    NO_IPV4_REPORT,
)


def test_read_report_returns_file_contents(tmp_path):
    """
    Verify that read_report() returns the exact contents
    of a valid report file.
    """

    # Arrange
    report_text = (
        "IOC Report\n"
        "IP: 192.168.1.10\n"
        "Domain: evilcorp.com"
    )

    report_file = tmp_path / "report.txt"

    report_file.write_text(
        report_text,
        encoding="utf-8",
    )

    # Act
    result = read_report(report_file)

    # Assert
    assert result == report_text


def test_extract_ipv4_addresses():
    """
    Verify that IPv4 addresses are extracted correctly.
    """

    # Arrange
    report = SAMPLE_REPORT

    # Act
    results = extract_iocs(
        report,
        COMPILED_PATTERNS,
    )

    # Assert
    assert results["IPv4"] == [
        "192.168.1.10",
    ]


def test_duplicate_ipv4_addresses_are_removed():
    """
    Verify duplicate IPv4 addresses are removed.
    """

    # Arrange
    report = DUPLICATE_IPV4_REPORT

    # Act
    results = extract_iocs(
        report,
        COMPILED_PATTERNS,
    )

    # Assert
    assert results["IPv4"] == [
        "8.8.8.8",
    ]


def test_no_ipv4_addresses_found():
    """
    Verify an empty list is returned
    when no IPv4 addresses exist.
    """

    # Arrange
    report = NO_IPV4_REPORT

    # Act
    results = extract_iocs(
        report,
        COMPILED_PATTERNS,
    )

    # Assert
    assert results["IPv4"] == []


def test_extract_domains():
    """
    Verify domain names are extracted correctly.
    """

    # Act
    results = extract_iocs(
        SAMPLE_REPORT,
        COMPILED_PATTERNS,
    )

    # Assert
    assert results["Domains"] == [
        "evilcorp.com",
    ]


def test_extract_urls():
    """
    Verify URLs are extracted correctly.
    """

    # Act
    results = extract_iocs(
        SAMPLE_REPORT,
        COMPILED_PATTERNS,
    )

    # Assert
    assert results["URLs"] == [
        "https://evilcorp.com/payload.exe",
    ]


def test_extract_emails():
    """
    Verify email addresses are extracted correctly.
    """

    # Act
    results = extract_iocs(
        SAMPLE_REPORT,
        COMPILED_PATTERNS,
    )

    # Assert
    assert results["Emails"] == [
        "attacker@evilcorp.com",
    ]