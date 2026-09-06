# SOC-IQ — R2-A: Persistent Runtime Data Path Inventory (Forensic Audit)

**Status:** Discovery / audit only. No persistence architecture changes are
made in this document or this checkpoint. All findings below are traced to
actual source, not inferred from naming conventions.

---

## 1. Checkpoint Identity

| Field | Value |
| --- | --- |
| Input archive | `SOC-IQ-PD08-R1-CLOSURE-FULL.zip` |
| Input SHA-256 | `f77e1b55eec31b1b197a94f55c50576419d91b048ac5b6978b1b95c63e650fd9` |
| ZIP integrity | `unzip -t` — no errors detected |
| ZIP entry count | 767 (directories + files) |
| Actual file count (non-directory entries extracted) | 681 |
| Extracted root | `SOC-IQ-PD08-FINAL-CLOSURE-FULL/` |
| Git metadata | None present in the archive (no `.git/`) — commit identity cannot be established from this checkpoint |

## 2. Environment

| Field | Value |
| --- | --- |
| OS (audit host) | Linux (container) |
| Python | 3.12.3 |
| Node | not invoked for this audit (no frontend paths were in scope beyond the one Rust/Tauri file referenced in Part E) |
| Key backend deps present in `requirements.txt` | `fastapi`, `uvicorn`, `python-dotenv`, `jinja2`, PDF generation lib, `pyinstaller` (build tooling) |
| `platformdirs` / `appdirs` | **Not present** in `requirements.txt` or anywhere in source |

## 3. Audit Scope

Inspected: `app/**`, `packaging/**`, `src-tauri/src/sidecar.rs`, `database/`,
`tests/**`, `docs/**` (persistence/packaging-relevant documents), and the
project's dependency manifests. Searched for every term listed in the R2-A
brief's required forensic search list. No source or configuration files were
modified. `database/soc_iq.db` (the shipped file) was not opened for content
review, only located and classified.

---

## 4. Database Path Analysis

```
app/config.py
   BASE_DIR = Path(__file__).resolve().parent.parent
   DATABASE_DIR = BASE_DIR / "database"
   DATABASE_PATH = DATABASE_DIR / "soc_iq.db"
        ↓
app/database/connection.py
   DatabaseConnection.__init__(database_path: Path = DATABASE_PATH)
   .connect() → self._database_path.parent.mkdir(parents=True, exist_ok=True)
              → sqlite3.connect(self._database_path)
```

- **Development mode:** `BASE_DIR` resolves to the real project root
  (confirmed by `tests/test_settings.py::test_base_dir_is_derived_from_module_file_not_cwd`
  and `::test_base_dir_resolution_is_stable_from_a_different_cwd`, which
  launches a subprocess from an unrelated `cwd` and asserts `BASE_DIR` is
  unaffected). The database is written to `<project root>/database/soc_iq.db`.
- **Packaged mode:** `app/config.py` is bundled into the PyInstaller onefile
  executable (`packaging/pyinstaller/socq_backend.spec`). At runtime, a
  frozen module's `__file__` resolves to a path inside PyInstaller's onefile
  extraction directory (the `_MEIPASS`-style temp directory), not next to the
  `.exe`. `BASE_DIR` therefore resolves to that temp directory in packaged
  mode, and `DATABASE_PATH` follows it: `<_MEIPASS temp dir>/database/soc_iq.db`.
- **Restart behavior:** The spec sets `runtime_tmpdir=None` (onefile
  default), meaning PyInstaller allocates a **fresh temporary extraction
  directory on every process launch** and removes it on clean exit. A
  restarted packaged app would resolve `BASE_DIR` to a *different* temp
  directory than the previous run, so the previous run's database would not
  be found — SOC-IQ would appear to reset to an empty database on every
  restart in packaged use.
- **Risk:** Confirmed — the database path resolves inside the PyInstaller
  temporary extraction directory in packaged mode. This is not a hypothetical
  based on config naming; it follows directly from `Path(__file__)` semantics
  under a frozen onefile build plus the absence of any `sys.frozen` /
  `sys._MEIPASS` branch anywhere in `app/config.py` (confirmed by search —
  zero occurrences of `_MEIPASS` or `frozen` in `app/`).

## 5. Logging Path Analysis

```
app/config.py:  LOGS_DIR = BASE_DIR / "logs"; LOG_FILE = LOGS_DIR / "soc_iq.log"
app/logger.py:  logger = logging.getLogger("SOC-IQ")   # created at import time, no handler
                configure_logger(verbose=False):
                    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
                    attaches FileHandler(LOG_FILE) [+ StreamHandler if verbose]
```

- `LOG_FILE` inherits the same `BASE_DIR` defect as the database in packaged
  mode (Part 4).
- **More significant finding:** `configure_logger()` is only ever called
  from `app/main.py` (the legacy PySide6 desktop entrypoint). `app/main.py`
  is explicitly excluded from the PyInstaller build (the `.spec` file's own
  header comment states PySide6/`app/gui/**` is deliberately not bundled,
  "not imported by anything on the `app.api.entrypoint` import path").
  `app/api/app.py` and `app/api/entrypoint.py` — the actual production
  sidecar the packaged `.exe` runs — never call `configure_logger()` or
  `initialize_application()`.
- **Consequence:** in the packaged/production sidecar, the `"SOC-IQ"` logger
  has no attached handler at all. The numerous `logger.info(...)` /
  `logger.exception(...)` calls throughout `app/database/connection.py`,
  `app/database/migration_runner.py`, etc. execute but write to nothing —
  no log file is created, and Python's logging module silently drops the
  records (no handler → falls through to `logging.lastResort`, typically a
  stderr warning-level-only handler, so INFO-level operational logs are lost
  entirely). This is independent of the `_MEIPASS` path question: even if
  `LOG_FILE` resolved somewhere persistent, no handler is ever attached to
  write it.

