# Phase 4C — Exit Criteria

**Status: PHASE 4C COMPLETE — AUDITED, VERIFIED, DOCUMENTED, AND FROZEN.**

This document records what was actually implemented, verified, and (in Stage 3) corrected
across Phase 4C's three delivery stages, against the criteria set by
`docs/phase4/PHASE4C_THREAT_INTEL_ARCHITECTURE.md` (the authoritative design document for
this phase, hereafter "the design doc"). It follows the same convention as
`docs/migration/PHASE4B_EXIT_CRITERIA.md`: a checklist with evidence, not a narrative
retelling.

## Stage summary

- **Stage 1 — Provider Abstraction Foundation.** `app/threat_intel/{models,provider,
  virustotal_provider}.py` created; `ThreatIntelProvider` protocol, `IOC`/`IOCType`/
  `Verdict`/`ProviderResult` models, `aggregate()`, and `VirusTotalProvider` (wrapping
  `VirusTotalClient` unmodified). Nothing wired into `ThreatIntelService` or any consumer
  yet — by design (design doc §3).
- **Stage 2 — Consumer Migration.** `ThreatIntelService` migrated to depend on
  `list[ThreatIntelProvider]` instead of a bare `VirusTotalClient`; the one direct-instantiation
  GUI consumer (`app/gui/pages/threat_intel_page.py`) migrated to go through
  `ThreatIntelService` instead of constructing `VirusTotalClient` itself.
- **Stage 3 — Adversarial Audit, Defect Fix, Documentation, Freeze.** Full re-audit against
  the design doc found one genuine, unfixed Phase 4C defect surviving Stage 2 (below), fixed
  it, added regression coverage, verified zero test regressions, and produced this document
  plus the frozen checkpoint.

## Exit-criteria checklist

