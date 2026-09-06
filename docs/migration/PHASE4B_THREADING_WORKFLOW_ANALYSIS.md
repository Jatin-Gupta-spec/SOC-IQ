# Phase 4B — Threading / Long-Running Workflow Analysis

**Status:** Phase 4B (Source-Verified). Based on full reads of
`app/gui/workers/analysis_worker.py`, `app/analyzer.py`, and the wiring code in
`app/gui/pages/analyze_page.py`.

## Complete workflow

```
report ingestion  (AnalyzePage._start_analysis: unvalidated path string from UI)
        |
        v
[GUI thread] QThread created + AnalysisWorker moved onto it, signals wired, thread.start()
        |
        v
[Worker thread] AnalysisWorker.run()
        |-- guards against double-entry via self._has_run (defensive, not part of the
        |   documented Qt contract -- protects against a hypothetical duplicate
        |   started/run connection)
        |-- emits `started`
        |
        v
    AnalyzeController.analyze(report_path, progress_callback)
        |-- validate_report(report_path): exists + is_file, else raises FileNotFoundError
        |   BEFORE any work begins (this is the sole validation stage; there is no
        |   separate "validation" step inside analyze_report itself)
        v
    AnalysisService.analyze() -> app.analyzer.analyze_report()
        |
        |-- [progress 10%] read_report()                         -- blocking file I/O
        |-- [progress 25%] extract_iocs()                        -- blocking, CPU (regex)
        |-- [progress 40%] exists_by_report_name()                -- blocking DB read
        |       |-- if duplicate: SELECT existing, RETURN EARLY (skips TI + scoring +
        |       |   save entirely)
        |-- [progress 60%] ThreatIntelService().enrich_results()  -- blocking network I/O
        |       (VirusTotal HTTP calls; can be slow / rate-limited)
        |-- [progress 80%] RiskScoringEngine().calculate()        -- blocking, CPU
        |-- [progress 90%] InvestigationRepository.save()         -- blocking DB write
        |       InvestigationRepository.get_by_id()                -- blocking DB read
        |-- [progress 100%] return {"investigation": ..., "existing": False}
        v
    [Worker thread] emits `finished(result)`  OR, on any uncaught exception,
                     logs full traceback (logger.exception) then emits `failed(str(error))`
        |
        v
[GUI thread] AnalyzePage._on_analysis_finished / _on_analysis_failed
        |-- worker.finished / worker.failed both also connected to thread.quit
        |-- thread.finished connected to: worker.deleteLater, thread.deleteLater,
        |   AnalyzePage._cleanup_worker (clears self._thread / self._worker references)
        v
   UI notification (progress dialog, toast, page refresh -- not independently verified
   this pass, outside stated scope)
```

## Blocking operations

Every single step inside `analyze_report()` is synchronous/blocking: file read, regex
extraction, two DB round-trips for the duplicate check, the VirusTotal HTTP call(s), risk
calculation, and the final save+reload. None of it is `async`. The entire reason a
`QThread` exists at all is to keep this blocking chain off the GUI thread — there is no
finer-grained concurrency inside the worker.

## Long-running operations

The threat-intelligence enrichment step (`ThreatIntelService.enrich_results`) is the only
step with genuinely variable, externally-bounded latency (network + third-party rate
limiting). Everything else is local and comparatively fast.

## Cancellation points

**None exist.** This is a confirmed, not inferred, fact — `AnalysisWorker.run()` polls no
interruption flag anywhere in its body, and `AnalyzePage.cleanup()`'s own docstring states
this explicitly: `quit()` only stops the `QThread` event loop from accepting new queued
calls, it has zero effect on a `run()` invocation already in progress. The `wait(5000)` in
`cleanup()` is a **grace period for shutdown logging only**, not a cancellation mechanism —
if analysis is still running after 5 seconds, `cleanup()` returns anyway and the thread
keeps running unsupervised in the background (safe only because it is deliberately never
parented to the page, so Qt's child-cleanup can't destroy a live thread out from under it).

The dialog's "Dismiss" button (`_on_progress_dialog_dismissed`) reinforces this: it is
explicitly documented as *not* a cancel button — it only hides the dialog while the analysis
keeps running and will still fire its finished/failed callbacks whenever it actually
completes.

## Error boundaries