## 6. Export Path Analysis

| Mechanism | Path source | Classification |
| --- | --- | --- |
| `export_report` command (`app/application/handlers.py`, backed by `app/reporting/export_manager.py` → per-format exporters) | `ExportReportRequest.output_path: str` — validated in `app/application/dto.py` to be a **non-empty, absolute path**, supplied by the caller (frontend) | **USER SELECTED** |
| Bulk investigation-history CSV export (`app/services/investigation_csv_export.py`, `ExportHistoryCsvRequest`) | Same pattern — `output_path` validated as absolute, caller-supplied | **USER SELECTED** |
| `app.config.OUTPUT_DIR`, `JSON_EXPORT_FILE`, `CSV_EXPORT_FILE` | `BASE_DIR / "output" / ...` | **APPLICATION DEFAULT — but dead.** Confirmed by search: these three constants have **no callers anywhere** in `app/` or `tests/` outside their own definition in `app/config.py`. They are not referenced by the reporting service, the export manager, the command handlers, or any test. |
| `ApplicationSettings.export_directory` default (`app/settings/models.py`) | `str((BASE_DIR / "output").resolve())` | **APPLICATION DEFAULT (advisory).** Persisted/editable via `config/settings.json` (see Part 7). Used to pre-fill the Settings UI and (per `app/gui/pages/settings_page.py` wiring) presumably to seed a save-dialog default location. It is a *suggested* directory, not an enforced write location — `dto.py` still requires an absolute path per export call. |
| Legacy GUI `QFileDialog` usage (`app/gui/pages/*.py`, various widgets) | OS native save dialog | **USER SELECTED** — but this GUI is retired (PD-06) and excluded from the packaged build; not part of the shipped product's export path today. |

Net finding: today's *actual, shipped* export mechanism never writes to an
application-default location — every real export path requires the caller
to supply an absolute destination. The only place an application default is
still live is `ApplicationSettings.export_directory`, whose **default
value** inherits the same packaged-mode `BASE_DIR` problem described in
Part 4 if a first-run packaged user is ever shown it as a pre-filled folder
suggestion.

## 7. Configuration / Runtime-State Analysis

| Data | Writer | Path Logic | Mutable? | Persistent? | Packaged Risk |
| --- | --- | --- | --- | --- | --- |
| SQLite DB (`soc_iq.db`) | `app/database/connection.py` | `BASE_DIR/database/soc_iq.db` | Yes | Dev: yes. Packaged: **no** (temp extraction dir, see Part 4) | 🔴 |
| Log file (`soc_iq.log`) | `app/logger.py::configure_logger` | `BASE_DIR/logs/soc_iq.log` | Yes | Dev: yes, *if* `configure_logger()` is called (only in retired GUI). Packaged: **never created** (handler never attached) | 🔴 |
| Settings file (`config/settings.json`) — `theme`, `export_directory` only | `app/settings/repository.py::SettingsRepository` (default `settings_path = BASE_DIR/"config"/"settings.json"`) | `BASE_DIR`-relative | Yes | Dev: yes. Packaged: same `BASE_DIR`/temp-dir exposure as the DB | 🟠 |
| VirusTotal API key | `app/secrets/store.py::RustKeystoreHandoffSecretStore` | **Not a filesystem path.** Read-only observer of an env var (`SOCIQ_SECRET_VIRUSTOTAL_API_KEY`) populated by the Rust parent process for the child's lifetime only (ADR-008). Real storage is OS keystore, owned by Rust (`keystore-core`, `src-tauri/src/keystore.rs`), out of this audit's Python-persistence scope. | N/A | N/A (delegated to Rust/OS keystore) | 🟢 — correctly out-of-band |
| `database/soc_iq.db` present in this checkpoint | (checked-in file, not written by the app in this session) | `BASE_DIR/database/soc_iq.db` — the exact dev-mode write target | — | — | 🟢 informational — see note below |
| `app/reporting/templates/*.j2`, `app/database/migrations/*.sql` | Not written at runtime; read-only bundled resources | `Path(__file__).parent`-relative | No | Bundled via PyInstaller `datas`; correctly Class 1 | 🟢 |
| Report/CSV export files | `app/reporting/*_exporter.py`, `app/services/investigation_csv_export.py` | Caller-supplied absolute `output_path` | Yes | User-selected — outside SOC-IQ's own persistence responsibility | 🟢 |

**Note on the checked-in `database/soc_iq.db`:** this checkpoint ships a
28,672-byte SQLite file at exactly the path the application itself writes
to in development mode. This is a repo-hygiene observation (generated
runtime state committed alongside source), not a packaged-runtime defect —
flagged for awareness, not for action in R2-A.

No PID files, lock files, cache directories, or `tempfile`/`TemporaryDirectory`
usage were found anywhere in `app/` (the required search terms `cache`,
`temp`, `TemporaryDirectory`, `NamedTemporaryFile` returned no matches inside
`app/`; `tempfile` appears only in `app/settings/repository.py` for an
atomic-write-via-rename pattern when saving `settings.json`, which is a
correct, transient use and not a separate persistence location).

## 8. PyInstaller Path Analysis

```
socq-backend(.exe)  [onefile, runtime_tmpdir=None]
        ↓ on each launch
fresh temporary extraction directory (new every run; removed on clean exit)
        ├── app/reporting/templates/   (bundled `datas` — Class 1, correct)
        ├── app/database/migrations/   (bundled `datas` — Class 1, correct)
        ├── frozen Python modules (app/config.py, app/database/connection.py, ...)
        └── BASE_DIR = Path(__file__).resolve().parent.parent
                → resolves INSIDE this same temporary directory
                → DATABASE_DIR, LOGS_DIR, OUTPUT_DIR, SAMPLES_DIR all inherit it
```

