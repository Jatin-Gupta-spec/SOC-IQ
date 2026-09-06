# §20 Report Ingestion Size Cap — Implementation (Part 2C-2)

## Selected control
```
Control: Report ingestion size cap (analyze_report input-size validation)
Requirement: docs/security/report-ingestion-security-model.md TARGET STATE
             ("Explicit input size limits are enforced ... before a report
             reaches the extraction pipeline"); threat-model.md's
             "Oversized report / regex DoS" row.
Threat: An oversized report (via analyze_report, whether through the native
        file picker or a direct call to the sidecar's local HTTP endpoint,
        or via the legacy GUI / CLI paths that share the same reader) is
        read fully into memory with no ceiling, then run through several
        regex passes -- an uncapped local resource-exhaustion vector.
Security invariant: A report above MAX_REPORT_SIZE_BYTES is rejected via
        the existing ReportReadError channel, based on a stat() size
        check performed before the file is ever opened for reading.
```

## Re-audit before implementation
Confirmed by direct inspection that `app/extractor.py::read_report()` did
`file.read()` with no size check — the gap was real, not already covered.
Confirmed the DTO layer (`AnalyzeReportRequest.__post_init__`) never
touches the filesystem (pure string validation only, by design, per the
file's own docstring on the frozen-dataclass pattern) — the actual existing
I/O-based validation for `analyze_report` lives in
`AnalyzeReportCommandHandler.handle()`'s `_report_path_is_valid()` helper in
`app/application/handlers.py`, not in the DTO. The Part 2C-1 report's
"affected code" note pointed at the DTO by analogy with `ExportReportRequest`;
tracing the real call path corrected that: the DTO was not the right place
to add I/O, so the fix went into `app/extractor.py::read_report()` itself.
This single choke point protects every current and future caller
(`AnalyzeReportCommandHandler`, the legacy GUI's `AnalyzeController`, and
`app/main.py`'s CLI path) without touching any of those callers, avoiding
duplicated logic and respecting Phase 4O's "don't modify legacy GUI" scope
boundary — no GUI file was touched.

## Implementation
```
Production files changed:
  app/extractor.py
    - added MAX_REPORT_SIZE_BYTES = 10 MB module constant, with an
      in-code rationale for the chosen value (no prior document
      specifies one; documented as a deliberate choice, not a spec
      citation)
    - read_report() now does report_path.stat().st_size and raises
      ReportReadError (the function's existing, documented exception
      type) if the size exceeds the cap -- before opening the file for
      reading

Tests changed (new file):
  tests/test_report_ingestion_size_cap.py
    - 10 unit tests directly against read_report() with real files on
      a real filesystem (oversized/at-cap/under-cap/empty/missing/
      non-UTF-8), including one that patches Path.open to fail the test
      if read_report ever opens an oversized file (proves rejection
      happens before any read, not merely that an exception is raised),
      and one sparse-200MB-file test that would hang/exhaust memory if
      the implementation ever fell back to reading
    - 2 integration tests through the real AnalyzeReportCommandHandler
      entrypoint (oversized report rejected with no analysis.completed
      event and no stack trace in the surfaced error message; a normal
      sample report still succeeds end-to-end)

Documentation changed:
  docs/security/PHASE4O_SECURITY_P2C2_REPORT_SIZE_CAP_IMPLEMENTATION.md (this file)
```

## Security tests
```
Negative/security tests: 6 passed
  (oversized rejected; rejection message states the limit; rejected
  without ever opening the file; massively-oversized sparse file
  rejected cheaply; missing-file and non-UTF-8 regressions preserved)
Positive/legitimate tests: 4 passed
  (exactly-at-cap accepted; just-under-cap accepted; small legitimate
  report unaffected; empty report still accepted)
Regression (handler integration): 2 passed
  (oversized rejected end-to-end via AnalyzeReportCommandHandler with
  correct event sequence; normal sample report still analyzes
  successfully end-to-end)
Total new file: 12/12 passed
```

## Error-handling / logging audit
The rejection message includes the report path and byte counts — the same
disclosure level as the pre-existing `REPORT_NOT_FOUND` error, which already
echoes `report_path` back to the caller (this is a local, single-user
desktop tool; the caller already supplied that path). No secret, credential,
or stack trace is included in the surfaced `response["error"]["message"]`
(asserted directly in the new integration test). `ReportReadError` is a
`SOCIQError` subclass with no explicit entry in
`app/application/errors.py`'s `_EXCEPTION_CODE_MAP`, so it resolves through
the existing MRO walk to the pre-existing generic `"APPLICATION_ERROR"` code
— no new error code was introduced, reusing the established mapping exactly
as the invariant required ("mirroring the existing pattern").

## Existing controls (re-verified after the change)
```
Part 2A (capability snapshot): PASS (22/22)
Part 2B (export path traversal): PASS (18/18)
Part 1B (Rust keystore / secret store / no-direct-keyring): PASS (35/35)
Phase 4O (legacy GUI retirement): PASS (66 retained files, 7 test suites --
  neither count changed; no legacy GUI file was touched)
```

## Full regression
```
Export/capability/keystore/secret + new size-cap suite combined: 87 passed
Full backend (excl. GUI): 849 passed, 1 skipped (837 baseline + 12 new)
GUI (offscreen): 103 passed, 1 skipped (unchanged)
Frontend tsc --noEmit: 0 errors (unchanged -- no frontend file touched)
Frontend vitest: 965/965 passed (unchanged)
Frontend production build: succeeded, 193 modules (unchanged)
keystore-core / sidecar-core / src-tauri cargo check / cargo test:
  ENVIRONMENT BLOCKED -- no Rust toolchain in this sandbox (unchanged
  from every prior session; no Rust file was touched by this control
  anyway)
```

## Environment limitations
No Rust toolchain available (cargo/rustc not found). Not applicable to this
control's own verification (pure Python change), but reported per the
brief's requirement to always state it.

## Known limitations / what this does not cover
- The 10 MB ceiling is this session's own reasoned default, not a value
  taken from any spec — flagged, not asserted as authoritative.
- Regex catastrophic-backtracking risk in `app/extractor.py`'s patterns was
  spot-checked by hand in the Part 2C-1 audit (no obvious pathological
  shape found) but not re-verified with an automated ReDoS fuzz pass in
  this part — the size cap bounds worst-case cost to a fixed ceiling
  regardless, which is the property this control is responsible for.
- Does not address the IPC/CSP loopback wildcard item from Part 2C-1 —
  that remains explicitly deferred pending a product decision, unchanged.

## Verdict: PASS
All new and existing tests pass; no regression in any previously-closed
control; change scope confirmed limited to `app/extractor.py` (production)
and one new test file.
