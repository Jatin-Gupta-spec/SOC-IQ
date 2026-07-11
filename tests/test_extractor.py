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

    results = extract_iocs(
        SAMPLE_REPORT,
        COMPILED_PATTERNS,
    )

    assert results["IPv4"] == [
        "192.168.1.10",
    ]


def test_duplicate_ipv4_addresses_are_removed():
    """
    Verify duplicate IPv4 addresses are removed.
    """

    results = extract_iocs(
        DUPLICATE_IPV4_REPORT,
        COMPILED_PATTERNS,
    )

    assert results["IPv4"] == [
        "8.8.8.8",
    ]


def test_no_ipv4_addresses_found():
    """
    Verify an empty list is returned
    when no IPv4 addresses exist.
    """

    results = extract_iocs(
        NO_IPV4_REPORT,
        COMPILED_PATTERNS,
    )

    assert results["IPv4"] == []


def test_extract_domains():
    """
    Verify domain names are extracted correctly.
    """

    results = extract_iocs(
        SAMPLE_REPORT,
        COMPILED_PATTERNS,
    )

    assert results["Domains"] == [
        "evilcorp.com",
    ]


def test_extract_urls():
    """
    Verify URLs are extracted correctly.
    """

    results = extract_iocs(
        SAMPLE_REPORT,
        COMPILED_PATTERNS,
    )

    assert results["URLs"] == [
        "https://evilcorp.com/payload.exe",
    ]


def test_extract_emails():
    """
    Verify email addresses are extracted correctly.
    """

    results = extract_iocs(
        SAMPLE_REPORT,
        COMPILED_PATTERNS,
    )

    assert results["Emails"] == [
        "attacker@evilcorp.com",
    ]


def test_extract_md5():
    """
    Verify MD5 hashes are extracted correctly.
    """

    results = extract_iocs(
        SAMPLE_REPORT,
        COMPILED_PATTERNS,
    )

    assert results["MD5"] == [
        "44d88612fea8a8f36de82e1278abb02f",
    ]


def test_extract_sha1():
    """
    Verify SHA1 hashes are extracted correctly.
    """

    results = extract_iocs(
        SAMPLE_REPORT,
        COMPILED_PATTERNS,
    )

    assert results["SHA1"] == [
        "7c4a8d09ca3762af61e59520943dc26494f8941b",
    ]


def test_extract_sha256():
    """
    Verify SHA256 hashes are extracted correctly.
    """

    results = extract_iocs(
        SAMPLE_REPORT,
        COMPILED_PATTERNS,
    )

    assert results["SHA256"] == [
        "3f786850e387550fdab836ed7e6dc881de23001b4fb5d6fcb5b8f8f9d4f6b6c5",
    ]


def test_extract_cve():
    """
    Verify CVE identifiers are extracted correctly.
    """

    results = extract_iocs(
        SAMPLE_REPORT,
        COMPILED_PATTERNS,
    )

    assert results["CVE"] == [
        "CVE-2024-4577",
    ]


def test_extract_windows_file_paths():
    """
    Verify Windows file paths are extracted correctly.
    """

    results = extract_iocs(
        SAMPLE_REPORT,
        COMPILED_PATTERNS,
    )

    assert results["Windows File Paths"] == [
        "C:\\Windows\\System32\\cmd.exe",
    ]


def test_extract_registry_keys():
    """
    Verify Windows registry keys are extracted correctly.
    """

    results = extract_iocs(
        SAMPLE_REPORT,
        COMPILED_PATTERNS,
    )

    assert results["Windows Registry Keys"] == [
        "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run",
    ]