Entry point frozen: `app/api/entrypoint.py` (confirmed via
`Analysis([str(PROJECT_ROOT / "app" / "api" / "entrypoint.py")], ...)` in the
`.spec`). `app/gui/**` (PySide6) is explicitly excluded — confirmed both by
the `.spec`'s `excludes` list and its header comment. `initialize_application()`
and `configure_logger()` (Part 5/9) are unreachable from this entry point.

Every current SOC-IQ path that falls into the "potentially writable runtime
files, ephemerally located" category:

- `DATABASE_PATH` (`BASE_DIR/database/soc_iq.db`)
- `LOG_FILE` (`BASE_DIR/logs/soc_iq.log`) — moot in practice per Part 5, but would be if logging were fixed without also fixing `BASE_DIR`
- `SAMPLES_DIR` (`BASE_DIR/samples`) — only used by `app/cli.py`'s default sample path, not part of the API/GUI production data flow, but shares the defect
- `OUTPUT_DIR` / `JSON_EXPORT_FILE` / `CSV_EXPORT_FILE` — dead code (Part 6), but if ever wired up would inherit the same defect
- `SettingsRepository`'s default `settings_path` (`BASE_DIR/config/settings.json`)
- `ApplicationSettings.export_directory`'s default value

## 9. Resource vs Mutable-Data Classification

**CLASS 1 — Bundled/read-only resource** (correctly `__file__`-relative, no
change needed):
- `app/reporting/templates/report.html.j2` (`app/reporting/html_exporter.py::_TEMPLATE_DIR`)
- `app/database/migrations/*.sql` (`app/database/migration_runner.py::MIGRATIONS_DIR`)

**CLASS 2 — Persistent application/user data** (currently mis-rooted under
`BASE_DIR`, the actual R2-B target):
- `DATABASE_PATH`
- `LOG_FILE`
- `SettingsRepository` default `settings_path`

**CLASS 3 — User-selected destination** (already correct, no change needed):
- `ExportReportRequest.output_path`
- `ExportHistoryCsvRequest.output_path`
- Legacy GUI `QFileDialog` exports (out of scope — retired code)

**CLASS 4 — Temporary data:**
- None found as a distinct location. `SettingsRepository`'s atomic-write
  temp file (via `tempfile`, immediately renamed into place next to
  `settings.json`) is the only transient-file usage in the codebase and is
  not a separate persistence concern.

No Class 1 resource is at risk of being mistakenly relocated by this audit —
both are explicitly declared as PyInstaller `datas` and use `Path(__file__)`
correctly for the reason the `.spec` file's own comment states (frozen
import machinery can't see plain non-`.py` files on `sys.path`).

## 10. Centralization Audit

There **is** a single authoritative module for base paths:
**`app/config.py`** (`BASE_DIR` and everything derived from it). Every
callsite reuses it rather than recomputing its own root:

- `app/database/connection.py` imports `DATABASE_PATH`
- `app/logger.py` imports `LOG_FILE`
- `app/initializer.py` imports `LOGS_DIR`, `OUTPUT_DIR`, `DATABASE_DIR`, `SAMPLES_DIR`
- `app/settings/models.py` and `app/settings/repository.py` import `BASE_DIR` directly
- `app/database/migration_runner.py` and `app/reporting/html_exporter.py` use their own `Path(__file__)` (correctly — these are Class 1 resources, not user data, so they should *not* route through the same abstraction as Class 2 data)

No competing/duplicated path-resolution mechanism exists. This is a
favorable finding for R2-B: the defect is concentrated in one place
(`app/config.py`'s `BASE_DIR` computation and the four Class-2 paths derived
from it), not scattered across independent hardcoded paths.

## 11. Call-Site Inventory

| File | Function/Class | Data Written | Path Source | Runtime Mode | Risk |
| --- | --- | --- | --- | --- | --- |
| `app/database/connection.py` | `DatabaseConnection.connect()` | SQLite DB | `app.config.DATABASE_PATH` (default arg) | Dev: OK. Packaged: ephemeral | 🔴 |
| `app/logger.py` | `configure_logger()` | Log file | `app.config.LOG_FILE` | Dev: OK, but only reachable from retired GUI. Packaged: unreachable (never called) | 🔴 |
| `app/initializer.py` | `initialize_application()` | Creates `LOGS_DIR`, `OUTPUT_DIR`, `DATABASE_DIR`, `SAMPLES_DIR` | `app.config.*` | Only called from `app/main.py` (retired GUI, excluded from packaging) | 🟠 |
| `app/settings/repository.py` | `SettingsRepository.__init__` / `save()` | `config/settings.json` | `BASE_DIR/"config"/"settings.json"` (default) | Dev: OK. Packaged: ephemeral | 🟠 |
| `app/reporting/export_manager.py` + per-format exporters | `export_html/json/markdown/pdf` | Report file | Caller-supplied `output_path` | Both modes: correct (Class 3) | 🟢 |
| `app/services/investigation_csv_export.py` | `export_investigations_history_csv` | CSV file | Caller-supplied `output_path` | Both modes: correct (Class 3) | 🟢 |
| `app/database/migration_runner.py` | module-level `MIGRATIONS_DIR` | (read-only) | `Path(__file__).resolve().parent / "migrations"` | Correct in both modes (Class 1, bundled) | 🟢 |
| `app/reporting/html_exporter.py` | module-level `_TEMPLATE_DIR` | (read-only) | `Path(__file__).parent / "templates"` | Correct in both modes (Class 1, bundled) | 🟢 |

## 12. Test Inventory

