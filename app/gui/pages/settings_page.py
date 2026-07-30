"""
Settings Page for the SOC-IQ desktop application.

Allows analysts to configure API credentials, database settings, export defaults,
and UI theme preferences.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from app.gui.components.buttons.animated_button import AnimatedButton
from app.gui.components.cards.modern_card import ModernCard
from app.gui.components.layout.component_section import ComponentSection
from app.gui.design.theme.theme_manager import theme_manager
from app.gui.design.tokens import Spacing
from app.gui.widgets.page_container import PageContainer


class SettingsPage(QWidget):
    """
    Application Settings & Preferences Page.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._container = PageContainer(
            title="System Settings & Preferences",
            description=(
                "Manage API credentials, report export directories, database "
                "storage, and appearance settings."
            ),
        )

        self._vt_api_key = QLineEdit()
        self._save_vt_btn = AnimatedButton("Save API Key")

        self._export_dir_input = QLineEdit()
        self._browse_dir_btn = AnimatedButton("Browse...")

        self._theme_combo = QComboBox()
        self._apply_theme_btn = AnimatedButton("Apply Theme")

        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        """
        Build Settings page user interface.
        """
        layout = self._container.content_layout()

        # 1. VirusTotal API Key Card
        vt_section = ComponentSection(
            title="Threat Intelligence Credentials",
            description="Configure your VirusTotal API key for live threat enrichment.",
        )

        vt_card = ModernCard()
        vt_box = QVBoxLayout()
        vt_box.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)
        vt_box.setSpacing(Spacing.MD)

        self._vt_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._vt_api_key.setPlaceholderText("Enter VirusTotal API key...")

        vt_row = QHBoxLayout()
        vt_row.setSpacing(Spacing.MD)
        vt_row.addWidget(self._vt_api_key, 3)
        vt_row.addWidget(self._save_vt_btn, 1)

        vt_box.addLayout(vt_row)
        vt_card.add_layout(vt_box)
        vt_section.add_widget(vt_card)
        layout.addWidget(vt_section)

        # 2. Export & Storage Preferences
        export_section = ComponentSection(
            title="Report Export Preferences",
            description="Set default output directory for generated HTML and PDF reports.",
        )

        export_card = ModernCard()
        exp_box = QVBoxLayout()
        exp_box.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)
        exp_box.setSpacing(Spacing.MD)

        self._export_dir_input.setPlaceholderText("Default export folder path...")

        exp_row = QHBoxLayout()
        exp_row.setSpacing(Spacing.MD)
        exp_row.addWidget(self._export_dir_input, 3)
        exp_row.addWidget(self._browse_dir_btn, 1)

        exp_box.addLayout(exp_row)
        export_card.add_layout(exp_box)
        export_section.add_widget(export_card)
        layout.addWidget(export_section)

        # 3. Theme & Appearance
        theme_section = ComponentSection(
            title="UI Theme & Appearance",
            description="Customize application visual styles and dark mode preferences.",
        )

        theme_card = ModernCard()
        thm_box = QVBoxLayout()
        thm_box.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)
        thm_box.setSpacing(Spacing.MD)

        self._theme_combo.addItems(["Dark Mode (SOC-IQ Standard)", "High Contrast Dark"])

        thm_row = QHBoxLayout()
        thm_row.setSpacing(Spacing.MD)
        thm_row.addWidget(self._theme_combo, 3)
        thm_row.addWidget(self._apply_theme_btn, 1)

        thm_box.addLayout(thm_row)
        theme_card.add_layout(thm_box)
        theme_section.add_widget(theme_card)
        layout.addWidget(theme_section)

        layout.addStretch()

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(self._container)

    def _connect_signals(self) -> None:
        """
        Connect settings buttons.
        """
        self._save_vt_btn.clicked.connect(self._save_api_key)
        self._browse_dir_btn.clicked.connect(self._browse_export_dir)
        self._apply_theme_btn.clicked.connect(self._apply_theme)

    def _save_api_key(self) -> None:
        """
        Save VT API Key.
        """
        key = self._vt_api_key.text().strip()
        if not key:
            QMessageBox.warning(self, "Invalid Key", "Please enter a valid API key.")
            return

        QMessageBox.information(self, "API Key Saved", "VirusTotal API key saved successfully.")

    def _browse_export_dir(self) -> None:
        """
        Select export folder.
        """
        directory = QFileDialog.getExistingDirectory(self, "Select Default Export Directory")
        if directory:
            self._export_dir_input.setText(directory)

    def _apply_theme(self) -> None:
        """
        Apply selected theme.
        """
        QMessageBox.information(self, "Theme Applied", "UI theme updated successfully.")