| Criterion | Evidence | PASS/FAIL |
|---|---|---|
| `ThreatIntelProvider` protocol exists, provider-neutral (design doc §4) | `app/threat_intel/provider.py`; structural `Protocol`, `runtime_checkable`; covered by `tests/test_threat_intel_provider_contract.py` | PASS |
| `Verdict` model with all 9 members incl. `NOT_FOUND` as distinct from `CLEAN` (design doc §5) | `app/threat_intel/models.py::Verdict`; `tests/test_threat_intel_models.py::TestLegacyVerdictStrings` | PASS |
| `ProviderResult` model (design doc §6) | `app/threat_intel/models.py::ProviderResult`; exercised throughout `tests/test_virustotal_provider.py` | PASS |
| `aggregate()` N-provider policy, testable independently of any provider (design doc §9) | `app/threat_intel/models.py::aggregate()`; `tests/test_threat_intel_models.py::TestAggregate*` (16 tests covering single-provider, empty-input, content precedence, absence precedence) | PASS |
| `VirusTotalProvider` adapter wraps `VirusTotalClient` via composition, unmodified client (design doc §13.1) | `app/threat_intel/virustotal_provider.py`; `VirusTotalClient`'s 77 tests in `tests/test_virustotal.py` required zero changes across all three stages | PASS |
| Sync-to-async bridge via `asyncio.to_thread`, option (a) (design doc §13.2) | `VirusTotalProvider._dispatch()` uses `asyncio.to_thread` for every `VirusTotalClient.lookup_*` call | PASS |
| `ThreatIntelService` depends on `ThreatIntelProvider`, not `VirusTotalClient` directly (design doc §13.3) | `app/threat_intel/service.py::ThreatIntelService.__init__` stores `self._providers: list[ThreatIntelProvider]`; no `self._virustotal: VirusTotalClient` attribute exists | PASS |
| `enrich_results` signature/dict-in-dict-out shape preserved for `analyzer.py` (design doc §14) | `app/analyzer.py:138` unchanged (`with ThreatIntelService() as service: service.enrich_results(...)`); `tests/test_threat_intel.py` exercises the same dict shape | PASS |
| `"Malicious"`/`"Suspicious"`/`"Clean"` legacy strings preserved exactly; `"Not Found"` added as new, distinct string (design doc §5/§14) | `app/threat_intel/service.py::_format_verdict`; `tests/test_threat_intel_models.py::TestLegacyVerdictStrings::test_legacy_strings_preserved_exactly` (Stage 1, `ProviderResult` path) and `tests/test_threat_intel.py::test_threat_intel_service_not_found_is_not_clean` / `test_lookup_indicator_not_found_is_not_clean` (Stage 3, the actual `ThreatIntelService` path every real consumer uses) | PASS |
| `NOT_FOUND` structurally distinct from `CLEAN`, checked before count-based branching (design doc §12 — "the central requirement of this phase") | See **Stage 3 defect and fix**, below. Fixed in `ThreatIntelService._format_verdict`; `VirusTotalProvider._translate` already did this correctly since Stage 1. Both paths now verified by test. | PASS (fixed in Stage 3 — see below) |
| GUI/application consumers do not directly depend on `VirusTotalClient` (design doc §1, §14 note re: `threat_intel_page.py`) | `app/gui/pages/threat_intel_page.py` imports only `app.threat_intel.service.ThreatIntelService`; grep audit found zero remaining `VirusTotalClient` instantiation outside `virustotal_provider.py` | PASS |
| Provider-neutral error boundary: VT-specific exceptions do not leak where design prohibits (design doc §10) | `VirusTotalProvider.lookup()` translates every VT exception into an error-shaped `ProviderResult`; validation errors re-raise per design doc §10's explicit call-site-bug carve-out; `ThreatIntelService.lookup_raw()`/`enrich_results` legacy path deliberately keeps VT-named exceptions (see Stage 3 audit note on this — reviewed, not a defect) | PASS |
| Existing 542-test-equivalent baseline stays green throughout (design doc §15.3) | See **Fresh test results**, below — zero regressions across all three stages | PASS |
| No second provider implemented this phase (design doc §3, §18) | grep confirms only `VirusTotalProvider` exists; no `AbuseIPDBProvider`/`OTXProvider`/etc. | PASS |
| VirusTotal-specific implementation isolated behind `VirusTotalProvider` (design doc §4) | Only instantiation site for `VirusTotalClient()` in `app/` is `virustotal_provider.py:151` (grep-verified) | PASS |

## Stage 3 defect and fix