| Test | What It Proves | Development | Packaged | Gap |
| --- | --- | --: | --: | --- |
| `tests/test_settings.py::test_base_dir_is_derived_from_module_file_not_cwd` | `BASE_DIR` equals the real project root | ✅ Covered | ❌ | No frozen-mode equivalent |
| `tests/test_settings.py::test_base_dir_resolution_is_stable_from_a_different_cwd` | `BASE_DIR` is independent of the process's launch `cwd` (subprocess launched from an unrelated directory) | ✅ Covered | ❌ | Proves cwd-independence, not `_MEIPASS`/frozen-independence — this is the exact gap R2-B must close |
| `tests/test_settings.py::test_default_settings_export_directory_is_under_base_dir` | `export_directory` default derives from `BASE_DIR` | ✅ Covered | ❌ | Same gap |
| `tests/test_migration_runner.py` (extensive suite) | Migration correctness against an explicit `tmp_path` database | ✅ Covered | N/A | Tests always inject an explicit `database_path`; never exercises the real default `DATABASE_PATH` or a frozen `MIGRATIONS_DIR` |
| `tests/test_settings.py` (repository round-trip tests) | Settings load/save correctness | ✅ Covered (always via `tmp_path`) | ❌ | Never exercises the real default `settings_path` |
| — | Logging initialization reachability from the production entrypoint (`app/api/app.py`) | ❌ | ❌ | **No test exists** that `configure_logger()`/`initialize_application()` are (or are not) called from the API/sidecar startup path. This audit found the gap by direct code trace, not from an existing test. |
| — | `sys.frozen` / `sys._MEIPASS` simulation for any of `BASE_DIR`, `DATABASE_PATH`, `LOG_FILE`, `MIGRATIONS_DIR`, `_TEMPLATE_DIR` | ❌ | ❌ | No test anywhere in the repository sets `sys.frozen`/`sys._MEIPASS` or otherwise simulates packaged execution. This is the single largest test gap relative to the defect in Part 4. |

Missing tests identified for R2-B (not implemented here, per scope):
1. A frozen-mode-simulating test proving the *new* Class-2 data root does **not** resolve under a `_MEIPASS`-style temporary path.
2. A regression test asserting `configure_logger()`/an equivalent is actually invoked from `app/api/app.py`'s startup (or wherever R2-B wires it), closing the gap in Part 5.
3. A restart-persistence test: write to the DB, tear down the process-level state, reconstruct `DatabaseConnection` with the default path, and confirm the same file/data is found — today's tests never exercise the real default path end-to-end.

## 13. Documentation Cross-Check

No document in `docs/` (including `docs/phase4/*`, `docs/architecture/*`,
`packaging/README.md`) claims that packaged-runtime data persistence is
already solved. The many "persistence" references found in `docs/phase4/`
concern *in-process* or *database-schema* persistence guarantees (e.g. SSE
event history, JSON-blob storage shape), not the packaged filesystem
location this audit covers. `packaging/pyinstaller/socq_backend.spec`'s own
header comment is explicit and accurate about what is/isn't bundled as data
— no discrepancy found there either.

**Finding:** this is a documentation *gap*, not a documentation
*contradiction* — no false claim to correct, but no document currently
describes where SOC-IQ's database/logs/settings should live in a packaged
install (e.g. no reference to `%APPDATA%`, `~/Library/Application Support`,
or `XDG_DATA_HOME`). R2-B's design should be recorded in
`docs/architecture/` once decided.

---

## 14. Risk-Ranked Findings

| # | Finding | Risk |
| --- | --- | --- |
| 1 | `BASE_DIR = Path(__file__).resolve().parent.parent` resolves inside PyInstaller's ephemeral onefile extraction directory in packaged mode; `DATABASE_PATH` inherits this — investigation data would not survive a restart of the packaged app | 🔴 RELEASE BLOCKER |
| 2 | The production sidecar entrypoint (`app/api/app.py` / `app/api/entrypoint.py`) never calls `configure_logger()` or `initialize_application()` — no log file is ever created in the packaged product, independent of the path defect above | 🔴 RELEASE BLOCKER |
| 3 | `SettingsRepository`'s default `settings_path` (`config/settings.json`) and `ApplicationSettings.export_directory`'s default value both inherit the same `BASE_DIR` defect | 🟠 HIGH |
| 4 | `app.config.OUTPUT_DIR` / `JSON_EXPORT_FILE` / `CSV_EXPORT_FILE` are dead, unused constants that could mislead a future maintainer about the real (Class 3, user-selected) export path | 🟡 MEDIUM |
| 5 | No `sys.frozen`/`_MEIPASS` simulation exists anywhere in the test suite, despite an existing, well-targeted cwd-independence test suite for the same `BASE_DIR` value — the precedent for this kind of test already exists and was not extended to packaged mode | 🟡 MEDIUM |
| 6 | `database/soc_iq.db` (live data) is checked into the project tree at the app's own default dev-mode write path | 🟢 LOW |
| 7 | No `platformdirs`/OS-conventional user-data-directory concept exists anywhere in the Python codebase | 🟢 LOW / INFORMATIONAL |
| 8 | Class 1 resources (`migrations/`, `templates/`) are correctly implemented and bundled — explicitly not a finding, recorded to prevent R2-B from mis-touching them | 🟢 INFORMATIONAL |

## 15. R2-B Implementation Requirements (evidence-based, not implemented here)

1. Introduce a packaged-mode-aware base path for **Class 2 data only**
   (database, logs, settings) — e.g. branch on `getattr(sys, "frozen", False)`
   / `sys._MEIPASS` and, when frozen, resolve against an OS-conventional
   per-user application-data directory (equivalents of `%APPDATA%`,
   `~/Library/Application Support`, `XDG_DATA_HOME`) rather than any
   `__file__`-derived location. Do **not** change the Class 1 resource paths
   (`MIGRATIONS_DIR`, `_TEMPLATE_DIR`) — they are correct as-is.
