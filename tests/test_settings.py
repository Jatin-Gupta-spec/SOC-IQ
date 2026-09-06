"""
Regression tests for the SOC-IQ settings subsystem
(app.settings.models / app.settings.repository /
app.settings.service).

Covers defaults, save/load round-tripping, corrupted and
missing settings files, export directory persistence, API
key persistence, and the BASE_DIR path fix (settings must
resolve relative to the project location, never the current
working directory).

Phase 4M Part 2B: the VirusTotal API key is no longer persisted in
settings.json at all -- it lives exclusively in a `SecretStore`
(see app/secrets/store.py). Tests below that exercise API-key
persistence inject `FakeSecretStore` (tests/fixtures/fake_secret_store.py)
rather than relying on a real OS credential store, which is
unavailable in this sandbox/CI environment. Tests that only exercise
`export_directory`/`theme` do not need a secret store at all, since
`SettingsRepository.save()`/`load()` never touch it for those fields.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from app.secrets.exceptions import SecretStoreUnavailableError
from app.settings.models import ApplicationSettings
from app.settings.repository import SettingsRepository
from app.settings.service import SettingsService
from tests.fixtures.fake_secret_store import FakeSecretStore


PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ==========================================================
# ApplicationSettings defaults
# ==========================================================


def test_default_settings_have_empty_api_key():
    settings = ApplicationSettings()

    assert settings.virustotal_api_key == ""


def test_default_settings_export_directory_is_under_app_data_root():
    from app.config import APP_DATA_ROOT

    settings = ApplicationSettings()

    assert settings.export_directory.endswith("exports")
    assert settings.export_directory.startswith(str(APP_DATA_ROOT))


def test_default_settings_theme():
    settings = ApplicationSettings()

    assert settings.theme == "Dark Mode (SOC-IQ Standard)"


def test_settings_repr_redacts_api_key():
    settings = ApplicationSettings(
        virustotal_api_key="super-secret-key",
    )

    rendered = repr(settings)

    assert "super-secret-key" not in rendered
    assert "<redacted>" in rendered


def test_settings_repr_shows_no_key_when_empty():
    settings = ApplicationSettings()

    rendered = repr(settings)

    assert "virustotal_api_key=''" in rendered


# ==========================================================
# SettingsRepository: save / load round trip
# ==========================================================


def test_repository_creates_defaults_when_file_missing(tmp_path):
    settings_path = tmp_path / "config" / "settings.json"
    repository = SettingsRepository(
        settings_path=settings_path,
        secret_store=FakeSecretStore(),
    )

    assert not settings_path.exists()

    loaded = repository.load()

    assert loaded == ApplicationSettings()
    # Loading with no file present should create one.
    assert settings_path.exists()


def test_repository_save_then_load_round_trip(tmp_path):
    settings_path = tmp_path / "settings.json"
    secret_store = FakeSecretStore()
    repository = SettingsRepository(
        settings_path=settings_path,
        secret_store=secret_store,
    )

    original = ApplicationSettings(
        virustotal_api_key="abc123",
        export_directory=str(tmp_path / "exports"),
        theme="Light Mode",
    )

    # export_directory/theme go through save(); the API key goes
    # through save_api_key() (the secret-store path) -- see the
    # module docstring on why these are no longer one call.
    repository.save(original)
    repository.save_api_key(original.virustotal_api_key)
    loaded = repository.load()

    assert loaded == original


def test_repository_save_never_writes_api_key_to_disk(tmp_path):
    settings_path = tmp_path / "settings.json"
    repository = SettingsRepository(
        settings_path=settings_path,
        secret_store=FakeSecretStore(),
    )

    repository.save(
        ApplicationSettings(virustotal_api_key="super-secret-key")
    )

    on_disk = settings_path.read_text(encoding="utf-8")
    assert "super-secret-key" not in on_disk
    assert "virustotal_api_key" not in json.loads(on_disk)


def test_repository_save_api_key_round_trips_via_secret_store(tmp_path):
    settings_path = tmp_path / "settings.json"
    secret_store = FakeSecretStore()
    repository = SettingsRepository(
        settings_path=settings_path,
        secret_store=secret_store,
    )

    repository.save_api_key("abc123")

    assert secret_store.get_secret("virustotal_api_key") == "abc123"
    assert repository.has_api_key() is True
    assert repository.load().virustotal_api_key == "abc123"


def test_repository_save_api_key_blank_deletes_existing_key(tmp_path):
    settings_path = tmp_path / "settings.json"
    secret_store = FakeSecretStore()
    repository = SettingsRepository(
        settings_path=settings_path,
        secret_store=secret_store,
    )

    repository.save_api_key("abc123")
    repository.save_api_key("   ")

    assert repository.has_api_key() is False
    assert repository.load().virustotal_api_key == ""


def test_repository_save_api_key_propagates_store_unavailable(tmp_path):
    settings_path = tmp_path / "settings.json"
    secret_store = FakeSecretStore()
    secret_store.fail_next = True
    repository = SettingsRepository(
        settings_path=settings_path,
        secret_store=secret_store,
    )

    with pytest.raises(SecretStoreUnavailableError):
        repository.save_api_key("abc123")


def test_repository_load_treats_store_unavailable_as_no_key(tmp_path):
    """
    A secret-store failure while *loading* must be a safe, controlled
    fallback (empty key / "not configured"), never a crash and never
    a plaintext fallback -- per the Part 2B brief S4.
    """
    settings_path = tmp_path / "settings.json"
    secret_store = FakeSecretStore()
    repository = SettingsRepository(
        settings_path=settings_path,
        secret_store=secret_store,
    )
    repository.save_api_key("abc123")
    secret_store.fail_next = True

    loaded = repository.load()

    assert loaded.virustotal_api_key == ""


def test_repository_has_api_key_false_when_store_unavailable(tmp_path):
    settings_path = tmp_path / "settings.json"
    secret_store = FakeSecretStore()
    secret_store.fail_next = True
    repository = SettingsRepository(
        settings_path=settings_path,
        secret_store=secret_store,
    )

    assert repository.has_api_key() is False


def test_repository_migrates_legacy_plaintext_key_into_secret_store(tmp_path):
    """
    An old settings.json written before Part 2B may still have a
    plaintext `virustotal_api_key`. The first load() after upgrading
    must move it into the secret store and never write it back to
    disk again.
    """
    settings_path = tmp_path / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps(
            {
                "virustotal_api_key": "legacy-plaintext-key",
                "export_directory": str(tmp_path / "exports"),
                "theme": "Light Mode",
            }
        ),
        encoding="utf-8",
    )

    secret_store = FakeSecretStore()
    repository = SettingsRepository(
        settings_path=settings_path,
        secret_store=secret_store,
    )

    loaded = repository.load()

    assert loaded.virustotal_api_key == "legacy-plaintext-key"
    assert secret_store.get_secret("virustotal_api_key") == "legacy-plaintext-key"
    # The migrated key must not still be sitting in the file.
    on_disk = settings_path.read_text(encoding="utf-8")
    assert "legacy-plaintext-key" not in on_disk


def test_repository_legacy_key_migration_failure_does_not_crash_load(tmp_path):
    """
    If the secret store can't be reached at migration time, load()
    must still succeed (falling back to "no key configured") rather
    than raising -- and must not silently keep the plaintext copy
    around as a fallback.
    """
    settings_path = tmp_path / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps({"virustotal_api_key": "legacy-plaintext-key"}),
        encoding="utf-8",
    )

    secret_store = FakeSecretStore()
    secret_store.fail_next = True
    repository = SettingsRepository(
        settings_path=settings_path,
        secret_store=secret_store,
    )

    loaded = repository.load()

    assert loaded.virustotal_api_key == ""


def test_repository_save_is_atomic_no_leftover_tmp_files(tmp_path):
    settings_path = tmp_path / "settings.json"
    repository = SettingsRepository(
        settings_path=settings_path,
        secret_store=FakeSecretStore(),
    )

    repository.save(ApplicationSettings(virustotal_api_key="key-1"))
    repository.save(ApplicationSettings(virustotal_api_key="key-2"))

    leftover_tmp_files = list(tmp_path.glob(".*.tmp"))

    assert leftover_tmp_files == []
    assert settings_path.exists()


def test_repository_save_creates_parent_directories(tmp_path):
    settings_path = tmp_path / "nested" / "dir" / "settings.json"
    repository = SettingsRepository(
        settings_path=settings_path,
        secret_store=FakeSecretStore(),
    )

    repository.save(ApplicationSettings(virustotal_api_key="key"))

    assert settings_path.exists()


# ==========================================================
# Corrupted / missing settings
# ==========================================================


def test_repository_load_resets_corrupted_json(tmp_path):
    settings_path = tmp_path / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text("{not valid json", encoding="utf-8")

    repository = SettingsRepository(
        settings_path=settings_path,
        secret_store=FakeSecretStore(),
    )
    loaded = repository.load()

    assert loaded == ApplicationSettings()
    # The corrupted file should have been overwritten with valid
    # JSON representing the defaults.
    on_disk = json.loads(settings_path.read_text(encoding="utf-8"))
    assert on_disk["theme"] == ApplicationSettings().theme


def test_repository_load_resets_settings_with_unknown_fields(tmp_path):
    settings_path = tmp_path / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps({"totally_unexpected_field": 123}),
        encoding="utf-8",
    )

    repository = SettingsRepository(
        settings_path=settings_path,
        secret_store=FakeSecretStore(),
    )
    loaded = repository.load()

    assert loaded == ApplicationSettings()


def test_repository_load_ignores_wrong_typed_legacy_api_key(tmp_path):
    settings_path = tmp_path / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    # A wrong-typed legacy virustotal_api_key (should be a string) is
    # popped out before ApplicationSettings is even constructed (see
    # SettingsRepository.load()), so it can no longer reach the
    # dataclass at all -- unlike pre-Part-2B, this field is not
    # sourced from disk anymore, so there is nothing to "accept
    # as-is". It is simply not a valid legacy key to migrate, and the
    # resulting settings' virustotal_api_key comes from the (empty)
    # secret store instead.
    settings_path.write_text(
        json.dumps({"virustotal_api_key": ["not", "a", "string"]}),
        encoding="utf-8",
    )

    repository = SettingsRepository(
        settings_path=settings_path,
        secret_store=FakeSecretStore(),
    )
    loaded = repository.load()

    assert loaded.virustotal_api_key == ""


def test_repository_load_missing_directory(tmp_path):
    settings_path = tmp_path / "does" / "not" / "exist" / "settings.json"
    repository = SettingsRepository(
        settings_path=settings_path,
        secret_store=FakeSecretStore(),
    )

    loaded = repository.load()

    assert loaded == ApplicationSettings()
    assert settings_path.exists()


def test_service_load_settings_falls_back_on_repository_exception(
    monkeypatch,
):
    """
    SettingsService.load_settings() must never propagate -- it is
    called unguarded during MainWindow construction, before the Qt
    event loop starts.
    """

    class ExplodingRepository:
        def load(self):
            raise OSError("disk on fire")

    service = SettingsService(repository=ExplodingRepository())

    result = service.load_settings()

    assert result == ApplicationSettings()


# ==========================================================
# Export directory / API key persistence via the service layer
# ==========================================================


def test_service_update_export_directory_persists(tmp_path):
    settings_path = tmp_path / "settings.json"
    repository = SettingsRepository(
        settings_path=settings_path,
        secret_store=FakeSecretStore(),
    )
    service = SettingsService(repository=repository)

    service.update_export_directory(str(tmp_path / "my-exports"))

    reloaded = service.load_settings()
    assert reloaded.export_directory == str(tmp_path / "my-exports")


def test_service_update_export_directory_strips_whitespace(tmp_path):
    settings_path = tmp_path / "settings.json"
    repository = SettingsRepository(
        settings_path=settings_path,
        secret_store=FakeSecretStore(),
    )
    service = SettingsService(repository=repository)

    service.update_export_directory("  /tmp/padded  ")

    reloaded = service.load_settings()
    assert reloaded.export_directory == "/tmp/padded"


def test_service_update_api_key_persists(tmp_path):
    settings_path = tmp_path / "settings.json"
    repository = SettingsRepository(
        settings_path=settings_path,
        secret_store=FakeSecretStore(),
    )
    service = SettingsService(repository=repository)

    service.update_api_key("my-vt-key")

    reloaded = service.load_settings()
    assert reloaded.virustotal_api_key == "my-vt-key"


def test_service_update_api_key_strips_whitespace(tmp_path):
    settings_path = tmp_path / "settings.json"
    repository = SettingsRepository(
        settings_path=settings_path,
        secret_store=FakeSecretStore(),
    )
    service = SettingsService(repository=repository)

    service.update_api_key("  padded-key  \n")

    reloaded = service.load_settings()
    assert reloaded.virustotal_api_key == "padded-key"


def test_service_update_api_key_propagates_store_unavailable(tmp_path):
    settings_path = tmp_path / "settings.json"
    secret_store = FakeSecretStore()
    secret_store.fail_next = True
    repository = SettingsRepository(
        settings_path=settings_path,
        secret_store=secret_store,
    )
    service = SettingsService(repository=repository)

    with pytest.raises(SecretStoreUnavailableError):
        service.update_api_key("my-vt-key")


def test_service_update_theme_persists(tmp_path):
    settings_path = tmp_path / "settings.json"
    repository = SettingsRepository(
        settings_path=settings_path,
        secret_store=FakeSecretStore(),
    )
    service = SettingsService(repository=repository)

    service.update_theme("Light Mode")

    reloaded = service.load_settings()
    assert reloaded.theme == "Light Mode"


def test_updating_one_field_does_not_clobber_others(tmp_path):
    settings_path = tmp_path / "settings.json"
    repository = SettingsRepository(
        settings_path=settings_path,
        secret_store=FakeSecretStore(),
    )
    service = SettingsService(repository=repository)

    service.update_api_key("first-key")
    service.update_theme("Light Mode")
    service.update_export_directory(str(tmp_path / "exports"))

    reloaded = service.load_settings()

    assert reloaded.virustotal_api_key == "first-key"
    assert reloaded.theme == "Light Mode"
    assert reloaded.export_directory == str(tmp_path / "exports")


def test_default_settings_service_uses_real_repository():
    """
    SettingsService() with no repository argument should build its
    own SettingsRepository (i.e. real dependency, not None).
    """

    service = SettingsService()

    assert isinstance(service._repository, SettingsRepository)


# ==========================================================
# BASE_DIR path fix: settings must resolve based on the
# project's own location, never the interpreter's current
# working directory.
# ==========================================================


def test_base_dir_is_derived_from_module_file_not_cwd():
    from app.config import BASE_DIR

    assert BASE_DIR == PROJECT_ROOT


@pytest.mark.real_settings_base_dir
def test_default_settings_path_is_under_app_data_root():
    from app.config import APP_DATA_ROOT, SETTINGS_FILE

    repository = SettingsRepository()

    assert repository._settings_path == SETTINGS_FILE
    assert repository._settings_path == APP_DATA_ROOT / "config" / "settings.json"


def test_base_dir_resolution_is_stable_from_a_different_cwd(tmp_path):
    """
    Launch a subprocess with its working directory set somewhere
    completely unrelated to the project, and confirm that
    app.config.BASE_DIR (and therefore the settings path) still
    resolves to the real project root rather than the launch
    directory.
    """

    other_cwd = tmp_path / "somewhere-else"
    other_cwd.mkdir()

    script = textwrap.dedent(
        f"""
        import sys
        sys.path.insert(0, {str(PROJECT_ROOT)!r})
        from app.config import BASE_DIR
        print(BASE_DIR)
        """
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=other_cwd,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(PROJECT_ROOT)


def test_settings_round_trip_survives_launch_from_different_cwd(tmp_path):
    """
    End-to-end variant of the BASE_DIR check: actually save and
    load settings from a subprocess launched with an unrelated cwd,
    confirming the settings.json file lands under the real project
    config/ directory rather than next to the launch cwd.
    """

    other_cwd = tmp_path / "launch-dir"
    other_cwd.mkdir()

    isolated_settings_path = tmp_path / "isolated_settings.json"

    script = textwrap.dedent(
        f"""
        import sys
        sys.path.insert(0, {str(PROJECT_ROOT)!r})
        from pathlib import Path
        from app.settings.repository import SettingsRepository
        from app.settings.models import ApplicationSettings

        repo = SettingsRepository(
            settings_path=Path({str(isolated_settings_path)!r})
        )
        # export_directory (not virustotal_api_key) is what's round
        # -tripped here: this test is about BASE_DIR/cwd-independent
        # path resolution, which is a settings.json-only concern as
        # of Phase 4M Part 2B -- the API key now lives in the OS
        # secret store instead, which this sandboxed subprocess has
        # no real backend for.
        repo.save(ApplicationSettings(export_directory="from-subprocess"))
        reloaded = repo.load()
        assert reloaded.export_directory == "from-subprocess"
        print("OK")
        """
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=other_cwd,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK"
    assert isolated_settings_path.exists()
    # Nothing should have been written into the unrelated launch dir.
    assert list(other_cwd.iterdir()) == []
