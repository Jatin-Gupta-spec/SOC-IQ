"""
Root-level pytest configuration for SOC-IQ.

D2 (Part 3A-2C/2D; path source updated for R2-B): test-suite
reproducibility
-----------------------------------------------
`SettingsRepository.__init__` falls back to a real, persistent
default (`app.config.SETTINGS_FILE`, under the OS-conventional
per-user application-data directory resolved by `platformdirs` --
see `app.config.APP_DATA_ROOT`) whenever a caller does not supply
its own `settings_path` -- this is intentional production behavior
(first-run settings generation must be portable and independent of
both CWD and any PyInstaller extraction directory; see
`test_default_settings_path_is_under_app_data_root` and
`test_base_dir_resolution_is_stable_from_a_different_cwd` in
`tests/test_settings.py`). Prior to R2-B this default was
`BASE_DIR / "config" / "settings.json"`; R2-B moved Class 2
(mutable, application-owned) data off of the `__file__`-relative
`BASE_DIR` and onto the persistent `APP_DATA_ROOT` -- see
docs/audits/SOC-IQ-R2-A-PERSISTENCE-PATH-INVENTORY.md.

The root cause of D2 is that several production call sites construct
their collaborators with this default deliberately (e.g.
`SettingsService()` inside `app/services/system_health_service.py`,
`app/application/handlers.py`, and -- verified as the actual trigger
during the full-suite run -- the unconditional
`SettingsService().load_settings()` in
`VirusTotalClient.__init__`, which every test that builds a
`VirusTotalClient` with a real or fake `api_key` still runs through).
None of those call sites are wrong in production. But when a test
exercises them without injecting a fake/temp repository, that real
default resolves inside *this* checkout, and `SettingsRepository.load()`'s
existing "missing file -> create portable defaults -> save()" path
(also correct, and also required in production) writes a live
`config/settings.json` into the tracked project tree.

Fix: isolate the *default* at its one source -- the module-level
`SETTINGS_FILE` name that `app.settings.repository` falls back to --
for the duration of every test, redirecting it to a path under that
test's own `tmp_path`. This is a pure test-isolation change:

* No production code is modified.
* Any test that already passes its own `settings_path` (the large
  majority of `tests/test_settings.py`, `tests/test_application_layer.py`,
  etc.) is completely unaffected -- they never consult this default.
* The default-path *mechanism* itself keeps working exactly as in
  production: a missing settings file at the (now temporary) default
  location still regenerates through the same
  `SettingsRepository.load()` logic, with the same portable defaults.
  See the manual, out-of-suite verification performed for Part 3A-2D
  (a real, unpatched `SettingsRepository()` constructed against a
  throwaway copy of the project) for confirmation that production
  first-run behavior is unchanged by this fixture.
* The one test that intentionally asserts the *real* production
  default (`test_default_settings_path_is_under_app_data_root`) opts
  out via the `real_settings_base_dir` marker registered in
  `pytest.ini`, so it keeps exercising the genuine, unpatched
  `SETTINGS_FILE`.
"""

from __future__ import annotations

import pytest

import app.settings.repository as settings_repository_module


@pytest.fixture(autouse=True)
def _isolate_default_settings_path(request, tmp_path, monkeypatch):
    """
    Redirect the default SettingsRepository/SettingsService config
    location to a per-test temporary directory, so a full test-suite
    run can never regenerate a real `settings.json` under the actual
    OS per-user application-data directory.

    Scope: function -- a fresh `tmp_path` (and therefore a fresh
    isolated "config/settings.json") per test, with deterministic
    cleanup handled by pytest's own `tmp_path` and `monkeypatch`
    fixtures (both revert/clean up automatically at the end of every
    test, no manual teardown needed here).
    """

    if "real_settings_base_dir" in request.keywords:
        # This test intentionally exercises the real, unpatched
        # production default -- see
        # test_default_settings_path_is_under_app_data_root.
        yield
        return

    monkeypatch.setattr(
        settings_repository_module,
        "SETTINGS_FILE",
        tmp_path / "config" / "settings.json",
    )

    yield
