# §20 Report Ingestion Size Cap — Independent Adversarial Verification (Part 2C-3)

## Control under verification
```
Control: Report ingestion size cap (app/extractor.py::read_report())
Threat: Oversized report read fully into memory before regex IOC-extraction
        passes -- local resource-exhaustion vector, reachable via the
        IPC/HTTP analyze_report command and the CLI path.
Security invariant: A report above MAX_REPORT_SIZE_BYTES (10 MB) is
        rejected via ReportReadError, based on a stat()-only size check
        performed before the file is ever opened for reading.
Trust boundary: Filesystem path supplied by the caller (frontend via
        Tauri/HTTP, or CLI) -- untrusted/user-controlled; enforcement must
        happen in Python before file I/O, not in the DTO (pure string
        validation) and not in Rust (Rust never reads report content).
Production entrypoints: FastAPI POST /commands/{name} -> COMMAND_HANDLERS
        ("analyze_report") -> AnalyzeReportCommandHandler.handle() ->
        app.analyzer.analyze_report() -> app.extractor.read_report();
        app/main.py CLI path -> the same analyze_report() function.
Protected operation: Reading report file contents into memory prior to
        IOC-extraction regex passes.
```

## Attack-surface trace
`read_report()` has exactly one caller in production code (`app/analyzer.py`),
and `analyze_report()` has exactly one production caller
(`AnalyzeReportCommandHandler`) plus the CLI in `app/main.py`, which calls
the same `analyze_report()` function -- not a separate reader. No legacy-GUI
`AnalyzeController` exists in this codebase (a stale reference in the Part
2C-2 report's re-audit narrative; not a real alternate path -- confirmed by
search, not assumed). The FastAPI transport (`app/api/app.py`) exposes a
single generic `POST /commands/{name}` dispatch endpoint routed through
`COMMAND_HANDLERS`; there is no second, lower-level endpoint that reads
report files directly. The Rust side (`src-tauri`) never reads report
content itself -- it proxies to the Python sidecar HTTP API. No
`MAX_REPORT_SIZE_BYTES`-equivalent constant, environment variable, or
config override exists anywhere else in the codebase that could bypass or
widen the cap.

**Bypass status: NONE FOUND.**

## Trust-boundary analysis
The size check happens via `Path.stat()` in `app/extractor.py`, in Python,
immediately before the only `Path.open()` call in the function -- the
correct location for a property that must hold regardless of which
production caller reaches it. `_report_path_is_valid()` in
`app/application/handlers.py` checks existence/is-file only; it does not
duplicate or weaken the size enforcement, which happens once, downstream,
at the single choke point.

## Independent adversarial testing performed
Beyond re-running the Part 2C-2 suite, the following additional adversarial
inputs were exercised directly against the real production entrypoints
(`AnalyzeReportCommandHandler` and the FastAPI `TestClient` over
`POST /commands/analyze_report`), not against `read_report()` in isolation:

```
Oversized report, non-ASCII/unicode filename      -> rejected (ReportReadError, size stated)
Directory path submitted in place of a file       -> rejected (REPORT_NOT_FOUND, pre-existing check)
Symlink pointing at an oversized real file         -> rejected (stat() follows the symlink; no bypass)
Legitimate path with harmless ../ segment, under cap -> accepted (no over-blocking of normal paths)
Oversized report via the real FastAPI HTTP transport -> rejected, same message/code as the direct handler path
```
No forbidden side effect (no `analysis.completed` event, no file ever
opened) occurred in any rejection case. Server-side logs record a full
traceback via `logger.exception` (expected, internal-only); the value
returned to the caller in every case contains only the report path the
caller itself supplied and the byte counts -- no stack trace, secret, or
internal detail beyond that.

## Mutation-style check
The enforcement condition (`if size > MAX_REPORT_SIZE_BYTES`) was locally
neutralized and the Part 2C-2 suite re-run: 5 of 12 tests failed
immediately (the four direct-rejection unit tests and the handler
integration rejection test), confirming the regression suite would catch
removal of the check. The change was then reverted and the suite
re-confirmed green (12/12). No repository state was left modified.

## Test quality
```
Production entrypoint exercised:            YES
Filesystem/side-effect outcome verified:    YES (Path.open patched to fail
                                             the test if called on the
                                             oversized file; sparse
                                             200 MB-file test would
                                             hang/OOM on a read-fallback)
False-pass weakness found:                  NO
False-pass weakness fixed:                  N/A
```

## Existing controls (re-verified)
```
Part 2A (capability snapshot):        PASS
Part 2B (export path traversal):      PASS
Part 1B (keystore / no-direct-keyring / secret store): PASS
Phase 4O (legacy GUI retirement):     PASS (no GUI file touched)
```

## Full regression (this pass, actual)
```
tests/test_report_ingestion_size_cap.py:                    12 passed
Existing-control suites (capability snapshot, export path
  traversal, no-direct-keyring, secret store):               75 passed
Full backend (pytest tests/, excluding tests/gui):          850 passed
GUI suite (offscreen):                                       104 passed
Frontend tsc --noEmit:                                        0 errors
Frontend vitest:                                             965 passed (70 files)
Frontend production build:                                   succeeded, 193 modules
keystore-core / sidecar-core / src-tauri cargo check/test:    ENVIRONMENT BLOCKED
                                                               (no cargo/rustc in
                                                               this sandbox)
```

## Verdict: PASS

No bypass, regression, or test-quality defect was found. No production
code was changed in this part, per the minimal-remediation rule (no flaw
found -> no change).
