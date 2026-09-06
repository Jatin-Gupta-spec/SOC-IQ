# R3-B Python/PyInstaller Release Build Gate

## 1. Source checkpoint
- Filename: `SOC-IQ-R3-A-FRONTEND-BUILD-FINAL-CLOSURE-FULL.zip`
- SHA-256: `b9847bc575bbec952afa5bd433ab26f89dfff1748ada0c278eb977ed4688c635`
- ZIP integrity: PASS (`testzip` clean)
- File count: 685 files / 87 directories / 772 entries

## 2. Toolchain
- Python: 3.12.3 (satisfies `.python-version` = 3.12)
- pip: 24.0 (bootstrap), venv upgraded to 26.2.1
- PyInstaller: 6.22.2 (installed fresh into an isolated venv; not previously present)
- Dependency source: `requirements.lock.txt` (34 pinned distributions, installed byte-for-byte
  as declared -- `pip install -r requirements.lock.txt` in a clean venv)

## 3. Packaging configuration used
- Authoritative spec: `packaging/pyinstaller/socq_backend.spec` (only PyInstaller spec in the
  repository; no competing packaging path found)
- Entrypoint frozen: `app/api/entrypoint.py` (the FastAPI/uvicorn loopback sidecar; not
  `app/main.py`/`app/cli.py`, which are the separate source-checkout CLI path)
- Mode: `--onefile`-equivalent (`EXE()` with no matching `COLLECT()`) -- single executable at
  `dist/socq-backend`, matching Tauri's `externalBin` single-artifact contract
- Bundled `datas`: `app/reporting/templates/*.j2`, `app/database/migrations/*.sql`
- Explicit excludes: `PySide6` (retired GUI toolkit, confirmed off the `app.api.entrypoint`
  import path)
- Wrapper script `packaging/scripts/build_backend.py` additionally stages the built binary
  into `src-tauri/binaries/socq-backend-<target-triple>[.exe]`. This script self-documents
  that a real Windows artifact can only be produced by running it on Windows (or a genuine
  Windows cross-toolchain) -- not reproducible in this Linux sandbox. R3-B ran the underlying
  PyInstaller build directly; running the staging wrapper itself was not necessary to prove
  the build gate and was not performed (no Rust toolchain in this sandbox to detect a real
  target triple from, and staging is a file-copy step, not part of the packaging proof).

## 4. Pre-build test verification (FRESHLY VERIFIED)
- `pytest --ignore=tests/gui -q`: **1129 passed**, 1 warning (pre-existing
  `StarletteDeprecationWarning`, unrelated to packaging), 3 subtests passed, 13.61s
- `QT_QPA_PLATFORM=offscreen pytest tests/gui -q`: **104 passed**, 2.28s
- Total: **1233/1233 backend tests passed**, 0 failed, 0 skipped
- These figures were run fresh in this part's venv, not carried over from
  `requirements.lock.txt`'s header (which documents an earlier, HISTORICAL 987/987 run at a
  different point in the project's history -- test count has grown since).

## 5. PyInstaller release build
- Command: `python -m PyInstaller packaging/pyinstaller/socq_backend.spec --noconfirm`
- Result: **Build complete** (`Build complete! The results are available in: dist`)
- Duration: 40s
- Output: `dist/socq-backend` -- single ELF64 executable, 28,537,744 bytes, stripped
- Architecture: x86_64 Linux (this sandbox's host architecture -- PyInstaller freezes for the
  OS it runs on, per `packaging/README.md`; a Windows artifact requires a Windows build
  machine and was not attempted here)

## 6. Build warnings (classified)
`build/socq_backend/warn-socq_backend.txt` reviewed in full. Every entry falls into one of:
1. **Expected/benign -- Windows-only stdlib/module** (`winreg`, `msvcrt`, `nt`, `_winapi`,
   `win32evtlog`, etc.) -- irrelevant on a Linux build target, expected to resolve on an
   actual Windows build machine via PyInstaller's own platform-conditional imports.