2. Wire `configure_logger()` (or an equivalent handler-attachment step) into
   the actual production startup path (`app/api/app.py`'s lifespan/startup,
   or `app/api/entrypoint.py` before `uvicorn.run`) — today's
   `initialize_application()`/`configure_logger()` pair is stranded in the
   retired `app/main.py` and never executes in the shipped product.
3. Point `SettingsRepository`'s default `settings_path` and
   `ApplicationSettings.export_directory`'s default value at the same new
   Class-2 root chosen in (1), for consistency.
4. Either wire `app.config.OUTPUT_DIR`/`JSON_EXPORT_FILE`/`CSV_EXPORT_FILE`
   into a real caller or remove them — leaving them as dead config next to
   the real (Class 3) export mechanism is a maintenance hazard.
5. Add the three tests identified in Part 12, following the existing
   pattern in `tests/test_settings.py`'s `test_base_dir_resolution_is_stable_from_a_different_cwd`
   (subprocess-based simulation), extended to simulate `sys.frozen`/`sys._MEIPASS`.
6. Decide and document (in `docs/architecture/`) the chosen per-OS data
   directory scheme, since no document currently specifies one (Part 13).
7. Resolve the checked-in `database/soc_iq.db` (Part 7 note) — likely a
   `.gitignore`/checkpoint-policy fix rather than a code fix, flagged for
   whoever owns repo hygiene going into R2-B.

None of the above is implemented in this checkpoint.

---

## 16. Modified Files

Only this document was added. No existing source, test, configuration, or
packaging file was modified.

- **Added:** `docs/audits/SOC-IQ-R2-A-PERSISTENCE-PATH-INVENTORY.md` (this file)

## 17. Testing

This part made no source changes, so no functional regression is possible
from this checkpoint's own work. No test suite was re-run to "produce a
number," per the R2-A scope instruction. All test-inventory statements in
Part 12 above are based on direct reading of the referenced test files
(file and function names quoted verbatim), not on execution.

## 18. Verdict

```text
PASS — R2-A CLOSED
```

Two 🔴 release-blocker findings were discovered and documented (packaged
database path ephemerality; packaged logging never initialized). Per the
R2-A brief, discovery and accurate documentation — not remediation — is the
success criterion for this part. Both are carried forward as explicit R2-B
requirements in Part 15.

---

## R2-B Implementation Status

**Status:** IMPLEMENTED. This section records what R2-B changed against
this document's own findings (Part 15). The findings above are historical
and were not rewritten.

### What was changed

| R2-A Finding (Part 15 item) | Change | File(s) |
| --- | --- | --- |
| #1 — `BASE_DIR`/`DATABASE_PATH` resolve inside the ephemeral PyInstaller extraction dir | Introduced `APP_DATA_ROOT` via `platformdirs.user_data_dir(APP_NAME, APP_AUTHOR, roaming=True)` (OS-native, never consults `__file__`/`sys._MEIPASS`). `DATABASE_DIR`, `LOGS_DIR`, `CONFIG_DIR` now derive from it. `BASE_DIR` and `SAMPLES_DIR` are unchanged (Class 1). | `app/config.py` |
| #2 — production sidecar (`app/api/app.py`) never calls `configure_logger()`/`initialize_application()` | Wired both into FastAPI's `lifespan` context manager, which runs on every real startup of the ASGI app (including under `app/api/entrypoint.py`'s `uvicorn.run`) | `app/api/app.py` |
| #3 — `SettingsRepository` default `settings_path` / `ApplicationSettings.export_directory` default inherit the `BASE_DIR` defect | Added `CONFIG_DIR`/`SETTINGS_FILE`/`EXPORTS_DIR` to `app/config.py`; repository and model defaults now point at them instead of `BASE_DIR` | `app/settings/repository.py`, `app/settings/models.py` |
| #4 — `OUTPUT_DIR`/`JSON_EXPORT_FILE`/`CSV_EXPORT_FILE` are dead, misleading constants | Removed. Replaced with `EXPORTS_DIR` (an actual, app-owned *default* export location, distinct from the Class 3 caller-supplied `output_path` these dead constants were never wired to) | `app/config.py` |
| #5 — no test simulates `sys.frozen`/`sys._MEIPASS`; no restart-persistence test; no test proves logging is reachable from the production entrypoint | Added `tests/test_persistence_paths.py` (11 tests, see below) | `tests/test_persistence_paths.py` (new) |
| #6 — no document specifies the chosen per-OS data directory scheme | This section | `docs/audits/SOC-IQ-R2-A-PERSISTENCE-PATH-INVENTORY.md` |
| #7 — checked-in `database/soc_iq.db` | Not touched (out of scope for R2-B; flagged again below as a repo-hygiene item for whoever owns it) | — |

`initialize_application()` (`app/initializer.py`) now creates `LOGS_DIR`,
`DATABASE_DIR`, `CONFIG_DIR`, `EXPORTS_DIR`, and `SAMPLES_DIR` (the last
retained from before — a harmless, pre-existing verification of a bundled
resource directory, not itself part of the Class 2 fix).

`tests/conftest.py`'s D2 test-isolation fixture and two tests in
`tests/test_settings.py`
(`test_default_settings_export_directory_is_under_base_dir` →
`test_default_settings_export_directory_is_under_app_data_root`;
`test_default_settings_path_is_under_base_dir` →
`test_default_settings_path_is_under_app_data_root`) were updated to match
the new default locations — these were asserting the exact `BASE_DIR`-based
defaults that Part 15 required moving off of, so updating them is the
direct, necessary consequence of finding #1/#3, not an unrelated change.

Added dependency: `platformdirs` (`requirements.txt`, `requirements.lock.txt`,
pinned to the version resolved in the verification environment, `4.9.4`).

### Chosen per-OS data directory scheme (finding #6)

