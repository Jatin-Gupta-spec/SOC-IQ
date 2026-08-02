"""
Settings repository for SOC-IQ.

Responsible for persisting application settings to disk.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from app.settings.models import ApplicationSettings


class SettingsRepository:
    """
    Handles loading and saving application settings.
    """

    def __init__(self, settings_path: Path | None = None) -> None:
        self._settings_path = settings_path or Path("config") / "settings.json"

    def load(self) -> ApplicationSettings:
        """
        Load application settings.

        Returns default settings if the file does not exist or is invalid.
        """
        if not self._settings_path.exists():
            settings = ApplicationSettings()
            self.save(settings)
            return settings

        try:
            with self._settings_path.open(
                "r",
                encoding="utf-8",
            ) as file:
                data = json.load(file)

            return ApplicationSettings(**data)

        except (
            OSError,
            json.JSONDecodeError,
            TypeError,
            ValueError,
        ):
            settings = ApplicationSettings()
            self.save(settings)
            return settings

    def save(
        self,
        settings: ApplicationSettings,
    ) -> None:
        """
        Save application settings.
        """
        self._settings_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with self._settings_path.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                asdict(settings),
                file,
                indent=4,
            )
            file.flush()