One boundary: the `try/except Exception` wrapping the entire body of `AnalysisWorker.run()`
after `started.emit()`. Everything raised anywhere in the `analyze_report()` call chain is
caught here, logged with full traceback (a deliberate fix — the comment notes failures were
previously only ever visible as a bare `str(error)`), and converted to a `failed(str(error))`
signal. There is no finer-grained error boundary per pipeline stage (e.g. a TI failure vs. a
DB failure are not distinguished at this layer) — but `analyze_report()` itself does have an
internal boundary specifically around threat-intel: `MissingAPIKeyError` and any other TI
exception are caught *inside* `analyze_report`, degrade `threat_intelligence` to an
`"unavailable"` status, and do **not** abort the overall command — analysis still proceeds
to scoring and save. So TI failure is non-fatal by design; everything else (file read,
extraction, DB errors, scoring errors) is fatal to the whole command.

## Progress reporting

A single `progress_changed(int, str)` signal, driven by an optional `progress_callback`
parameter threaded all the way from `AnalysisWorker.run()` through `AnalyzeController.
analyze()` through `AnalysisService.analyze()` into `analyze_report()`, which calls it
directly (not via Qt signal — it's a plain `Callable[[int, str], None]`) at 6 fixed
checkpoints: 10/25/40/60/80/90/100%. This is a synchronous callback invoked on the worker
thread; `AnalysisWorker` re-exposes it as a genuine Qt signal
(`self.progress_changed.emit`) so the GUI thread receives it safely across the thread
boundary via Qt's queued-connection mechanism.

## Retry behavior

None observed anywhere in this chain. A failed VirusTotal call is not retried by
`analyze_report()` itself (any retry logic, if it exists, would live inside
`ThreatIntelService`/`VirusTotalClient`, which are outside this phase's stated file list and
were not read).

## Database writes

Exactly one write path in the whole workflow: `InvestigationRepository.save()`, reached only
when no duplicate investigation exists for the report name. Per `DatabaseConnection`'s
verified connection-per-operation pattern (see `PHASE4B_ARCHITECTURAL_FINDINGS.md`), this
write opens and closes its own SQLite connection independently of the two reads that precede
it (`exists_by_report_name`, and the duplicate-path `find_by_report_name`) and the one that
follows it (`get_by_id` reload) — there is no single transaction spanning the whole
"check-then-write-then-reload" sequence. WAL mode plus a lack of `busy_timeout` (also noted
in the Architectural Findings) means a concurrent GUI-thread read during this write is very
unlikely to block, but is not proven immune to `sqlite3.OperationalError: database is
locked` under contention, since no `busy_timeout` pragma was found.

## Thread ownership

- **GUI thread:** owns `AnalyzePage`, the `QThread` object itself (constructed there), and
  all signal *reception* (progress dialog updates, final result handling).
- **Worker thread:** owns exactly one `AnalysisWorker` instance for exactly one run (enforced
  by the `_has_run` guard), and executes the entire `analyze_report()` call chain
  synchronously on that thread, including the blocking DB and network calls.
- **Deliberately thread-agnostic:** the `QThread` object is never parented to `AnalyzePage`,
  specifically so that if `AnalyzePage` itself is torn down while analysis is still running,
  Qt's parent-child destruction can't try to destroy a live thread (a documented Qt fatal
  error: "QThread: Destroyed while thread is still running"). Lifetime is instead governed
  purely by the `finished -> deleteLater` signal chain.

## What must become an application-layer background job (Phase 4C+ concern, not built here)

Per the phase brief, only documenting this, not implementing it:

1. The lack of any cancellation mechanism is a real gap that a future job system should
   address (a job queue with a cooperative cancellation flag, rather than Qt's coarse
   `QThread.quit()`).
2. The lack of a transaction spanning "check duplicate → save → reload" is a latent race
   condition if the target architecture ever allows concurrent analysis requests (e.g. two
   API calls analyzing the same report name at once) — currently masked because the GUI only
   ever runs one `AnalysisWorker` at a time (enforced by `AnalyzePage._start_analysis`'s
   `if self._thread is not None and self._thread.isRunning(): return` guard).
3. Progress reporting's 6 fixed checkpoints (not evenly spaced, not derived from actual
   sub-task timing) is a reasonable UX heuristic today but should probably become real
   per-stage events (`analysis.progress` with a `stage` field, as already sketched in
   `06-event-architecture.md`'s target event shape) rather than a bare percentage.