`platformdirs.user_data_dir("SOC-IQ", "Himanshu Gupta", roaming=True)`,
which resolves to:

- Windows: `%APPDATA%\Himanshu Gupta\SOC-IQ` (roaming profile)
- macOS: `~/Library/Application Support/SOC-IQ`
- Linux: `$XDG_DATA_HOME/SOC-IQ` (or `~/.local/share/SOC-IQ` if unset)

Chosen over a hand-rolled `sys.frozen`/`_MEIPASS` branch (the specific
mechanism Part 15 item 1 suggested) because `platformdirs` was already
identified in Part 2 as absent-but-worth-evaluating, is the de facto
standard for this exact problem, and — critically — never inspects
`__file__`, `sys.frozen`, or `sys._MEIPASS` at all, so it is correct in
dev, `python -m`, and frozen-onefile modes by construction rather than by
an explicit branch that could drift out of sync with PyInstaller's actual
behavior.

### Database

`DatabaseConnection`'s default `database_path` argument is now bound to
`app.config.DATABASE_PATH` (`APP_DATA_ROOT/database/soc_iq.db`) at import
time, exactly as before structurally — only the value changed. Schema,
migrations, `MigrationRunner`, and `InvestigationRepository` are
untouched. `connect()`'s existing "create the parent directory of the
*actual* configured path" behavior (already correct, per its own comment)
was not touched.

### Logging

`configure_logger()` itself (formatter, handler-replacement safety,
verbose/console-handler behavior) is unchanged. Only `LOG_FILE`'s value
changed (now under `APP_DATA_ROOT/logs`), and it is now actually invoked
in production via `app/api/app.py`'s `lifespan`, closing the reachability
gap Part 5/15 identified. `app/main.py` (retired GUI) still calls it too —
harmless and idempotent (`configure_logger()` already tolerated repeat
calls before this change).

### Exports

No change to the real (Class 3) export mechanism —
`ExportReportRequest.output_path` / `ExportHistoryCsvRequest.output_path`
in `app/application/dto.py` still require and use exactly the
caller-supplied absolute path; `app/application/dto.py` does not import
`app.config` at all (verified by
`test_export_dto_does_not_depend_on_app_config`). `ApplicationSettings.export_directory`'s
*default* (an advisory pre-fill value only) now points at the new
`EXPORTS_DIR`, replacing the dead-code `OUTPUT_DIR` it previously
referenced.

### Configuration / runtime state

`SettingsRepository`'s default `settings_path` now resolves under
`APP_DATA_ROOT/config/settings.json`. File format, atomic-write-via-rename
behavior, and the settings.json/secret-store split (Phase 4M Part 2B) are
unchanged. The VirusTotal API key path (OS keystore via Rust, per ADR-008)
was not touched — it was already out-of-band (Part 7, 🟢).

### Resource separation

`MIGRATIONS_DIR` (`app/database/migration_runner.py`) and `_TEMPLATE_DIR`
(`app/reporting/html_exporter.py`) are unchanged — still `Path(__file__)`-relative,
still resolve under `BASE_DIR`, not `APP_DATA_ROOT`. Verified by
`test_bundled_resources_remain_file_relative_not_persistent`.

### Tests added

`tests/test_persistence_paths.py` (11 tests), covering every proof point
in Part 15 item 5:

1. `test_app_data_root_matches_platformdirs` — root == `platformdirs.user_data_dir(...)`
2. `test_app_data_root_is_not_derived_from_base_dir`
3. `test_app_data_root_independent_of_cwd` — subprocess from unrelated cwd
4. `test_app_data_root_not_under_simulated_meipass` — subprocess with `sys.frozen=True`/`sys._MEIPASS` set
5. `test_initialize_application_creates_persistent_directories`
6. `test_database_connection_default_path_is_persistent`
7. `test_database_connection_survives_reconstruction_against_persistent_path` — restart-persistence proof (write → close → reopen → data still present)
8. `test_configure_logger_writes_to_persistent_log_file`
9. `test_production_sidecar_wires_initialization_on_startup` — drives the real FastAPI `lifespan` via `TestClient` and asserts both calls actually execute
10. `test_bundled_resources_remain_file_relative_not_persistent`
11. `test_export_dto_does_not_depend_on_app_config`

### Repo hygiene note carried forward (finding #7)

`database/soc_iq.db` (28,672 bytes, checked in at the app's own dev-mode
write path) is still present in this checkpoint, unmodified and
undeleted, per R2-B's explicit "do not silently delete/overwrite" scope
rule. Resolving this (almost certainly a `.gitignore` addition) remains
unassigned to any R2 part so far and should be picked up by whoever owns
repo hygiene.

### What R2-B did not touch

Database schema and migrations, GUI/React/Tauri/Rust code, Threat
Intelligence, Analyze behavior, report content/exporters themselves (only
their *default output directory constant*, which was dead code, changed),
AI, security architecture, the legacy GUI, user-selected save destinations,
temporary-file behavior, PyInstaller packaging verification, and the
Windows installer — all explicitly out of scope per the R2-B brief.

## R2-D Logs & Generated Exports Persistence

### Scope

This part covered only application-owned logs and application-owned
default/generated export destinations. Database persistence (R2-C) was
not touched.

### Finding: architecture was already correct

Tracing the actual logging and export code paths (not just naming)
showed R2-B had already fully closed this gap when `APP_DATA_ROOT`,
`LOGS_DIR`, and `EXPORTS_DIR` were introduced:

- **Logging** — `app/logger.py`'s `configure_logger()` writes to
  `app.config.LOG_FILE` (`APP_DATA_ROOT / "logs" / "soc_iq.log"`), not
  a `BASE_DIR`/CWD/`_MEIPASS`-relative path. It creates the parent
  directory defensively before opening the file handler, and — safe to
  call more than once — closes and removes any previously attached
  handlers before adding new ones, so repeated (re)configuration (e.g.
  toggling verbose mode) cannot leak duplicate `FileHandler`s or
  produce duplicate log entries.
