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

    result = read_report(report_file)

    assert result == report_text


def test_extract_ipv4_addresses():
    results = extract_iocs(
        SAMPLE_REPORT,
        COMPILED_PATTERNS,
    )

    assert results["ipv4"] == [
        "192.168.1.10",
    ]


def test_duplicate_ipv4_addresses_are_removed():
    results = extract_iocs(
        DUPLICATE_IPV4_REPORT,
        COMPILED_PATTERNS,
    )

    assert results["ipv4"] == [
        "8.8.8.8",
    ]


def test_no_ipv4_addresses_found():
    results = extract_iocs(
        NO_IPV4_REPORT,
        COMPILED_PATTERNS,
    )

    assert results["ipv4"] == []


def test_extract_domains():
    results = extract_iocs(
        SAMPLE_REPORT,
        COMPILED_PATTERNS,
    )

    assert results["domains"] == [
        "evilcorp.com",
    ]


def test_extract_urls():
    results = extract_iocs(
        SAMPLE_REPORT,
        COMPILED_PATTERNS,
    )

    assert results["urls"] == [
        "https://evilcorp.com/payload.exe",
    ]


def test_extract_emails():
    results = extract_iocs(
        SAMPLE_REPORT,
        COMPILED_PATTERNS,
    )

    assert results["emails"] == [
        "attacker@evilcorp.com",
    ]


def test_extract_md5():
    results = extract_iocs(
        SAMPLE_REPORT,
        COMPILED_PATTERNS,
    )

    assert results["md5"] == [
        "44d88612fea8a8f36de82e1278abb02f",
    ]


def test_extract_sha1():
    results = extract_iocs(
        SAMPLE_REPORT,
        COMPILED_PATTERNS,
    )

    assert results["sha1"] == [
        "7c4a8d09ca3762af61e59520943dc26494f8941b",
    ]


def test_extract_sha256():
    results = extract_iocs(
        SAMPLE_REPORT,
        COMPILED_PATTERNS,
    )

    assert results["sha256"] == [
        "3f786850e387550fdab836ed7e6dc881de23001b4fb5d6fcb5b8f8f9d4f6b6c5",
    ]


def test_extract_cve():
    results = extract_iocs(
        SAMPLE_REPORT,
        COMPILED_PATTERNS,
    )

    assert results["cves"] == [
        "CVE-2024-4577",
    ]


def test_extract_windows_file_paths():
    results = extract_iocs(
        SAMPLE_REPORT,
        COMPILED_PATTERNS,
    )

    assert results["windows_file_paths"] == [
        "C:\\Windows\\System32\\cmd.exe",
    ]


def test_extract_registry_keys():
    results = extract_iocs(
        SAMPLE_REPORT,
        COMPILED_PATTERNS,
    )

    assert results["windows_registry_keys"] == [
        "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run",
    ]