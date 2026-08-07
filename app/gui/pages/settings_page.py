"""
Settings Page for the SOC-IQ desktop application.

Allows analysts to configure API credentials, database settings, export defaults,
and UI theme preferences.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from app.gui.components.buttons.animated_button import AnimatedButton
from app.gui.components.cards.modern_card import ModernCard
from app.gui.components.layout.component_section import ComponentSection
from app.gui.design.tokens import Spacing
from app.gui.events.application_events import events
from app.gui.widgets.page_container import PageContainer
from app.settings.service import SettingsService


class SettingsPage(QWidget):
    """
    Application Settings & Preferences Page.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._settings_service = SettingsService()

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
        self._load_settings()
        self._connect_signals()

    def _build_ui(self) -> None:
        """
        Build Settings page user interface.
        """
        layout = self._container.content_layout()

        # Threat Intelligence
        vt_section = ComponentSection(
            title="Threat Intelligence Credentials",
            description="Configure your VirusTotal API key for live threat enrichment.",
        )

        vt_card = ModernCard()
        vt_layout = QVBoxLayout()
        vt_layout.setContentsMargins(
            Spacing.LG,
            Spacing.LG,
            Spacing.LG,
            Spacing.LG,
        )
        vt_layout.setSpacing(Spacing.MD)

        self._vt_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._vt_api_key.setPlaceholderText(
            "Enter VirusTotal API key..."
        )

        vt_row = QHBoxLayout()
        vt_row.setSpacing(Spacing.MD)
        vt_row.addWidget(self._vt_api_key, 3)
        vt_row.addWidget(self._save_vt_btn, 1)

        vt_layout.addLayout(vt_row)
        vt_card.add_layout(vt_layout)
        vt_section.add_widget(vt_card)
        layout.addWidget(vt_section)

        # Export Preferences
        export_section = ComponentSection(
            title="Report Export Preferences",
            description="Set the default export directory for generated reports.",
        )

        export_card = ModernCard()
        export_layout = QVBoxLayout()
        export_layout.setContentsMargins(
            Spacing.LG,
            Spacing.LG,
            Spacing.LG,
            Spacing.LG,
        )
        export_layout.setSpacing(Spacing.MD)

        self._export_dir_input.setPlaceholderText(
            "Default export folder..."
        )

        export_row = QHBoxLayout()
        export_row.setSpacing(Spacing.MD)
        export_row.addWidget(self._export_dir_input, 3)
        export_row.addWidget(self._browse_dir_btn, 1)

        export_layout.addLayout(export_row)
        export_card.add_layout(export_layout)
        export_section.add_widget(export_card)
        layout.addWidget(export_section)

        # Theme
        theme_section = ComponentSection(
            title="UI Theme & Appearance",
            description="Configure application appearance.",
        )

        theme_card = ModernCard()
        theme_layout = QVBoxLayout()
        theme_layout.setContentsMargins(
            Spacing.LG,
            Spacing.LG,
            Spacing.LG,
            Spacing.LG,
        )
        theme_layout.setSpacing(Spacing.MD)

        self._theme_combo.addItems(
            [
                "Dark Mode (SOC-IQ Standard)",
                "High Contrast Dark",
            ]
        )

        theme_row = QHBoxLayout()
        theme_row.setSpacing(Spacing.MD)
        theme_row.addWidget(self._theme_combo, 3)
        theme_row.addWidget(self._apply_theme_btn, 1)

        theme_layout.addLayout(theme_row)
        theme_card.add_layout(theme_layout)
        theme_section.add_widget(theme_card)
        layout.addWidget(theme_section)

        layout.addStretch()

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(self._container)

    def _load_settings(self) -> None:
        """
        Load saved application settings into the UI.
        """
        settings = self._settings_service.load_settings()

        self._vt_api_key.setText(settings.virustotal_api_key)
        self._export_dir_input.setText(settings.export_directory)

        index = self._theme_combo.findText(settings.theme)

        if index >= 0:
            self._theme_combo.setCurrentIndex(index)

    def _connect_signals(self) -> None:
        """
        Connect settings buttons.
        """
        self._save_vt_btn.clicked.connect(self._save_api_key)
        self._browse_dir_btn.clicked.connect(self._browse_export_dir)
        self._apply_theme_btn.clicked.connect(self._apply_theme)

    def _save_api_key(self) -> None:
        """
        Save VirusTotal API key.
        """
        key = self._vt_api_key.text().strip()

        if not key:
            QMessageBox.warning(
                self,
                "Invalid Key",
                "Please enter a valid API key.",
            )
            return

        try:
            self._settings_service.update_api_key(key)
        except Exception as error:
            # Previously an exception here (disk write
            # failure, permissions, etc.) would propagate
            # straight out of a Qt slot uncaught. Depending
            # on platform/binding, that ranges from a silent
            # no-op to a hard crash — never a clear message
            # to the analyst that their key wasn't saved.
            QMessageBox.critical(
                self,
                "Save Failed",
                f"Could not save the VirusTotal API key:\n{error}",
            )
            return

        QMessageBox.information(
            self,
            "Success",
            "VirusTotal API key saved successfully.",
        )

        # Nothing previously told the rest of the running
        # app that credentials changed. Concretely: the
        # Threat Intelligence page builds its VirusTotalClient
        # once at construction time — without this signal, a
        # freshly saved key is silently ignored by any page
        # already open until the app is restarted.
        events.settings_changed.emit({"virustotal_api_key": key})

    def _browse_export_dir(self) -> None:
        """
        Select and save export directory.
        """
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Default Export Directory",
        )

        if not directory:
            return

        self._export_dir_input.setText(directory)

        try:
            self._settings_service.update_export_directory(directory)
        except Exception as error:
            QMessageBox.critical(
                self,
                "Save Failed",
                f"Could not save the export directory:\n{error}",
            )
            return

        events.settings_changed.emit({"export_directory": directory})

    def _apply_theme(self) -> None:
        """
        Save selected theme.
        """
        theme = self._theme_combo.currentText()

        try:
            self._settings_service.update_theme(theme)
        except Exception as error:
            QMessageBox.critical(
                self,
                "Save Failed",
                f"Could not save the theme preference:\n{error}",
            )
            return

        QMessageBox.information(
            self,
            "Success",
            "Theme preference saved.",
        )

        # Persisting the choice is not the same as applying
        # it. Broadcasting this lets whatever owns live
        # theming (ThemeManager / MainWindow — not part of
        # this review) react and restyle immediately instead
        # of requiring an app restart for "Apply Theme" to
        # actually apply anything.
        events.settings_changed.emit({"theme": theme})