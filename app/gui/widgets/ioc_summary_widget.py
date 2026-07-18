"""
Reusable IOC summary widget for the SOC-IQ desktop application.

This widget displays all extracted Indicators of Compromise
for a completed investigation.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.database.models import Investigation


class IOCSummaryWidget(QWidget):
    """
    Displays extracted Indicators of Compromise.
    """

    def __init__(self) -> None:
        super().__init__()

        self._content = QPlainTextEdit()

        self._content.setReadOnly(True)

        self._content.setPlainText(
            "Waiting for investigation..."
        )

        self._build_ui()

    def _build_ui(self) -> None:
        """
        Build the widget layout.
        """

        layout = QVBoxLayout()

        layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        layout.addWidget(
            self._content,
        )

        self.setLayout(
            layout,
        )

    def load_investigation(
        self,
        investigation: Investigation,
    ) -> None:
        """
        Display IOC information for an investigation.
        """

        ioc_titles = {
            "ipv4": "IPv4 Addresses",
            "domains": "Domains",
            "urls": "URLs",
            "emails": "Emails",
            "md5": "MD5 Hashes",
            "sha1": "SHA1 Hashes",
            "sha256": "SHA256 Hashes",
            "cves": "CVEs",
            "windows_file_paths": "Windows File Paths",
            "windows_registry_keys": "Registry Keys",
        }

        lines: list[str] = []

        for key, title in ioc_titles.items():
            values = investigation.iocs.get(
                key,
                [],
            )

            lines.append(title)
            lines.append(
                "-" * len(title)
            )

            if values:
                lines.extend(values)
            else:
                lines.append(
                    "None"
                )

            lines.append("")

        self._content.setPlainText(
            "\n".join(lines)
        )

    def reset(self) -> None:
        """
        Reset the widget.
        """

        self._content.setPlainText(
            "Waiting for investigation..."
        )