**What was found:** Stage 2 preserved `ThreatIntelService._format_verdict` byte-for-byte to
keep `enrich_results`'/`lookup_indicator`'s legacy raw-dict output shape intact (malicious/
suspicious/harmless/undetected/reputation/last_analysis_date/permalink, none of which
`ProviderResult` can carry losslessly — design doc §6's flagged UNKNOWN). Byte-for-byte
preservation of `_format_verdict` also preserved its bug: it never reads `found`, so a
not-found result (`malicious=0, suspicious=0, total=0`) fell through to `verdict = "Clean"` —
exactly the defect design doc §2.2/§12 describes as "the central requirement of this phase"
to fix. `VirusTotalProvider.lookup()` (the `ProviderResult` path, added in Stage 1) already
implemented the correct structural fix — but nothing in production calls that path;
`analyzer.py` and the GUI page both go through `ThreatIntelService.enrich_results`/
`lookup_indicator`, which use `VirusTotalProvider.lookup_raw()` (the legacy-shape escape
hatch) specifically to avoid that lossy translation. The fix therefore needed to land in
`_format_verdict` itself, not just in the already-correct `ProviderResult` path.

**Fix:** `_format_verdict` now reads `result.get("found", True)` first and short-circuits to
`verdict = "Not Found"` before any malicious/suspicious/clean branching — matching design doc
§12's required structure ("read as an explicit, first-class signal before any count-based
logic runs"). The `True` default only affects pre-existing test doubles
(`FakeVirusTotalClient` in `tests/test_threat_intel.py`) that never populated `found` at all
and were exercising the malicious/suspicious/clean branches, not the found/not-found one —
every real `VirusTotalClient`/`VirusTotalProvider.lookup_raw()` result always includes
`found` (confirmed in `virustotal.py`'s eight response-building methods), so this default
never masks a real not-found response.

**Regression tests added** (`tests/test_threat_intel.py`, 6 new tests):
- `test_threat_intel_service_not_found_is_not_clean` — `enrich_results` path.
- `test_threat_intel_service_found_and_zero_counts_is_still_clean` — confirms the fix
  distinguishes not-found from a genuine found-and-clean zero-count result, not just
  relabels every zero-count case.
- `test_lookup_indicator_returns_legacy_shape_for_each_type` — the GUI-facing method,
  previously only ever exercised via `MagicMock()` in the GUI test file, never against its
  real implementation.
- `test_lookup_indicator_not_found_is_not_clean` — same fix, GUI-facing path.
- `test_lookup_indicator_invalid_type_raises_value_error`
- `test_lookup_indicator_propagates_errors_unlike_enrich_results`

**Downstream impact reviewed (design doc §12's own "downstream propagation requirement"):**
`ioc_details_widget.py::_VERDICT_COLORS` already defaults an unrecognized verdict string to
neutral gray (confirmed safe by construction, no change needed — matches design doc's own
prediction). `risk_explanation_service.py` and `correlation_service.py` only exact-match on
`"Malicious"`/`"Suspicious"`, so `"Not Found"` passes through inertly, same as before. No
crashes, no misclassification. `tests/test_correlation_service.py` (53 tests) and
`tests/test_risk_explanation_service.py` re-run clean after the fix.

## Fresh test results (Stage 3, this checkpoint)

```
python3 -m pytest tests/test_threat_intel_provider_contract.py tests/test_threat_intel.py \
  tests/test_threat_intel_models.py tests/test_virustotal.py tests/test_virustotal_provider.py \
  tests/test_investigation_threat_intel_overview.py -q
189 passed

python3 -m pytest tests/ -q --ignore=tests/gui
481 passed

QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ -q
635 passed
```

Baseline immediately before this stage (Part 2 checkpoint, re-run fresh, not merely
recalled): 183 / 475 / 629 respectively. The +6 delta in every figure is exactly the 6 new
regression tests above; no other count changed. Zero failures, zero regressions, at any
point across Stage 1 → Stage 2 → Stage 3.

## Known, reviewed non-defects (not fixed — reasoning recorded so a future agent doesn't
re-litigate these)

- **`_format_verdict`'s malicious/suspicious/clean/not-found logic is duplicated** between
  `ThreatIntelService._format_verdict` (str-keyed legacy dict) and
  `VirusTotalProvider._translate` (`Verdict` enum). Both are independently tested. Unifying
  them would require a shared primitive spanning two incompatible output shapes (legacy dict
  vs. `ProviderResult`), which is more abstraction than four lines of trivial precedence logic
  justifies, and risks the "do not redesign the architecture" scope lock from Part 2. Left as
  reviewed, accepted duplication.
- **`ThreatIntelService.enrich_results`/`lookup_raw` catch VT-specific exception names**
  (`InvalidHashError`, `RateLimitExceededError`, etc.) rather than their provider-neutral
  bases (`ProviderValidationError`, `ProviderRateLimitError`, etc.), even though both would
  catch identically (multiple inheritance, `exceptions.py`). This is intentional: `_lookup_raw`/
  `enrich_results` are inherently VT-only legacy-shaped surfaces in Phase 4C (only one
  provider exists; the design doc's own §1 already documents this pattern as a known,
  pre-existing characteristic, not a Stage 2/3 regression). Not a leakage bug.
- **Instructions in the Part 3 task brief reference `tests/test_threat_intel_provider.py`**;
  the actual file (created Stage 1, referenced by every subsequent stage's own report) is
  `tests/test_threat_intel_provider_contract.py`. Naming inaccuracy in the instructions, not
  a missing-file gap — confirmed by running the actual file (2/2 passed) and cross-checking
  against Part 1/Part 2's own reports, which both cite the `_contract` filename.
