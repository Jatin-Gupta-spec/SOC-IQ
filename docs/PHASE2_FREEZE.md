# Phase 2 — Final Freeze Record

```
Phase 2
Status: FROZEN
```

## Completed

- Part 1A
- Part 1B
- Part 1C
- Part 2A
- Part 2B-1
- Part 2B-2

## Recovery

**Issue found:** a stale local `.pytest_cache` shipped inside the source
ZIP recorded that 10 of the 12 tests in
`tests/gui/test_investigation_analyst_context.py` failed on the last
real `pytest` run performed before this freeze (timestamped ~45
seconds before the final Part 2B-2 commit, so it was never re-run
afterward). All 10 failures were `isVisible()` assertions; the 2
tests in the same file that check label text/tooltip instead of
visibility passed.

**Root cause:** each failing test constructs `InvestigationWorkspacePage`,
`ThreatIntelligenceWidget`, or `IOCSummaryWidget` as a standalone
top-level widget and never calls `.show()` on it. In Qt, `isVisible()`
reflects real on-screen visibility, which requires the whole ancestor
chain up to a *shown* top-level window — it stays `False` regardless of
correct internal `setVisible()` calls until the widget itself is shown.
Reading the widget source confirmed the application logic was already
correct: all three widgets call `setVisible()` correctly inside
`load_investigation()` / `reset()` / `_reset_workspace()`. No other GUI
test file in the suite uses `isVisible()`, consistent with this being
an isolated test-setup gap rather than a wider pattern.

**Fix:** added `widget.show()` (10 one-line additions, one per
affected test) immediately after construction in each affected test.
No assertions were weakened and no expected behavior was changed —
see commit `fix(tests): show top-level widgets before asserting
isVisible() in analyst-context GUI tests`.

**Caveat (read before trusting this fix blindly):** this environment
has no network access, so `pytest` and `PySide6` could not be
installed and the fix could not be dynamically re-run. The diagnosis
and fix are based on static reading of the test file and the exact
widget source it exercises, not on an actual passing test run.
**Recommended next step:** run `pytest tests/gui/test_investigation_analyst_context.py -v`
in an environment with `PySide6` installed to confirm all 12 tests
pass before treating this as fully closed.

No other Phase 2 regressions requiring recovery were found.

## Testing

```
pytest (non-GUI, 11 files, 229 tests): 229 passed, 0 failed, 0 errors
  — real pytest could not be installed (no network access to fetch
    it or its dependencies in this sandbox). Ran the actual,
    unmodified test files through a small pytest-compatible shim
    (fixtures, tmp_path, monkeypatch, capsys, parametrize, skipif,
    raises — see methodology note below) that was itself sanity-
    checked against known pass/fail/error cases before use.
pytest (GUI, 6 files, ~63 tests): NOT RUN — PySide6 dependency
    unavailable (no network access to install it). Import-graph
    check confirms every GUI module's *internal* imports resolve
    correctly; PySide6 itself is the only missing piece.
compileall: PASS (zero syntax errors across the full repository)
import integrity: 102 app submodules walked — 53 import cleanly
    under system Python, 49 fail only on the expected missing
    rich/PySide6, 0 unexpected import failures
database smoke test: PASS — real DatabaseConnection against a
    custom path, save/reload, and reconnection-persistence all
    verified directly (not via the shim)
end-to-end backend pipeline smoke test: PASS — ran the actual
    analyze_report() pipeline (extract → threat intel → score →
    save → reload → reconnect) against samples/malware_report.txt
    with an isolated temp DB; threat intel correctly degraded to
    status=unavailable/reason=missing_api_key with no fabricated
    data; all 4 report exporters (HTML/JSON/Markdown/PDF) produced
    correct, non-empty, readable output with the right severity,
    IOC data, and analyzed_at timestamp (Phase 1 timestamp fix
    confirmed intact — export filename uses export time, report
    content uses analysis time)
```

**Methodology note:** the pytest shim used above executes the real,
unmodified test files exactly as written; it only supplies the
fixture/collection plumbing pytest normally provides. It does not
alter any test's logic or assertions.

## Architecture

- Phase 0 / Phase 1 / Phase 2 Part 1A–2B-2 boundaries remain intact.
- No `GUI → Database` or `GUI → External API` violations beyond the
  existing, correct `GUI → app.database.service.InvestigationService`
  usage, which is the intended Application/Service layer (confirmed
  against `GUI → Application/Service → Backend/Domain →
  Repository/Provider`).
- No `Backend → GUI` imports found anywhere.
- `BadgeType` / `TimelineEvent` remain defined in the shared,
  backend-safe `app/services/models.py`; GUI modules import them
  from there (directly, or re-exported through
  `app/gui/components/feedback/status_badge.py`), never redefined
  locally.

## Known limitations

- GUI test suite (`tests/gui/`) could not be executed in this
  environment; PySide6 is unavailable with no network access to
  install it.
- The CLI's `rich`-based display layer (`app/display.py`) could not
  be exercised directly for the same reason; the argument-parsing
  and non-display logic covered by `tests/test_cli.py` was verified
  (6/6 passing).
- The `test_investigation_analyst_context.py` fix above is
  statically diagnosed and unverified by an actual test run — see
  the caveat in Recovery.

## Next Baseline

`SOC-IQ-Phase2-FINAL-FROZEN.zip` is now the authoritative baseline for
Phase 3.
