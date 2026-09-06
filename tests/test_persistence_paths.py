"""
Regression tests for the R2-B persistent application-data path
architecture.

Covers the eight proof points required by
docs/audits/SOC-IQ-R2-A-PERSISTENCE-PATH-INVENTORY.md Part 15 item 5:

1. The persistent root resolves to the intended OS/per-user
   application-data location (via `platformdirs`).
2. The persistent root does not depend on the current working
   directory.
3. The persistent root does not resolve under a PyInstaller-style
   `sys._MEIPASS` temporary extraction directory, even when the
   process is simulated as frozen.
4. `initialize_application()` creates every required persistent
   directory.
5. The database's default path is the new persistent path.
6. The logger writes to the new persistent path once configured, and
   the production sidecar (`app.api.app`) actually wires that
   configuration into its startup, closing the R2-A gap where
   `configure_logger()`/`initialize_application()` were stranded in
   the retired PySide6 entrypoint.
7. Bundled, read-only Class 1 resources (migration SQL, the Jinja2
   report template) still resolve under `app/`'s own package
   location and were not redirected into the mutable data directory.
8. The explicit, caller-supplied `output_path` on export requests
   (Class 3, user-selected) remains untouched by any of the above --
   `app.application.dto` does not import anything from `app.config`.
"""

from __future__ import annotations

import logging
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ==========================================================
# 1 & 2 -- persistent root resolution / cwd independence
# ==========================================================


def test_app_data_root_matches_platformdirs():
    from platformdirs import user_data_dir

    from app.config import APP_AUTHOR, APP_DATA_ROOT, APP_NAME

    expected = Path(user_data_dir(APP_NAME, APP_AUTHOR, roaming=True))

    assert APP_DATA_ROOT == expected


def test_app_data_root_is_not_derived_from_base_dir():
    from app.config import APP_DATA_ROOT, BASE_DIR

    # The whole point of R2-B: Class 2 data no longer lives under the
    # __file__-relative source/bundle root.
    assert not str(APP_DATA_ROOT).startswith(str(BASE_DIR))