2. **Expected/benign -- optional extras genuinely unused by this app's runtime path**
   (`uvloop`, `httptools`, `websockets`/`wsproto` full stacks, `yaml`, `gunicorn`,
   `watchfiles`, `cryptography`/`OpenSSL`, `brotli`/`h2`, `IPython`, `mypy`, `hypothesis`,
   `numpy`, `olefile`, `defusedxml`, `chardet`, `simplejson`, `sniffio`, `trio`/`outcome`,
   `itsdangerous`, `multipart`/`python_multipart`). None of these are imported by
   `app/api/entrypoint.py`'s actual import graph at runtime; uvicorn's `loops.auto` and
   `protocols.*.auto` fall back to the stdlib asyncio/h11 implementations already present.
3. **Benign, minor spec imprecision -- `email_validator`**: declared defensively in the
   spec's `hiddenimports` but not installed (not in `requirements.lock.txt`) and not actually
   needed -- `grep -rn "EmailStr\|email_validator" app/` returns zero matches. No functional
   impact; left as-is (removing it is spec housekeeping, not a packaging defect requiring a
   fix under R3-B's minimal-fix policy).

No entries were classified as unresolved packaging defects.

## 7. Resource / import completeness
Verified by direct execution (see §8), not just static spec inspection:
- `app/database/migrations/*.sql` -- confirmed loaded and applied: a fresh, empty `$HOME`
  produced a working `soc_iq.db` with the `list_investigations` command returning
  `{"success": true, "data": [], "error": null}` (schema present, query succeeded).
- `app/reporting/templates/*.j2` -- present in the `datas` build log entries (data
  reclassification, 8 entries); not independently exercised via a live report-generation
  request in this part (would require a populated investigation and was not necessary to
  prove the packaging gate given migrations/DB resource loading was already directly proven).
- No `ImportError`/`ModuleNotFoundError` at runtime for any of `fastapi`, `uvicorn`,
  `pydantic`, `platformdirs`, `sqlite3`, `Jinja2`, `requests`, `python-dotenv`.

## 8. Packaged executable smoke test (FRESHLY VERIFIED, Linux only)
Executed the real built binary three times, each with a clean, isolated `$HOME`:
1. **Launch + handshake**: `dist/socq-backend` (with `SOCIQ_SIDECAR_PORT` pinned) printed the
   bound port as a single flushed line on stdout, per the entrypoint's documented handshake
   contract. No stderr output, no crash.
2. **`GET /health`**: `HTTP 200`, body `{"success":true,"data":{"status":"ok"},"error":null}`.
3. **`POST /commands/list_investigations`**: `HTTP 200`, body
   `{"success":true,"data":[],"error":null}` -- this is the real production application
   (`app.api.app`'s command dispatch), not a placeholder/test entrypoint.
4. **Persistence boundary**: after the command above, `$HOME/.local/share/SOC-IQ/database/soc_iq.db`
   and `$HOME/.local/share/SOC-IQ/logs/soc_iq.log` existed -- confirming database and logs are
   written to the OS-conventional persistent app-data directory, not to the ephemeral
   PyInstaller onefile extraction directory (`sys._MEIPASS`).

**Windows execution: `PACKAGED EXECUTION NOT PROVEN -- ENVIRONMENT LIMITATION`.** This
sandbox has no Windows environment and no Rust/Tauri toolchain; only the Linux-native
PyInstaller artifact could be built and executed here. The Windows artifact
(`socq-backend-x86_64-pc-windows-msvc.exe`) was not built and cannot be smoke-tested in this
environment, consistent with `packaging/README.md`'s own stated limitation.

## 9. Secret / data-leakage audit
- Source tree: no `.env` file present; `.gitignore` excludes `.env`. `database/soc_iq.db` in
  the source tree is a documented, intentionally-tracked empty test fixture (see
  `.gitignore`'s own comment, cross-referenced against `tests/test_application_layer.py`,
  `tests/test_integration_e2e.py`, `tests/test_analyzer_pipeline_options.py`) -- verified
  empty (0 rows in `investigations`), not leaked developer data.
  `grep -rniE "(api[_-]?key|secret|password|token)\s*[:=]\s*['\"][A-Za-z0-9]{10,}"` across
  `src/` and `app/` found no hardcoded credentials.
- Built artifact: `strings dist/socq-backend` scanned for the VirusTotal env-var name,
  plausible API-key patterns, and this sandbox's build paths (`/home/claude/...`) -- no
  matches. (Caveat: PyInstaller onefile artifacts store Python bytecode inside a compressed
  archive section, so a raw `strings` pass over the ELF is a weak signal for Python-level
  string literals; the authoritative check is source-level, confirmed above and via
  `packaging/pyinstaller/socq_backend.spec`'s own header, which documents that the VirusTotal
  credential is handed to this process only via the `SOCIQ_SECRET_VIRUSTOTAL_API_KEY`
  environment variable at spawn time by the Rust parent, never read from a file.)
- No real secret was found. Nothing required redaction in this report.

## 10. Persistence boundary regression check
R2-E remains the authoritative packaged-persistence proof; this is the lightweight R3-B
regression check plus one piece of new evidence:
- Static inspection: `app/config.py`'s `DATABASE_DIR`, `LOGS_DIR`, `CONFIG_DIR` all derive
  from `APP_DATA_ROOT = Path(user_data_dir(APP_NAME, APP_AUTHOR, roaming=True))`
  (`platformdirs`), not from `BASE_DIR` (the `__file__`-relative, PyInstaller-extraction-path
  variable, reserved for bundled read-only resources only per that module's own comments).
- Runtime confirmation (§8.4): the packaged executable actually wrote its database and log
  file to `~/.local/share/SOC-IQ/...`, matching the static analysis.
- **Documentation correction**: `packaging/README.md` contained a stale "Known follow-up"
  note, dated to an earlier phase, claiming the database/logs were *not* yet persistent in a
  packaged build. This was contradicted by the current `app/config.py` (an R2-B fix) and by
  this part's own smoke test. Corrected in this part -- see §13.

No regression found. The packaging configuration inspected in R3-B (spec `datas`,
`hiddenimports`, excludes) does not redirect any mutable path into the extraction directory.

## 11. Tests
See §4. 1233/1233 backend tests passed, freshly run in this part's isolated venv.

## 12. Fixes made
Exactly one file changed, and it is documentation only:

| File | Change | R3-B reason |
|---|---|---|
| `packaging/README.md` | Replaced a stale "Known follow-up (not fixed by this part)" note claiming packaged DB/logs are non-persistent with an accurate note reflecting the R2-B fix, cross-referenced against this part's own smoke-test evidence. | Part 15 requires this part's documentation to be accurate; leaving a stale, contradicted defect claim in the packaging docs would actively mislead a future engineer about the current persistence-boundary state, which is squarely what R3-B's Part 10 regression check exists to verify and report on. |

No application code, spec file, or test file was modified -- the build succeeded and all
tests passed against the R3-A checkpoint unchanged.

## 13. Environment limitations
- No Windows environment: the Windows PyInstaller artifact could not be built or executed.
- No Rust/Tauri toolchain: `packaging/scripts/build_backend.py`'s target-triple staging step
  (which needs `rustc -Vv` for a real triple) was not exercised; this does not affect the
  PyInstaller build proof itself, only the later Tauri-staging convenience step.
- Only the Linux-native onefile executable was built and smoke-tested.

## 14. Unresolved findings
None classified as packaging defects. The `email_validator` hiddenimport (§6.3) is noted as
minor spec imprecision, not a defect requiring a fix.
