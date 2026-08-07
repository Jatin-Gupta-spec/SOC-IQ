"""
Settings repository for SOC-IQ.

Responsible for persisting application settings to disk.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path

from app.logger import logger
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
            # Falling back to defaults silently would make a corrupt
            # or unreadable settings file (and whatever it held --
            # e.g. a configured VirusTotal key) disappear without any
            # trace. Log it so this is diagnosable, without echoing
            # the file contents (which may contain the API key).
            logger.exception(
                "Failed to load settings from %s; "
                "resetting to defaults.",
                self._settings_path,
            )

            settings = ApplicationSettings()
            self.save(settings)
            return settings

    def save(
        self,
        settings: ApplicationSettings,
    ) -> None:
        """
        Save application settings.

        Writes atomically: the new content is written to a temporary
        file in the same directory and then moved into place with
        `os.replace`, which is atomic on both POSIX and Windows. This
        guarantees `settings.json` is either the old complete file or
        the new complete file, never a partially-written one -- a
        crash or power loss mid-write can no longer corrupt it (and
        silently cost the user their saved API key on next load).
        """
        directory = self._settings_path.parent

        directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        fd, tmp_name = tempfile.mkstemp(
            dir=directory,
            prefix=f".{self._settings_path.name}.",
            suffix=".tmp",
        )

        try:
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                json.dump(
                    asdict(settings),
                    file,
                    indent=4,
                )
                file.flush()
                os.fsync(file.fileno())

            os.replace(tmp_name, self._settings_path)

        except BaseException:
            # Clean up the temp file if anything went wrong before
            # (or during) the atomic rename, so we don't leave stray
            # .tmp files behind on every failed save.
            try:
                os.remove(tmp_name)
            except OSError:
                pass
            raise