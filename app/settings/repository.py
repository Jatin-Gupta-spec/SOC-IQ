"""
Settings repository for SOC-IQ.

Responsible for persisting application settings. As of Phase 4M
Part 2B, this repository is a "split" persistence boundary:

* `export_directory` / `theme` are non-secret, low-stakes
  configuration and continue to live in `config/settings.json` on
  disk, exactly as before.
* `virustotal_api_key` is a credential and is never written to
  `config/settings.json` (or any other plaintext file) anymore. It
  is sourced exclusively through a `SecretStore`
  (`app.secrets.store.SecretStore` -- backed by the read-only Rust
  keystore handoff via `RustKeystoreHandoffSecretStore` in
  production, per ADR-008 / Phase 4O Security Part 1B-2), per the
  Part 2A foundation and the Part 2B integration brief.

  As of Part 1B-2, the production `SecretStore` is read-only: Rust
  owns credential storage exclusively, so `save_api_key()` and the
  legacy-plaintext migration below now always raise (a
  `SecretStoreReadOnlyError`, a `SecretStoreUnavailableError`
  subclass) when they reach the real store, since there is no
  Python-side write path left to reach. Existing callers that
  already handle `SecretStoreUnavailableError` safely continue to
  do so unchanged.

Callers still see a single `ApplicationSettings` object with all
three fields populated -- `load()` transparently merges the disk
file and the secret store into one object, and `save()`/`save_api_key()`
route each field to the right backend. Nothing above this repository
(SettingsService, the GUI, the command handlers, VirusTotalClient)
needs to know that split exists.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path

from app.config import SETTINGS_FILE
from app.logger import logger
from app.secrets.exceptions import (
    SecretNotFoundError,
    SecretStoreUnavailableError,
)
from app.secrets.store import RustKeystoreHandoffSecretStore, SecretStore
from app.settings.models import ApplicationSettings

#: The name this repository stores the VirusTotal API key under in
#: the secret store. Kept as a module constant (rather than
#: inlined at each call site) so there is exactly one place that
#: defines "which secret is the VT key" -- matching the pattern
#: `app/secrets/store.py`'s own docstring uses as its example name.
_VT_API_KEY_SECRET_NAME = "virustotal_api_key"


class SettingsRepository:
    """
    Handles loading and saving application settings.
    """

    def __init__(
        self,
        settings_path: Path | None = None,
        secret_store: SecretStore | None = None,
    ) -> None:
        self._settings_path = settings_path or SETTINGS_FILE
        # Real production default is the read-only Rust keystore
        # handoff (ADR-008). Tests (and any other caller that needs
        # a deterministic, non-environment collaborator) inject
        # their own SecretStore -- see
        # tests/fixtures/fake_secret_store.py.
        self._secret_store: SecretStore = (
            secret_store or RustKeystoreHandoffSecretStore()
        )

    def load(self) -> ApplicationSettings:
        """
        Load application settings.

        Returns default settings if the file does not exist or is invalid.
        The VirusTotal API key, if any, always comes from the secret
        store rather than from disk -- see the module docstring.
        """
        if not self._settings_path.exists():
            settings = ApplicationSettings()
            self._populate_api_key_from_store(settings)
            self.save(settings)
            return settings

        try:
            with self._settings_path.open(
                "r",
                encoding="utf-8",
            ) as file:
                data = json.load(file)

            # Legacy on-disk field: earlier (pre-Part-2B) versions of
            # this repository wrote the plaintext VT key straight into
            # settings.json. Pop it out before constructing
            # ApplicationSettings so it is never treated as this
            # load's source of truth for the key, then migrate it into
            # the secret store below -- see _migrate_legacy_plaintext_key.
            legacy_plaintext_key = data.pop(_VT_API_KEY_SECRET_NAME, None)

            settings = ApplicationSettings(**data)

        except (
            OSError,
            json.JSONDecodeError,
            TypeError,
            ValueError,
        ):
            # Falling back to defaults silently would make a corrupt
            # or unreadable settings file disappear without any
            # trace. Log it so this is diagnosable, without echoing
            # the file contents.
            logger.exception(
                "Failed to load settings from %s; "
                "resetting to defaults.",
                self._settings_path,
            )

            settings = ApplicationSettings()
            self._populate_api_key_from_store(settings)
            self.save(settings)
            return settings

        if isinstance(legacy_plaintext_key, str) and legacy_plaintext_key.strip():
            migrated = self._migrate_legacy_plaintext_key(legacy_plaintext_key)
            if migrated:
                # Rewrite the file now, not just on the next save() --
                # save() already excludes virustotal_api_key from the
                # payload, so this is exactly what strips the
                # plaintext copy off disk immediately rather than
                # leaving it there until something else happens to
                # call save() later.
                self.save(settings)

        self._populate_api_key_from_store(settings)
        return settings

    def save(
        self,
        settings: ApplicationSettings,
    ) -> None:
        """
        Save the non-secret portion of application settings
        (`export_directory`, `theme`) to disk.

        `virustotal_api_key` is deliberately excluded from the
        persisted JSON -- it is never written here, whatever value
        `settings.virustotal_api_key` currently holds. Callers that
        want to change the stored API key must use `save_api_key()`
        instead, which routes it to the secret store. This keeps
        "save some settings" from ever becoming an accidental path
        for a plaintext credential to reach disk.

        Writes atomically: the new content is written to a temporary
        file in the same directory and then moved into place with
        `os.replace`, which is atomic on both POSIX and Windows. This
        guarantees `settings.json` is either the old complete file or
        the new complete file, never a partially-written one.
        """
        directory = self._settings_path.parent

        directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        payload = asdict(settings)
        payload.pop(_VT_API_KEY_SECRET_NAME, None)

        fd, tmp_name = tempfile.mkstemp(
            dir=directory,
            prefix=f".{self._settings_path.name}.",
            suffix=".tmp",
        )

        try:
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                json.dump(
                    payload,
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

    def save_api_key(self, api_key: str) -> None:
        """
        Persist the VirusTotal API key to the secret store.

        A blank/whitespace-only value is treated as "unset" and
        deletes any previously stored key, rather than storing an
        empty string -- mirroring how `has_secret()`/`is_configured()`
        checks are used elsewhere to mean "a real key is configured".

        Raises `SecretStoreUnavailableError` if the underlying store
        cannot be reached -- including, against the real production
        store, a `SecretStoreReadOnlyError` (a `SecretStoreUnavailableError`
        subclass), since Rust is the sole owner of credential writes
        under ADR-008 and this call can never actually reach a
        writable store there. There is no plaintext fallback:
        callers (the GUI's `_save_api_key`, the `save_settings`
        command handler) are expected to surface this as a failed
        save, not silently persist the key anywhere else.
        """
        key = api_key.strip()

        if key:
            self._secret_store.set_secret(_VT_API_KEY_SECRET_NAME, key)
        else:
            self._secret_store.delete_secret(_VT_API_KEY_SECRET_NAME)

    def has_api_key(self) -> bool:
        """
        Return whether a VirusTotal API key is currently configured,
        without reading its value.

        On a secret-store failure this returns `False` (a controlled,
        safe failure mode per the Part 2B brief S4) rather than
        raising -- this mirrors `_populate_api_key_from_store`'s
        behavior for `load()` and is meant for status-only callers.
        """
        try:
            return self._secret_store.has_secret(_VT_API_KEY_SECRET_NAME)
        except SecretStoreUnavailableError:
            logger.exception(
                "Secret store unavailable while checking whether a "
                "VirusTotal API key is configured; reporting not "
                "configured for this call."
            )
            return False

    def _populate_api_key_from_store(self, settings: ApplicationSettings) -> None:
        """
        Fill in `settings.virustotal_api_key` from the secret store,
        in place.

        `SecretNotFoundError` (no key ever configured) and
        `SecretStoreUnavailableError` (the store itself could not be
        reached) both resolve to "" here -- from a caller's
        perspective both mean "no usable key right now", and the
        existing `bool(settings.virustotal_api_key)` /
        `is_configured()` checks throughout the app already treat an
        empty string as "not configured". The two cases are still
        logged differently: not-found is expected and silent;
        unavailable is logged, since it indicates a real problem
        worth diagnosing.
        """
        try:
            settings.virustotal_api_key = self._secret_store.get_secret(
                _VT_API_KEY_SECRET_NAME
            )
        except SecretNotFoundError:
            settings.virustotal_api_key = ""
        except SecretStoreUnavailableError:
            logger.exception(
                "Secret store unavailable while loading the VirusTotal "
                "API key; treating it as not configured for this "
                "session rather than failing settings load entirely."
            )
            settings.virustotal_api_key = ""

    def _migrate_legacy_plaintext_key(self, legacy_plaintext_key: str) -> bool:
        """
        One-time migration path for a VT key found in plaintext in an
        old settings.json (pre-Part-2B).

        Returns True if the key was successfully moved into the
        secret store (the caller then rewrites settings.json to strip
        the plaintext copy immediately), False if the store could not
        be reached.

        On success the key now lives only in the secret store. On
        failure (secret store unavailable) the key is intentionally
        *not* carried forward anywhere: per the Part 2B brief S6, an
        exposed plaintext credential must never be automatically
        migrated into a place that could itself leak it (a log line,
        a re-written plaintext file, etc.), so the safe outcome here
        is that the user has to reconfigure the key -- not that the
        plaintext copy is preserved, duplicated, or silently dropped
        without record. Only the fact that migration failed is
        logged, never the key value. The plaintext copy is left
        exactly where it was in this failure case (nothing rewrites
        the file), so no data is lost even though it isn't yet secure
        -- migration is simply retried on the next load().
        """
        try:
            self._secret_store.set_secret(
                _VT_API_KEY_SECRET_NAME,
                legacy_plaintext_key.strip(),
            )
            logger.info(
                "Migrated a previously plaintext-stored VirusTotal API "
                "key into the secure secret store."
            )
            return True
        except SecretStoreUnavailableError:
            logger.exception(
                "Found a legacy plaintext VirusTotal API key in "
                "settings.json but the secret store is unavailable, "
                "so it could not be migrated yet. It has not been "
                "modified on disk and migration will be retried on "
                "the next load()."
            )
            return False
