"""
Shared fixtures for headless PySide6 GUI tests.

These tests exercise real Qt widgets rather than mocks, so they
need a running `QApplication` and, since this suite runs in CI /
sandboxed environments with no display server, the "offscreen"
platform plugin. Forcing `QT_QPA_PLATFORM=offscreen` here (rather
than relying on it being set in the environment already) means
`pytest tests/gui` works the same way locally and in CI without
extra setup.

A single `QApplication` is created once per test session:
PySide6/Qt does not support constructing more than one in the same
process, and every widget test in this package needs one alive for
the whole run.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    """
    Provide a single `QApplication` instance for the test session.
    """

    app = QApplication.instance()

    if app is None:
        app = QApplication([])

    yield app
