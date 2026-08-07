"""
Settings service for SOC-IQ.

Provides business logic for application settings.
"""

from __future__ import annotations

from app.logger import logger
from app.settings.models import ApplicationSettings
from app.settings.repository import SettingsRepository


class SettingsService:
    """
    Provides application settings operations.
    """

    def __init__(
        self,
        repository: SettingsRepository | None = None,
    ) -> None:
        self._repository = repository or SettingsRepository()

    def load_settings(self) -> ApplicationSettings:
        """
        Load application settings.

        Falls back to default settings rather than propagating a
        read failure. `SettingsPage.__init__` calls this unguarded
        while `MainWindow` is being constructed -- before the Qt
        event loop is running -- so an unhandled exception here
        (a missing or corrupted settings file, a permissions
        issue on first run, etc.) would otherwise prevent the
        entire application from starting rather than simply
        falling back to defaults for that one run.
        """
        try:

            return self._repository.load()

        except Exception:

            logger.exception(
                "Failed to load application settings; "
                "falling back to defaults."
            )

            return ApplicationSettings()

    def save_settings(
        self,
        settings: ApplicationSettings,
    ) -> None:
        """
        Save application settings.
        """
        self._repository.save(settings)

    def update_api_key(
        self,
        api_key: str,
    ) -> None:
        """
        Update the VirusTotal API key.
        """
        settings = self.load_settings()
        settings.virustotal_api_key = api_key.strip()
        self.save_settings(settings)

    def update_export_directory(
        self,
        export_directory: str,
    ) -> None:
        """
        Update the default export directory.
        """
        settings = self.load_settings()
        settings.export_directory = export_directory.strip()
        self.save_settings(settings)

    def update_theme(
        self,
        theme: str,
    ) -> None:
        """
        Update the application theme.
        """
        settings = self.load_settings()
        settings.theme = theme
        self.save_settings(settings)