- **Application-owned default exports** — `EXPORTS_DIR`
  (`APP_DATA_ROOT / "exports"`) is created at startup by
  `initialize_application()` and used only as the advisory default
  shown in Settings (`ApplicationSettings.export_directory`). It is
  never consulted by the actual exporters.
- **User-selected exports** — every real exporter
  (`JSONReportExporter`, `MarkdownReportExporter`, `HTMLReportExporter`,
  `PDFReportExporter`, `investigation_csv_export`) takes an explicit
  `output_path: Path` supplied by the caller. `ExportReportRequest` /
  `ExportHistoryCsvRequest` require this path to be absolute and
  `app/application/dto.py` imports nothing from `app.config` —
  confirmed unchanged.
- **Resources** — bundled Jinja2/report templates and migration SQL
  continue to resolve under `BASE_DIR`, untouched.
- **Temporary files** — the only `tempfile` usage in the affected
  areas is `app/settings/repository.py`'s atomic-write temp file for
  `settings.json`, which is correctly transient (out of R2-D's scope;
  R2-A did not flag it as misclassified).

No production code changes were required. This part's contribution is
closing the remaining **verification** gap R2-A/B left open for logs
and exports specifically: a real subprocess-boundary log-persistence
proof, a real (non-mocked) generated-export persistence proof, an
explicit end-to-end proof that a user-selected destination outside
`APP_DATA_ROOT`/`EXPORTS_DIR` is honored exactly, and a handler-
duplication regression test.

### New regression tests (`tests/test_persistence_paths.py`)

1. `test_log_persists_across_subprocess_boundary` — two real,
   independent subprocesses write distinct marker log lines to the
   same on-disk log file; both markers are confirmed present after
   both processes have exited (real process-boundary proof, content
   verified — not just file existence).
2. `test_default_export_directory_is_under_app_data_root`
3. `test_settings_export_directory_defaults_to_persistent_exports_dir`
4. `test_real_export_write_persists_at_destination` — a real
   `JSONReportExporter.export()` call (no mocked filesystem) writes to
   an isolated exports directory; a separate subprocess then opens the
   file and confirms its content, proving the export outlives the
   producing process.
5. `test_explicit_user_selected_destination_honored_exactly` — exports
   to a path deliberately outside both `APP_DATA_ROOT` and
   `EXPORTS_DIR` and confirms the exact path is used, unredirected.
6. `test_configure_logger_does_not_duplicate_handlers` — configures
   the logger three times (including a verbose-mode toggle) and
   confirms exactly one `FileHandler` remains attached, pointed at the
   correct file, and that a subsequent log call produces exactly one
   line — no duplicate handlers, no duplicate entries.

### Test results

```
$ python -m pytest tests/test_persistence_paths.py -q
17 passed, 1 warning in 0.83s

$ python -m pytest tests/ -q
1233 passed, 1 warning, 3 subtests passed in 10.88s
```

### Known limitations

This part does not prove real Windows packaged (PyInstaller/installer)
persistence — that remains a later, out-of-scope verification stage.
The subprocess proofs above use `sys.executable` running from source,
not a frozen executable.

### Verdict

**PASS — R2-D CLOSED**

## R2-E PyInstaller Packaged Persistence Verification

### Environment (honest disclosure)

This verification ran in a **Linux** container, not Windows:

```
OS: Linux 6.18.44 x86_64 (containerized)
Python: 3.12.3
PyInstaller: 6.22.2
```

`packaging/pyinstaller/socq_backend.spec` is OS-agnostic Python and was
built/run exactly as documented (`pyinstaller
packaging/pyinstaller/socq_backend.spec --noconfirm`), producing a real
onefile ELF executable (`dist/socq-backend`, 28 MB) that PyInstaller's
bootloader extracts to a `/tmp/_MEI*` temp directory per launch — the
same onefile extraction mechanism the Windows build uses (Windows would
extract to a `%TEMP%\_MEI*`-style directory instead). This proves the
**PyInstaller onefile extraction-vs-persistent-data architecture**, but
it is **not** a substitute for running the actual Windows-targeted
build on Windows. See "Remaining limitations" below.

### Build

```
$ pyinstaller packaging/pyinstaller/socq_backend.spec --noconfirm
...
Build complete! The results are available in: dist/
```

Build succeeded with no errors. Two informational warnings
(`Library ole32/shell32 required via ctypes not found`) are expected on
Linux — those are Windows-only ctypes libraries referenced defensively
by a dependency and are irrelevant off Windows.

### Real packaged-runtime verification performed

Using the actual built executable (not source-mode Python), with
`HOME`/`XDG_DATA_HOME` pointed at an isolated, throwaway directory and
`SOCIQ_SIDECAR_PORT` pinned so the real HTTP command API could be
driven directly:

1. **Run #1** launched the packaged executable. It printed its bound
   port to stdout per the real handshake contract, then a real
   `POST /commands/analyze_report` call (against an actual sample
   report file) drove the full production pipeline — IOC extraction,
   risk scoring, database save, five timeline events — creating
   investigation `id=1` in
   `~/.local/share/SOC-IQ/database/soc_iq.db`. A real
   `POST /commands/export_report` call then wrote a user-selected JSON
   export to an arbitrary path outside both `APP_DATA_ROOT` and the
   PyInstaller extraction directory.
2. Run #1's extraction directory (`/tmp/_MEI0000060e4vVjYc`) was
   recorded, then the process was terminated (`SIGTERM`).
3. **Run #2** launched the same executable against the *same*
   persistent `HOME`, but received a **different** extraction directory
   (`/tmp/_MEI0000065ezauD3N`) — confirming extraction is genuinely
   per-launch/ephemeral, not reused.