def test_app_data_root_independent_of_cwd(tmp_path):
    """
    Launch a subprocess from an unrelated cwd and confirm
    app.config.APP_DATA_ROOT resolves identically to running it from
    this process's own cwd -- mirroring the existing
    test_base_dir_resolution_is_stable_from_a_different_cwd pattern
    in tests/test_settings.py, extended to the new persistent root.
    """

    other_cwd = tmp_path / "somewhere-else"
    other_cwd.mkdir()

    script = textwrap.dedent(
        f"""
        import sys
        sys.path.insert(0, {str(PROJECT_ROOT)!r})
        from app.config import APP_DATA_ROOT
        print(APP_DATA_ROOT)
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

    from app.config import APP_DATA_ROOT

    assert result.stdout.strip() == str(APP_DATA_ROOT)


# ==========================================================
# 3 -- not PyInstaller extraction (_MEIPASS)
# ==========================================================


def test_app_data_root_not_under_simulated_meipass(tmp_path):
    """
    Simulate a frozen PyInstaller onefile process (sys.frozen=True,
    sys._MEIPASS pointing at a fresh temporary extraction directory)
    and confirm app.config.APP_DATA_ROOT does not resolve anywhere
    underneath it.

    Run in a subprocess (rather than monkeypatching sys.frozen/
    sys._MEIPASS in-process) so the simulated frozen state can never
    leak into any other test.
    """

    fake_meipass = tmp_path / "_MEI123456"
    fake_meipass.mkdir()

    script = textwrap.dedent(
        f"""
        import sys
        sys.path.insert(0, {str(PROJECT_ROOT)!r})
        sys.frozen = True
        sys._MEIPASS = {str(fake_meipass)!r}
        from app.config import APP_DATA_ROOT
        print(APP_DATA_ROOT)
        """
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr

    resolved_root = result.stdout.strip()

    assert not resolved_root.startswith(str(fake_meipass))
    assert "_MEI" not in resolved_root


# ==========================================================
# 4 -- directory creation
# ==========================================================


def test_initialize_application_creates_persistent_directories(
    tmp_path, monkeypatch
):
    import app.initializer as initializer_module

    database_dir = tmp_path / "database"
    logs_dir = tmp_path / "logs"
    config_dir = tmp_path / "config"
    exports_dir = tmp_path / "exports"
    samples_dir = tmp_path / "samples"

    monkeypatch.setattr(initializer_module, "DATABASE_DIR", database_dir)
    monkeypatch.setattr(initializer_module, "LOGS_DIR", logs_dir)
    monkeypatch.setattr(initializer_module, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(initializer_module, "EXPORTS_DIR", exports_dir)
    monkeypatch.setattr(initializer_module, "SAMPLES_DIR", samples_dir)

    for directory in (database_dir, logs_dir, config_dir, exports_dir, samples_dir):
        assert not directory.exists()

    initializer_module.initialize_application()

    for directory in (database_dir, logs_dir, config_dir, exports_dir, samples_dir):
        assert directory.is_dir()


# ==========================================================
# 5 -- database path
# ==========================================================


def test_database_connection_default_path_is_persistent():
    from app.config import APP_DATA_ROOT, DATABASE_PATH
    from app.database.connection import DatabaseConnection

    connection = DatabaseConnection()

    assert connection.database_path == DATABASE_PATH
    assert str(connection.database_path).startswith(str(APP_DATA_ROOT))


def test_database_connection_survives_reconstruction_against_persistent_path(
    tmp_path, monkeypatch
):
    """
    Restart-persistence proof: write through one DatabaseConnection,
    close it, construct a brand new DatabaseConnection against the
    same (persistent-style) default, and confirm the data is still
    there -- the exact guarantee that was broken when the default
    path lived inside PyInstaller's per-launch _MEIPASS directory.
    """

    import app.config as config_module
    from app.database.connection import DatabaseConnection

    persistent_db_path = tmp_path / "database" / "soc_iq.db"
    monkeypatch.setattr(config_module, "DATABASE_PATH", persistent_db_path)

    first = DatabaseConnection(database_path=config_module.DATABASE_PATH)
    conn = first.connect()
    conn.execute("CREATE TABLE restart_probe (value TEXT)")
    conn.execute("INSERT INTO restart_probe VALUES ('still-here')")
    conn.commit()
    first.close()

    second = DatabaseConnection(database_path=config_module.DATABASE_PATH)
    row = second.connect().execute(
        "SELECT value FROM restart_probe"
    ).fetchone()
    second.close()

    assert row["value"] == "still-here"


# ==========================================================
# 6 -- logging path + production wiring
# ==========================================================


def test_configure_logger_writes_to_persistent_log_file(tmp_path, monkeypatch):
    import app.config as config_module
    import app.logger as logger_module

    log_file = tmp_path / "logs" / "soc_iq.log"
    monkeypatch.setattr(config_module, "LOG_FILE", log_file)
    monkeypatch.setattr(logger_module, "LOG_FILE", log_file)

    logger_module.configure_logger(verbose=False)
    logger_module.logger.info("r2b-persistence-probe")

    for handler in logger_module.logger.handlers:
        handler.flush()

    assert log_file.exists()
    assert "r2b-persistence-probe" in log_file.read_text(encoding="utf-8")


def test_production_sidecar_wires_initialization_on_startup(tmp_path, monkeypatch):
    """
    Closes the R2-A gap (Part 5 / Part 15 item 2): the production
    sidecar entrypoint must actually call
    initialize_application()/configure_logger() on startup, not just
    have them exist unreachable in the retired GUI.

    Drives the app's real lifespan via TestClient's context-manager
    form (which runs FastAPI's lifespan startup/shutdown) rather than
    just inspecting handler wiring, so this proves the calls actually
    execute, not merely that something is registered.
    """

    from fastapi.testclient import TestClient

    import app.initializer as initializer_module
    import app.logger as logger_module
    from app.api.app import app as fastapi_app

    calls: list[str] = []
    monkeypatch.setattr(
        initializer_module,
        "initialize_application",
        lambda: calls.append("initialize_application"),
    )
    monkeypatch.setattr(
        logger_module,
        "configure_logger",
        lambda verbose=False: calls.append("configure_logger"),
    )
    # app.api.app imported both names directly, so they must be
    # patched at that import site too.
    import app.api.app as api_app_module

    monkeypatch.setattr(
        api_app_module,
        "initialize_application",
        lambda: calls.append("initialize_application"),
    )
    monkeypatch.setattr(
        api_app_module,
        "configure_logger",
        lambda verbose=False: calls.append("configure_logger"),
    )

    with TestClient(fastapi_app):
        pass

    assert calls == ["initialize_application", "configure_logger"]


# ==========================================================
# 7 -- resource separation
# ==========================================================


def test_bundled_resources_remain_file_relative_not_persistent():
    from app.config import APP_DATA_ROOT, BASE_DIR
    from app.database.migration_runner import MIGRATIONS_DIR
    from app.reporting.html_exporter import _TEMPLATE_DIR

    assert str(MIGRATIONS_DIR).startswith(str(BASE_DIR))
    assert str(_TEMPLATE_DIR).startswith(str(BASE_DIR))

    assert not str(MIGRATIONS_DIR).startswith(str(APP_DATA_ROOT))
    assert not str(_TEMPLATE_DIR).startswith(str(APP_DATA_ROOT))

    assert MIGRATIONS_DIR.is_dir()
    assert _TEMPLATE_DIR.is_dir()


# ==========================================================
# 8 -- user-selected export destinations untouched
# ==========================================================


def test_export_dto_does_not_depend_on_app_config():
    """
    app.application.dto (ExportReportRequest / ExportHistoryCsvRequest)
    must keep requiring and using exactly the caller-supplied absolute
    output_path -- Class 3 data is out of scope for R2-B and this
    proves nothing in this part accidentally routed it through
    app.config.
    """

    import app.application.dto as dto_module

    source = Path(dto_module.__file__).read_text(encoding="utf-8")
    assert "app.config" not in source
    assert "app_data_root" not in source.lower()


# ==========================================================
# R2-D 1 -- log restart persistence across a real process
# boundary (subprocess), verifying content, not just existence
# ==========================================================


def test_log_persists_across_subprocess_boundary(tmp_path):
    """
    Run #1 (subprocess A) configures logging against an isolated,
    on-disk persistent-style log file, writes an identifiable entry,
    and exits (closing all handlers via configure_logger's own
    close-before-reconfigure path / process teardown). Run #2
    (subprocess B) starts fresh, points at the SAME log file, and
    confirms the Run #1 entry is still present before writing its own
    -- proving persistence across an actual process boundary, not
    merely an in-process close/reopen.
    """

    log_file = tmp_path / "logs" / "soc_iq.log"

    run_script = textwrap.dedent(
        f"""
        import sys
        sys.path.insert(0, {str(PROJECT_ROOT)!r})
        from pathlib import Path
        import app.config as config_module
        import app.logger as logger_module
        config_module.LOG_FILE = Path({str(log_file)!r})
        logger_module.LOG_FILE = Path({str(log_file)!r})
        logger_module.configure_logger(verbose=False)
        logger_module.logger.info(sys.argv[1])
        for h in logger_module.logger.handlers:
            h.flush()
            h.close()
        """
    )

    for marker in ("r2d-run-1-marker", "r2d-run-2-marker"):
        result = subprocess.run(
            [sys.executable, "-c", run_script, marker],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stderr

    content = log_file.read_text(encoding="utf-8")
    assert "r2d-run-1-marker" in content
    assert "r2d-run-2-marker" in content


# ==========================================================
# R2-D 2 -- application-owned default export destination is
# persistent, and a real generated export survives process exit
# ==========================================================


def test_default_export_directory_is_under_app_data_root():
    from app.config import APP_DATA_ROOT, EXPORTS_DIR

    assert str(EXPORTS_DIR).startswith(str(APP_DATA_ROOT))


def test_settings_export_directory_defaults_to_persistent_exports_dir():
    from app.config import EXPORTS_DIR
    from app.settings.models import ApplicationSettings

    assert ApplicationSettings().export_directory == str(EXPORTS_DIR.resolve())


def test_real_export_write_persists_at_destination(tmp_path):
    """
    Writes a real JSON export (the actual production exporter, no
    filesystem mocking) to an application-owned default-style
    destination under an isolated exports root, then confirms a
    brand-new process can observe the file with correct content --
    i.e. it remains available after the producing process exits.
    """

    from app.reporting.json_exporter import JSONReportExporter
    from app.reporting.models import InvestigationReport

    exports_dir = tmp_path / "exports"
    output_path = exports_dir / "r2d-probe-report.json"

    report = InvestigationReport(
        report_name="R2-D Export Persistence Probe",
        analyzed_at="2026-01-01T00:00:00Z",
        status="completed",
        severity="low",
        risk_score=0,
        confidence=0.0,
        ioc_score=0,
        threat_intel_score=0,
        cve_score=0,
        iocs={},
        threat_intelligence={},
        investigation_id=None,
    )

    JSONReportExporter.export(report, output_path)

    assert output_path.exists()

    check_script = textwrap.dedent(
        f"""
        import json
        with open({str(output_path)!r}, encoding="utf-8") as f:
            data = json.load(f)
        assert data["report_name"] == "R2-D Export Persistence Probe"
        print("ok")
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", check_script],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"


# ==========================================================
# R2-D 3 -- explicit user-selected destination is honored exactly,
# end to end, and is never redirected under EXPORTS_DIR/APP_DATA_ROOT
# ==========================================================


def test_explicit_user_selected_destination_honored_exactly(tmp_path):
    from app.reporting.json_exporter import JSONReportExporter
    from app.reporting.models import InvestigationReport

    # A destination that is deliberately NOT under APP_DATA_ROOT or
    # EXPORTS_DIR, mirroring a user picking an arbitrary folder (e.g.
    # D:\\Reports\\...) in a save dialog.
    user_chosen_dir = tmp_path / "wherever-the-user-picked"
    output_path = user_chosen_dir / "Investigation.json"

    report = InvestigationReport(
        report_name="R2-D User-Selected Destination Probe",
        analyzed_at="2026-01-01T00:00:00Z",
        status="completed",
        severity="low",
        risk_score=0,
        confidence=0.0,
        ioc_score=0,
        threat_intel_score=0,
        cve_score=0,
        iocs={},
        threat_intelligence={},
        investigation_id=None,
    )

    returned_path = JSONReportExporter.export(report, output_path)

    assert returned_path == output_path
    assert output_path.exists()

    from app.config import APP_DATA_ROOT, EXPORTS_DIR

    assert not str(output_path).startswith(str(APP_DATA_ROOT))
    assert not str(output_path).startswith(str(EXPORTS_DIR))


# ==========================================================
# R2-D 4 -- no duplicate/leaked logging handlers across repeated
# (re)configuration, and only one persistent destination is active
# ==========================================================


def test_configure_logger_does_not_duplicate_handlers(tmp_path, monkeypatch):
    import app.config as config_module
    import app.logger as logger_module

    log_file = tmp_path / "logs" / "soc_iq.log"
    monkeypatch.setattr(config_module, "LOG_FILE", log_file)
    monkeypatch.setattr(logger_module, "LOG_FILE", log_file)

    logger_module.configure_logger(verbose=False)
    logger_module.configure_logger(verbose=False)
    logger_module.configure_logger(verbose=True)

    file_handlers = [
        h
        for h in logger_module.logger.handlers
        if isinstance(h, logging.FileHandler)
    ]

    assert len(file_handlers) == 1
    assert Path(file_handlers[0].baseFilename) == log_file

    logger_module.logger.info("r2d-no-duplicate-probe")
    for h in logger_module.logger.handlers:
        h.flush()

    entries = log_file.read_text(encoding="utf-8").count(
        "r2d-no-duplicate-probe"
    )
    assert entries == 1
