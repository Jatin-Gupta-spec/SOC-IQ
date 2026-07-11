import sys

import pytest

from app.cli import parse_arguments
from app.config import (
    APP_NAME,
    APP_VERSION,
    SAMPLE_REPORT,
)


def test_default_arguments(monkeypatch):
    """
    Verify default CLI arguments.
    """

    monkeypatch.setattr(
        sys,
        "argv",
        ["soc-iq"],
    )

    args = parse_arguments()

    assert args.input == str(SAMPLE_REPORT)
    assert args.json is False
    assert args.csv is False


def test_input_argument(monkeypatch):
    """
    Verify --input overrides the default report.
    """

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "soc-iq",
            "--input",
            "custom_report.txt",
        ],
    )

    args = parse_arguments()

    assert args.input == "custom_report.txt"


def test_json_argument(monkeypatch):
    """
    Verify --json enables JSON export.
    """

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "soc-iq",
            "--json",
        ],
    )

    args = parse_arguments()

    assert args.json is True
    assert args.csv is False


def test_csv_argument(monkeypatch):
    """
    Verify --csv enables CSV export.
    """

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "soc-iq",
            "--csv",
        ],
    )

    args = parse_arguments()

    assert args.csv is True
    assert args.json is False


def test_json_and_csv_arguments(monkeypatch):
    """
    Verify JSON and CSV exports can both be enabled.
    """

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "soc-iq",
            "--json",
            "--csv",
        ],
    )

    args = parse_arguments()

    assert args.json is True
    assert args.csv is True


def test_version_argument(monkeypatch, capsys):
    """
    Verify --version prints the application version.
    """

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "soc-iq",
            "--version",
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        parse_arguments()

    assert exc_info.value.code == 0

    captured = capsys.readouterr()

    assert captured.out.strip() == f"{APP_NAME} {APP_VERSION}"