4. A real `POST /commands/get_investigation` call against Run #2
   successfully read back investigation `id=1`, created by Run #1,
   with identical field values (risk score, confidence, SHA-256, etc.).
5. The persistent log file
   (`~/.local/share/SOC-IQ/logs/soc_iq.log`) contained the complete,
   uninterrupted transcript of both runs concatenated — the migration
   log lines from Run #1's startup and Run #2's later
   "Loading investigation 1" line are in the same file.
6. A second export (HTML format) in Run #2 rendered successfully via
   the bundled Jinja2 template (`app/reporting/templates/`, packaged as
   PyInstaller `datas`), proving bundled-resource resolution works
   under the frozen import machinery — the resulting 35 KB HTML file
   was written to the user-selected destination, not the extraction
   directory.
7. `strings` inspection of the built executable and its `datas`
   declaration in the spec confirmed only the two intended resource
   directories (`app/reporting/templates`, `app/database/migrations`)
   are bundled — no `.env`, API key, or the repo's checked-in dev
   `database/soc_iq.db` was found embedded in the package.

### Proof

```
Run #1 DB path:  ~/.local/share/SOC-IQ/database/soc_iq.db
Run #2 DB path:  ~/.local/share/SOC-IQ/database/soc_iq.db
Same persistent path: YES
Previous record visible in run 2: YES
Database under PyInstaller extraction: NO

Run #1 extraction dir: /tmp/_MEI0000060e4vVjYc
Run #2 extraction dir: /tmp/_MEI0000065ezauD3N (different — per-launch)
Log path: ~/.local/share/SOC-IQ/logs/soc_iq.log
Log outside extraction: YES
Log content from both runs present in the single file: YES

User-selected export (JSON, then HTML): written to the exact
caller-supplied path in both runs; never redirected under
APP_DATA_ROOT or EXPORTS_DIR.

Extraction cleanup: on a clean SIGTERM shutdown, PyInstaller's
bootloader removed the extraction directory (observed after Run #2's
shutdown). On a less graceful termination during Run #1, one
extraction directory was observed to remain on disk after process
exit — a known PyInstaller onefile-bootloader characteristic, not a
SOC-IQ defect, and irrelevant to the persistence guarantee since no
application-owned mutable data was in it.
```

### Automation added

`packaging/scripts/verify_packaged_persistence.py` — a standalone
smoke-test script that performs the exact sequence above (build-or-
reuse an executable, launch twice against an isolated persistent HOME,
drive the real command API, assert all eight proof points) and exits
non-zero on any failure. Run with:

```
python packaging/scripts/verify_packaged_persistence.py
```

or, to reuse an already-built executable:

```
python packaging/scripts/verify_packaged_persistence.py --exe dist/socq-backend
```

Executed twice during this part (once building fresh, once reusing the
existing build) — both runs: all 8 checks `PASS`.

### Source vs packaged comparison

| Behavior              | Source Mode              | PyInstaller Mode (Linux build) | Expected               |
|------------------------|---------------------------|----------------------------------|-------------------------|
| Database location       | `APP_DATA_ROOT/database/` | `APP_DATA_ROOT/database/` (same) | Persistent              |
| Log location             | `APP_DATA_ROOT/logs/`     | `APP_DATA_ROOT/logs/` (same)     | Persistent              |
| App-owned export dir     | `APP_DATA_ROOT/exports/` (advisory only, unused by real exporters) | same | Persistent |
| User-selected export     | exact caller path         | exact caller path                | User-selected            |
| Bundled resources (templates/migrations) | `BASE_DIR`-relative | packaged as PyInstaller `datas`, resolved via frozen import machinery | Package/resource path |
| Temporary files          | none in scope             | one-file extraction dir, per-launch, outside `APP_DATA_ROOT` | Temporary |

No unexpected differences observed.

### Existing regression suite

No source code changes were required for R2-E (the R2-B/R2-D
architecture already worked correctly under packaging). Full suite
re-run for hygiene:

```
$ python -m pytest tests/ -q
1233 passed, 1 warning, 3 subtests passed in 11.58s
```

### Remaining limitations (explicit)

- **This is not Windows verification.** The spec was built and run on
  Linux, producing a Linux ELF onefile executable. It proves the
  PyInstaller onefile extraction-vs-persistent-data architecture is
  sound in principle and exercised correctly by SOC-IQ's code, but the
  actual Windows executable (built via `packaging/scripts/build-windows.ps1`
  on a Windows host, using `%APPDATA%` rather than XDG paths) has not
  been built or run.
- No installer-level (MSI/NSIS/etc.) installation or runtime
  verification was performed — that is explicitly later work.
- The Tauri parent process was not involved; the sidecar was launched
  directly, matching how `src-tauri/src/sidecar.rs` would spawn it, but
  without the Rust parent itself.
- VirusTotal enrichment was not exercised (no API key configured in the
  isolated test environment) — irrelevant to persistence, out of scope.

### Verdict

**FAIL — R2-E NOT CLOSED — PACKAGED RUNTIME NOT PROVEN (Windows)**

Rationale: the R2-E brief specifically requires proof on Windows
(`%APPDATA%`, the actual `build-windows.ps1` toolchain, a Windows
executable). That was not available in this environment. The
persistence architecture was, however, verified end-to-end using the
project's real, unmodified PyInstaller spec and a real built onefile
executable, actually launched twice with actual command-API-driven
writes and reads across a genuine process/extraction-directory
boundary — this is real packaged-runtime proof, just not on the target
OS the brief requires. R3 work should not proceed past this point
claiming Windows packaged persistence is proven; a Windows-hosted
re-run of `packaging/scripts/verify_packaged_persistence.py` (or the
equivalent manual steps) is the recommended way to close this
honestly.
