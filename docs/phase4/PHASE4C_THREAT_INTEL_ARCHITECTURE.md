# Phase 4C — Threat Intelligence Provider Abstraction & Verdict Model

**Status:** Documentation Foundation (Phase 4C, Step 2). No source code has been changed to
produce this document.
**Related:** `docs/architecture/PHASE4_NEXT_GENERATION_ARCHITECTURE_MASTER_PLAN.md` §5, §26
(4C row), §30.F; `docs/adr/ADR-007-multi-provider-ti-abstraction.md`;
`docs/architecture/08-threat-intelligence-architecture.md`;
`docs/security/threat-model.md`; `docs/migration/PHASE4B_LOGIC_PRESERVATION_MATRIX.md`
(Threat intelligence section); `docs/migration/PHASE4B_EXIT_CRITERIA.md`.

**Method note:** every CONFIRMED statement below was verified this phase by direct reads of
`app/threat_intel/service.py`, `app/threat_intel/virustotal.py`, `app/threat_intel/__init__.py`,
`app/threat_intel/exceptions.py`, `app/settings/{models,service,repository}.py`, `app/config.py`,
`app/analyzer.py`, `app/extractor.py`, `app/scoring/engine.py`, `app/database/{models,repository}.py`,
`app/services/{correlation_service,risk_explanation_service}.py`, `app/exporters.py`,
`app/gui/pages/threat_intel_page.py`, `app/gui/widgets/{ioc_details_widget,threat_intelligence_widget,
ioc_detail_dialog}.py`, `tests/test_threat_intel.py`, and `tests/test_virustotal.py`. Where the
Phase 4A/4B documents already stated something consistent with source, that document is cited
alongside the source confirmation rather than re-deriving it from scratch. Where source
contradicts or adds detail beyond an older doc, source wins and the discrepancy is called out
explicitly.

---

## 1. Current VirusTotal Architecture (CONFIRMED)

Three layers exist today, all VirusTotal-specific:

1. **`VirusTotalClient`** (`app/threat_intel/virustotal.py`, 1,190 lines) — a synchronous
   `requests`-based HTTP client for the VirusTotal v3 API. Owns:
   - Per-IOC-type input validation (`_validate_sha256`, `_validate_ip`, `_validate_domain`,
     `_validate_url`) — each raises a dedicated `Invalid*Error` before any network call.
   - Four public lookup methods: `lookup_sha256`, `lookup_ip`, `lookup_domain`, `lookup_url`.
     Each performs one GET request, then branches on HTTP status: `200` → parse and return a
     normalized dict; `404` → return a normalized "not found" dict (see §12); `401`/`403` →
     raise `InvalidAPIKeyError`; `429` → raise `RateLimitExceededError`; `>=500` or anything
     else unexpected → raise `UnexpectedAPIResponseError`. Network-level failures
     (`requests.exceptions.Timeout` / `ConnectionError` / other `RequestException`) are caught
     in a shared `_request()` helper and re-raised as `ThreatIntelTimeoutError` /
     `ThreatIntelConnectionError`.
   - Response parsing/validation (`_extract_attributes_and_stats`, four
     `_parse_success_*_response` methods, four `_build_not_found_*_response` methods) that
     normalizes VT's `data.attributes.last_analysis_stats` shape into a flat dict with keys
     `malicious`, `suspicious`, `harmless`, `undetected`, `reputation`, `last_analysis_date`,
     `permalink`, a type-specific identity field (`sha256`/`ip`/`domain`/`url` (+`url_id`)),
     and — critically — a boolean **`found`** field (`True` on `200`, `False` on `404`).
   - API key resolution via `SettingsService().load_settings().virustotal_api_key` (or an
     injected `api_key` for tests), raising `MissingAPIKeyError` if absent.
   - Session lifecycle: owns a `requests.Session` unless one is injected; `close()` /
     context-manager protocol / a `__del__` safety net that warns and closes if the caller
     never did.

2. **`ThreatIntelService`** (`app/threat_intel/service.py`, 466 lines) — the orchestrator
   `analyzer.py` actually calls. Takes an **optional `VirusTotalClient`** as its *only*
   injectable dependency (constructor: `virustotal: VirusTotalClient | None = None`). Its
   single public entry point, `enrich_results(results: dict) -> dict`, pulls four IOC lists
   out of the extractor's output dict (`SHA256`/`sha256`, `ipv4`/`IPV4`/`ips`,
   `domains`/`DOMAINS`/`domain`, `urls`/`URLS`/`url` — tolerant of multiple extractor key
   spellings), loops each category through the matching `VirusTotalClient.lookup_*` call,
   catches the client's typed exceptions per-item, and returns a dict shaped
   `{"hashes": [...], "ips": [...], "domains": [...], "urls": [...], "status": str,
   "coverage": {...}}`.
   - `_format_verdict(result)` (static method) is the **verdict computation**: it reads
     `malicious`/`suspicious`/`harmless`/`undetected` (defaulting missing/`None` to `0`),
     computes `total = malicious + suspicious + harmless + undetected`, and sets
     `result["verdict"]` to `"Malicious"` if `malicious > 0`, else `"Suspicious"` if
     `suspicious > 0`, else `"Clean"`. It also sets `result["detection_ratio"]` to
     `f"{malicious}/{total}"` (or `"N/A"` if `total == 0`).
   - Coverage/status bookkeeping: `succeeded`/`failed`/`skipped_invalid` counters,
     `rate_limited`/`invalid_api_key` flags that — once set — stop processing *all remaining
     categories* (not just the rest of the current one) and count every unprocessed item as
     `failed`. Overall `status` is `"no_indicators"` (nothing requested), `"partial"`
     (anything failed/rate-limited/invalid-key), or `"ok"`.
   - Four private single-category wrapper methods (`_enrich_sha256_hashes`, `_enrich_ips`,
     `_enrich_domains`, `_enrich_urls`) that each just call `enrich_results` with a single key
     and unpack one category back out — thin conveniences, not separately used elsewhere in
     the codebase (CONFIRMED via `grep`; no call sites found outside `service.py` itself).
   - Context-manager protocol (`__enter__`/`__exit__`) and `close()`, which delegates to
     `self._virustotal.close()`.

3. **Exceptions** (`app/threat_intel/exceptions.py`, 77 lines) — a flat hierarchy under
   `ThreatIntelError` → `VirusTotalError` → nine concrete exceptions
   (`MissingAPIKeyError`, `InvalidHashError`, `InvalidIPError`, `InvalidDomainError`,
   `InvalidURLError`, `InvalidAPIKeyError`, `RateLimitExceededError`,
   `ThreatIntelConnectionError`, `ThreatIntelTimeoutError`, `UnexpectedAPIResponseError`).
   Every exception is explicitly VirusTotal-flavored (`VirusTotalError` base), not
   provider-neutral — even though `ThreatIntelService`'s catch sites (which are meant to be
   the provider-agnostic layer) already import and catch them by these VT-specific names.

`app/threat_intel/__init__.py` is empty (CONFIRMED) — no re-exports, no package-level
surface.

**Caller:** `app/analyzer.py::analyze_report()` is the sole production call site
(`with ThreatIntelService() as service: threat_intelligence = service.enrich_results(extracted_iocs)`),
inside a `try`/`except MissingAPIKeyError` that degrades to a
`{"status": "unavailable", "reason": "no_api_key", ...}` shape rather than failing the whole
analysis. This matches `PHASE4B_THREADING_WORKFLOW_ANALYSIS.md`'s description of this as the
one internal error boundary explicitly built around threat intel.

**Second, independent call path (CONFIRMED, previously undocumented in the Phase 4A/4B
docs):** `app/gui/pages/threat_intel_page.py` constructs a `VirusTotalClient` **directly**,
bypassing `ThreatIntelService` entirely, for its single-IOC ad-hoc lookup search box. This
path already checks `result.get("found", False)` correctly (see §3) and is worth naming
explicitly because it proves the raw building block for `NOT_FOUND` has existed all along —
the defect is specifically that the *main enrichment pipeline* (`ThreatIntelService`) never
uses it.

---

## 2. Confirmed Architectural Limitations

1. **No provider abstraction (CONFIRMED).** `ThreatIntelService.__init__` takes one concrete
   client type (`VirusTotalClient | None`), not a protocol or a list of providers. Adding
   AbuseIPDB or OTX today would require either a second constructor parameter with
   copy-pasted per-category loop logic, or reshaping AbuseIPDB/OTX responses to imitate VT's
   dict shape inside `ThreatIntelService` itself — both are exactly the "provider-specific
   logic leaking into orchestration" problem ADR-007 and Master Plan §1.5 describe, confirmed
   again here by direct re-read.

2. **`NOT_FOUND` is silently collapsed into `CLEAN` (CONFIRMED — the load-bearing defect).**
   `VirusTotalClient.lookup_*` already computes and returns `found: bool` per call (`True` on
   HTTP 200, `False` on HTTP 404 with all four stat counters zeroed — see the four
   `_build_not_found_*_response` methods). But `ThreatIntelService._format_verdict` **never
   reads the `found` key** — it is not referenced anywhere in `service.py`. Verdict is derived
   purely from `malicious > 0` / `suspicious > 0` / else `"Clean"`. Since a not-found response
   has `malicious == suspicious == 0` by construction, every not-found IOC that passes through
   the main enrichment pipeline is labeled `"Clean"` — indistinguishable, downstream, from an
   IOC VirusTotal actually checked and found harmless. This is exactly the false-assurance
   scenario ADR-007 and `docs/security/threat-model.md` warn about, and it is not hypothetical:
   it is what the current code does today, every time a queried indicator has no VT record.
   - **Confirmed by an existing behavioral asymmetry, not just by reading the code**: the
     ad-hoc lookup page (`threat_intel_page.py`, §1) reads `result.get("found", False)` off
     the *exact same* `VirusTotalClient` return shape and correctly shows "Status: Not found
     in VirusTotal." The information is present on the object; `ThreatIntelService` simply
     discards it. Fixing this is squarely a `ThreatIntelService`/verdict-model problem, not a
     `VirusTotalClient` problem — `VirusTotalClient`'s output already carries what's needed.

3. **No test currently exercises "not found" through the enrichment/verdict pipeline
   (CONFIRMED — a real coverage gap, not merely a design gap).** `tests/test_virustotal.py`
   has four dedicated tests confirming `found is False` at the *client* level (`
   test_not_found_returns_normalized_zeroed_result`, `test_ip_not_found_...`,
   `test_domain_not_found_...`, `test_url_not_found_...`). But every one of the 20 tests in
   `tests/test_threat_intel.py` uses a hand-written `FakeVirusTotalClient` (and its
   subclasses) whose `lookup_*` methods **never include a `found` key at all** in their
   returned dicts — meaning `_format_verdict`'s failure to read `found` has never been
   exercised by a test that could catch it. `test_threat_intel_service_clean_verdict` tests a
   *found-and-clean* case (`malicious=0, suspicious=0, harmless=80, undetected=5`, i.e.
   `found` would be `True` in real traffic) — it does not, and was never intended to, cover
   the not-found case. This gap is flagged again in §15 (Testing Strategy) as the first new
   test that must exist before any refactor is considered done.

4. **Exception hierarchy is VirusTotal-named at every level (CONFIRMED).** All nine concrete
   exceptions derive from `VirusTotalError`, and `ThreatIntelService`'s per-item `except`
   clauses catch them by those VT-specific names. A second provider's connection failure would
   either have to be shoehorned into raising a `VirusTotalError` subclass (semantically wrong)
   or `ThreatIntelService` would need parallel catch blocks per provider (defeats the point of
   an abstraction).

5. **Only 4 of 10 extracted IOC categories are ever enriched (CONFIRMED, previously
   undocumented).** `app/extractor.py::IOC_PATTERNS` extracts ten categories: `ipv4`,
   `domains`, `urls`, `emails`, `md5`, `sha1`, `sha256`, `cves`, `windows_file_paths`,
   `windows_registry_keys`. `ThreatIntelService.enrich_results` only ever looks at four of
   them (`SHA256`/`sha256`, `ipv4`, `domains`, `urls`); `emails`, `md5`, `sha1`, `cves`,
   `windows_file_paths`, and `windows_registry_keys` are extracted and scored
   (`RiskScoringEngine.IOC_WEIGHTS` has entries for all ten) but never sent to VirusTotal at
   all. This is not itself a defect Phase 4C is required to fix (VirusTotal's actual API does
   not meaningfully support Windows-path/registry-key lookups), but it **is** a fact the
   `IOCType` model (§8) needs to represent correctly: "extracted" and "enrichable" are not the
   same set, and the target model must not silently imply otherwise.

6. **Aggregation policy does not exist yet, and cannot be tested yet (CONFIRMED absence).**
   With exactly one provider, there is nothing to aggregate. Master Plan §5.3's proposed
   policy is real design work, not yet implemented, and not exercised by any existing test.

7. **`_enrich_sha256_hashes` / `_enrich_ips` / `_enrich_domains` / `_enrich_urls` are dead
   convenience wrappers (CONFIRMED via `grep`).** No call site outside `service.py` uses them.
   They are candidates for removal during the refactor (§10) since they add surface area
   without current callers, but are not a correctness problem today.

---

## 3. Target Provider Abstraction (PROPOSED)

Adopting the shape already agreed in ADR-007 / Master Plan §5.1, confirmed here as the
Phase 4C target rather than re-derived independently:

- A `ThreatIntelProvider` protocol (§4) that every provider adapter implements, including a
  `VirusTotalProvider` that wraps the **preserved, unmodified** HTTP/parsing logic currently
  in `virustotal.py`.
- `ThreatIntelService` refactored from "holds one `VirusTotalClient`" to "holds
  `list[ThreatIntelProvider]`" — becoming a true orchestrator: for each IOC, call every
  provider that supports that IOC's type and is configured, collect their `ProviderResult`s,
  and hand the list to the aggregation policy (§9) to produce one display verdict.
- The **VirusTotal adapter is the only provider registered in Phase 4C.** No second provider
  is implemented this phase (Master Plan §30.F, explicit "do not do this yet" rule; ADR-007
  Alternatives Considered).

---

## 4. `ThreatIntelProvider` Contract (PROPOSED)

```python
from typing import Protocol

class ThreatIntelProvider(Protocol):
    name: str                          # "virustotal", "abuseipdb", "otx", ...
    supported_ioc_types: set[IOCType]  # which IOC types this provider can look up

    async def lookup(self, ioc: IOC) -> ProviderResult:
        """
        Look up a single IOC against this provider.

        MUST NOT raise for "not found" -- that is a normal, expected
        outcome represented as Verdict.NOT_FOUND in the returned
        ProviderResult, not an exception. MAY raise a
        ThreatIntelError subclass for genuine failures (timeout,
        connection error, rate limit, invalid/missing key,
        malformed provider response) which the orchestrator is
        responsible for catching and translating into an
        error-shaped ProviderResult (see SS11) rather than letting
        propagate out of enrich_results().
        """
        ...

    def is_configured(self) -> bool:
        """
        Return True if this provider has everything it needs to
        attempt a lookup (e.g. an API key is present) without
        making a network call. ThreatIntelService uses this to
        skip unconfigured providers up front and reflect that in
        coverage/status, rather than attempting a lookup that is
        guaranteed to fail on a missing-key error.
        """
        ...
```

Design notes (PROPOSED, with rationale):

- **`async def lookup`**: matches Master Plan §5.1 verbatim. This is a real, deliberate change
  from `VirusTotalClient`'s current fully synchronous `requests`-based calls — see §13
  (Migration Strategy) for how that gap is bridged without an immediate full async rewrite.
- **`supported_ioc_types` as a `set[IOCType]`**, not a hardcoded four-category tuple: this is
  what lets `ThreatIntelService` route a given IOC to only the providers that can handle it
  (e.g. AbuseIPDB supports IPs but not file hashes) without provider-specific `if` branches in
  the orchestrator.
- **`is_configured()` is synchronous and cheap.** It exists so the orchestrator can compute
  `unsupported` / `no_api_key` verdicts (§8) without an actual network round-trip, and so a
  provider with no credentials configured is skipped rather than attempted-and-failed on every
  single IOC in an investigation.

---

## 5. Canonical `Verdict` Model (PROPOSED)

```python
from enum import Enum

class Verdict(str, Enum):
    MALICIOUS = "malicious"
    SUSPICIOUS = "suspicious"
    CLEAN = "clean"
    NOT_FOUND = "not_found"      # provider has no record -- explicitly NOT "clean"
    UNSUPPORTED = "unsupported"  # provider doesn't support this IOC type
    NO_API_KEY = "no_api_key"
    UNAVAILABLE = "unavailable"  # timeout / connection error
    RATE_LIMITED = "rate_limited"
    ERROR = "error"              # unexpected/malformed provider response
```

This is the load-bearing decision of the whole subsystem (ADR-007, Master Plan §5.2), carried
into this document unchanged because direct source reading this phase did not surface any
reason to deviate from it — if anything, §2.2 above is independent confirmation that the
distinction is necessary, not just theoretically tidy.

**Enforcement is structural, not conventional**: a provider adapter that receives an
HTTP-404-equivalent ("no record") from its upstream API **must** construct
`Verdict.NOT_FOUND`; there is no code path by which "not found" can produce `Verdict.CLEAN`,
because the two are different enum members set by different branches in the adapter, not by a
shared "compute from counts" function the way `_format_verdict` does today. This is the
specific mechanism that fixes the defect in §2.2: today's bug exists *because* verdict is
derived from detection counts alone; the fix is that `found`/`not-found` must be read as an
explicit, first-class signal before any count-based logic runs, and a not-found result must
short-circuit straight to `Verdict.NOT_FOUND` without ever reaching the malicious/suspicious/
clean branching at all.

**Legacy string compatibility (PROPOSED, new to this document — needed for §14/§16):** the
existing GUI, scoring narrative, and correlation-service code do **exact string matches**
against `"Malicious"` and `"Suspicious"` (CONFIRMED — see
`risk_explanation_service.py::_count_threat_intel_verdicts`,
`correlation_service.py::_correlate_threat_intel_links_for_category`,
`ioc_details_widget.py::_VERDICT_COLORS`). Any display-string mapping from the new `Verdict`
enum back to a legacy string **must** preserve `"Malicious"` and `"Suspicious"` exactly
(capitalized, singular) for backward compatibility with un-migrated consumers during the
transition window described in §14. `Verdict.CLEAN` should map to the existing `"Clean"`
string. `Verdict.NOT_FOUND` must map to a **new, distinct** string (e.g. `"Not Found"`) that
does not collide with any string those exact-match call sites already check for — the whole
point is that `record.get("verdict") == "Clean"` must NOT become true for a not-found record
under the new model, either.

---

## 6. `ProviderResult` Model (PROPOSED)

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class ProviderResult:
    provider: str                     # e.g. "virustotal"
    ioc: IOC
    verdict: Verdict
    confidence: float | None          # 0-1; None where the provider gives no confidence signal
    raw_detection_ratio: str | None   # e.g. "12/94" -- provider-specific, display-only
    source_url: str | None            # e.g. VT permalink
    queried_at: datetime
    error_detail: str | None = None   # populated when verdict is UNAVAILABLE/ERROR/RATE_LIMITED
```

Mapping from today's `VirusTotalClient` output (CONFIRMED fields on the left, PROPOSED
`ProviderResult` field on the right) — this is the concrete translation
`VirusTotalProvider.lookup()` performs, per §13:

| Current VT field | `ProviderResult` field | Notes |
|---|---|---|
| `found` | derives `verdict` (`NOT_FOUND` when `False`) | consumed, not carried forward verbatim |
| `malicious`, `suspicious`, `harmless`, `undetected` | derive `verdict` when `found is True` | same malicious→suspicious→clean precedence as today's `_format_verdict`, but only reachable once `found is True` |
| *(computed today in `_format_verdict`)* `detection_ratio` string | `raw_detection_ratio` | format preserved (`f"{malicious}/{total}"`, `"N/A"` if `total == 0`) |
| `reputation` | folds into `confidence` (PROPOSED normalization, see UNKNOWN below) | see §17 risk — reputation is an unbounded signed int on VT, not a 0-1 scale |
| `last_analysis_date` | *(no direct field — see UNKNOWN below)* | not represented in the `ProviderResult` shape as currently proposed |
| `permalink` | `source_url` | direct carry-over |
| `sha256`/`ip`/`domain`/`url` | `ioc` (the `IOC` passed into `lookup()`, echoed back) | identity no longer needs a per-type field name once `IOC` is a typed value |

**UNKNOWN (flag for implementation, not guessed here):** the master-plan `ProviderResult`
shape has no field for `last_analysis_date`, which every current GUI consumer (
`threat_intel_page.py`'s detail view, at minimum) displays today. Whether this becomes a new
`ProviderResult` field, is folded into `error_detail`-style metadata, or is intentionally
dropped as a Phase 4C-vs-4K display concern needs a decision during implementation — it is not
resolved by anything read this phase and should not be guessed at here.

---

## 7. IOC Type Support Model (CONFIRMED current state + PROPOSED target)

**Current (CONFIRMED):** four enrichable categories only — SHA256, IPv4, domain, URL — driven
implicitly by which `lookup_*` methods `VirusTotalClient` happens to implement, not by any
declared capability set. `ThreatIntelService.enrich_results` hardcodes exactly these four
categories in its extraction logic (§1). MD5, SHA1, email, CVE, Windows file path, and Windows
registry key IOCs are extracted (§2.5) but the enrichment pipeline has no branch for them at
all — they are simply absent from `threat_intelligence["hashes"/"ips"/"domains"/"urls"]`.

**Target (PROPOSED):** an `IOCType` enum (or reuse of a normalized string set already
implied by `app.config.IOC_TYPES`) that every provider declares support for via
`supported_ioc_types`. `ThreatIntelService` iterates IOCs by type and, for each IOC, calls
`.lookup()` only on providers whose `supported_ioc_types` includes that type. An IOC of a type
**no configured provider supports** (e.g. a Windows registry key, today and for the
foreseeable future) gets `Verdict.UNSUPPORTED` rather than being silently dropped from the
enrichment output the way it is today — this is a genuine behavior improvement over the
current silent-omission behavior, and should be called out as such rather than treated as
equivalent to today's behavior (see §14 compatibility strategy for how this interacts with
existing "not enriched" GUI states).

**Phase 4C scope note:** the *model* (declaring and checking `supported_ioc_types`) is in
scope. Adding a provider that actually supports MD5/SHA1/email/CVE lookups is not — VirusTotal
supports SHA256 file lookups already covers the file-hash case VT itself provides; MD5/SHA1
support for VT specifically is a separate, smaller follow-up (VT's `/files/{id}` endpoint
does accept MD5/SHA1 identifiers per VT's public documentation, **UNKNOWN whether SOC-IQ's
current `VirusTotalClient._validate_sha256`-only validation is an intentional narrowing or an
oversight** — not confirmed by source in this phase, since `virustotal.py`'s docstrings give
no rationale; worth a direct question before Phase 4C implementation decides whether
`VirusTotalProvider` should widen hash support beyond SHA256 or preserve the current
SHA256-only surface exactly).

---

## 8. Provider Configuration Model (PROPOSED)

- **Preserved:** VT's API key continues to live in `ApplicationSettings.virustotal_api_key`,
  loaded via `SettingsService`, with the existing redacted `__repr__` and atomic-write
  persistence in `SettingsRepository` (CONFIRMED — both mechanisms read this phase, both
  sound, no reason to change either in Phase 4C). Master Plan §22/ADR-008's OS-secure-storage
  work is explicitly a **later** phase (4M) — Phase 4C does not move the key off disk.
- **New (PROPOSED):** `ApplicationSettings` gains one field per future provider's credential
  as each provider is added (e.g. `abuseipdb_api_key: str = ""`), following the exact pattern
  `virustotal_api_key` already establishes — same redaction treatment, same atomic-write path.
  **Not added in Phase 4C** (no second provider exists yet), but the pattern is documented now
  so it isn't re-litigated when AbuseIPDB/OTX onboarding (§18) actually happens.
- **`VirusTotalProvider.is_configured()`** becomes `bool(self._api_key)` — a direct,
  synchronous translation of the existing `MissingAPIKeyError` check
  `VirusTotalClient.__init__` performs today, but checkable *before* attempting a lookup
  rather than discovered via an exception raised from inside the client constructor.

---

## 9. Provider Aggregation Policy (PROPOSED)

Per Master Plan §5.3, carried forward as the Phase 4C target (single-provider today, so the
policy is exercised in its degenerate one-provider form but must be written as a general
N-provider function from the start, testable independently of any one provider):

```
def aggregate(results: list[ProviderResult]) -> Verdict:
    if any(r.verdict is Verdict.MALICIOUS for r in results):
        return Verdict.MALICIOUS
    if any(r.verdict is Verdict.SUSPICIOUS for r in results):
        return Verdict.SUSPICIOUS
    if any(r.verdict is Verdict.CLEAN for r in results):
        return Verdict.CLEAN
    # No provider found a record and no provider positively asserted "clean" --
    # do NOT default to CLEAN here. This is the precise line NOT_FOUND != CLEAN
    # is protecting.
    if all(r.verdict is Verdict.NOT_FOUND for r in results):
        return Verdict.NOT_FOUND
    ...  # UNAVAILABLE / RATE_LIMITED / ERROR precedence -- see UNKNOWN below
```

**UNKNOWN (explicitly not decided by this document):** exact precedence among
`UNAVAILABLE`/`RATE_LIMITED`/`ERROR`/`UNSUPPORTED`/`NO_API_KEY` when they're mixed with each
other (e.g. one provider returns `NOT_FOUND` and another returns `UNAVAILABLE` — is the
aggregate `NOT_FOUND`, `UNAVAILABLE`, or a new composite state?). Master Plan §5.3 only spells
out the malicious/suspicious/clean/not_found chain in prose; the error-class precedence is
genuinely unresolved and must be decided — and unit-tested per Master Plan's own top-10 risk
#10 ("verdict-aggregation policy silently downgrading MALICIOUS to a lower severity due to a
provider bug") — during implementation, not guessed here.

**Single-provider degenerate case (this is what Phase 4C actually ships and tests):** with
exactly one `VirusTotalProvider` registered, `aggregate([single_result])` reduces to "return
that provider's verdict, unchanged." The policy function must still be a real, independently
callable unit under test in Phase 4C (Master Plan exit criterion: "new unit tests for verdict
policy") even though only its single-input behavior is exercised by production traffic this
phase — this is precisely so the function doesn't have to be written *and* first-tested
simultaneously with the first real second-provider addition.

---

## 10. Error Handling (CONFIRMED current + PROPOSED target)

**Current (CONFIRMED):** `ThreatIntelService.enrich_results` catches VT-specific exceptions
per-item inside each of its four near-identical loops (§1). Three outcomes per exception type:
`Invalid*Error` → skip this one item (`skipped_invalid += 1`), continue the loop;
`ThreatIntelTimeoutError`/`ThreatIntelConnectionError`/`UnexpectedAPIResponseError` → count as
`failed`, continue the loop; `RateLimitExceededError`/`InvalidAPIKeyError` → count all
*remaining* items across *all* categories as failed and **stop all further processing**
(`break` out of the current loop, and the `if not (rate_limited or invalid_api_key):` guard
skips every subsequent category's loop entirely).

**Target (PROPOSED):** the same three-tier behavior (skip-invalid / count-as-failed /
stop-everything) is preserved, but re-expressed against provider-neutral exceptions
(`ThreatIntelError` subclasses that are no longer named `VirusTotalError`) and against
per-provider results rather than per-client-call exceptions where possible — i.e. a provider
adapter's `lookup()` catching its own transport-level failures and returning an
`UNAVAILABLE`/`RATE_LIMITED`/`ERROR`-verdict `ProviderResult` with `error_detail` populated,
rather than the orchestrator needing to catch a raw exception for every failure mode. Genuine
input-validation failures (`Invalid*Error` equivalents) remain exceptions raised before any
network call, since those are call-site bugs (malformed IOC value), not provider-side
failures, and skipping them without ever attempting a network call is correct today and should
stay correct.

**Exception hierarchy (PROPOSED restructure):** introduce provider-neutral base exceptions
under `ThreatIntelError` (already exists as the root — CONFIRMED) — e.g.
`ProviderConnectionError`, `ProviderTimeoutError`, `ProviderRateLimitError`,
`ProviderAuthError`, `ProviderResponseError` — with today's `VirusTotalError` subclasses
either becoming aliases/subclasses of these (for the transition window, §14) or being retired
once `VirusTotalProvider` is the only caller that would otherwise raise them.

---

## 11. Timeout / Rate-Limit Semantics (CONFIRMED current + PROPOSED target)

**Current (CONFIRMED):**
- Timeout is a single float, `VIRUSTOTAL_TIMEOUT` (`app/config.py`, default `30` seconds,
  overridable via `VIRUSTOTAL_TIMEOUT` env var, validated `> 0` in
  `VirusTotalClient.__init__`), applied identically to every request via `requests.Session.get(
  ..., timeout=self._timeout)`. There is no per-request or per-IOC-type override.
- Rate limiting is **entirely reactive**: `VirusTotalClient` has no request budget, no
  backoff, no retry. It only recognizes rate limiting after VT responds with HTTP 429, at
  which point `ThreatIntelService` treats it as a hard stop for the rest of the current
  enrichment run (§10) — there is no wait-and-retry, no partial backoff, no per-provider
  rate budget tracked across calls.
- **CONFIRMED absence (per `PHASE4B_THREADING_WORKFLOW_ANALYSIS.md`, independently consistent
  with source read this phase):** no retry logic exists anywhere in this chain today. A failed
  VirusTotal call is not retried.

**Target (PROPOSED):** timeout remains a simple per-provider configuration value (each
provider adapter owns its own timeout setting, following VT's existing pattern) — Phase 4C
does not introduce retry/backoff logic; that is out of scope per the stated objective
("preserve existing VirusTotal behavior"). Rate-limit handling remains reactive
(HTTP 429 → `Verdict.RATE_LIMITED` on that `ProviderResult`, orchestrator applies the same
stop-remaining-work policy as today) rather than proactive, preserving current behavior
exactly rather than silently upgrading it — a proactive rate budget is a legitimate future
enhancement but is explicitly not bundled into this abstraction work.

---

## 12. `NOT_FOUND` vs `CLEAN` Semantics (CONFIRMED problem, PROPOSED fix — the central
requirement of this phase)

Restating and consolidating §2.2/§5 in one place, since this is called out as the single most
important requirement:

- **What "not found" means today, at the client level (CONFIRMED, correct):**
  `VirusTotalClient.lookup_*` receiving HTTP 404 means "VirusTotal has never analyzed this
  indicator" — no scan, no verdict, no data — and the client correctly encodes this as
  `found: False` with all four detection counters zeroed (not omitted — explicitly `0`, which
  matters for §2.2's bug: zeroed counters are indistinguishable from a genuinely-clean result
  once `found` is discarded).
- **What "clean" means today, at the client level (CONFIRMED, correct):** HTTP 200 with
  `malicious == 0 and suspicious == 0` (whether `harmless`/`undetected` are zero or not) means
  "VirusTotal scanned this and no engine flagged it" — a real, positive signal, fundamentally
  different in evidentiary weight from "we have no idea."
- **Where they get conflated today (CONFIRMED, the bug):** `ThreatIntelService._format_verdict`
  computes verdict from counts alone, never consulting `found`. A not-found result
  (`malicious=0, suspicious=0`, `total=0`) and a found-and-clean result with zero harmless/
  undetected counts would both hit the `else: verdict = "Clean"` branch — the *only* current
  differentiator between them downstream is `detection_ratio` being `"N/A"` (when `total == 0`)
  vs. a real ratio like `"0/85"`, which is not surfaced as a meaningfully different verdict
  anywhere in scoring, correlation, or the verdict-color-coded GUI widgets (all of which key
  off the `verdict` string, not `detection_ratio`).
- **The fix (PROPOSED, per §5):** `Verdict.NOT_FOUND` is a distinct enum member, set directly
  from a provider adapter's own "no record" signal (VT's `found is False` / HTTP 404) **before**
  any malicious/suspicious/clean branching is even reached — not derived from counts at all.
  This makes the conflation structurally impossible rather than merely "fixed for now" the way
  a one-off `if not found: verdict = "not_found"` patch inside the *existing* `_format_verdict`
  would be (such a patch was explicitly considered and rejected as the approach here, since it
  would fix today's VT-only bug without building the reusable, provider-neutral mechanism the
  rest of this document specifies).
- **Downstream propagation requirement (PROPOSED, new to this document):** every consumer that
  currently branches on the `verdict` string — `RiskScoringEngine` (does NOT currently branch
  on the string; scores raw counts, so it is naturally unaffected — CONFIRMED, see §2 in
  `scoring/engine.py`), `risk_explanation_service.py`'s malicious/suspicious counting,
  `correlation_service.py`'s narrative text, and the three GUI verdict-rendering widgets
  (`ioc_details_widget.py`, `threat_intelligence_widget.py`, `ioc_detail_dialog.py`) — must be
  re-audited once the new verdict value exists, specifically to confirm none of them treats an
  *unrecognized* verdict string as equivalent to `"Clean"` by virtue of falling through a
  default branch. Direct confirmation this phase: `ioc_details_widget.py::_VERDICT_COLORS`
  already defaults an unrecognized verdict to a neutral disabled-gray color (not the "Clean"
  green) — this specific widget is safe by construction today and needs no change for basic
  correctness, though its color map should eventually gain an explicit `"Not Found"` entry
  (Master Plan §11's semantic-color-mapping note) as a presentation improvement, not a
  correctness fix. The other two GUI widgets and `risk_explanation_service.py`/
  `correlation_service.py`'s exact-string checks are unaffected in the sense that they won't
  crash or misclassify a not-found verdict as malicious/suspicious — but they also won't do
  anything *useful* with a new `"Not Found"` value without deliberate updates, which is
  legitimate follow-on GUI work, not a Phase 4C blocker (Phase 4C's stated objective is the
  provider/verdict architecture, not a GUI redesign — see §13's compatibility strategy for what
  Phase 4C's `enrich_results` output must guarantee in the meantime).

---

## 13. VirusTotal Migration Strategy (PROPOSED)

1. **Preserve `virustotal.py`'s HTTP/parsing logic almost verbatim** (Master Plan §5.4,
   confirmed as the right call by this phase's read — the validation, request, and
   response-parsing logic is already well-factored, has 77 passing tests, and has no
   VT-shape-specific logic that would need to change to satisfy the new interface). The
   change is at the **boundary**: instead of `lookup_sha256`/`lookup_ip`/`lookup_domain`/
   `lookup_url` being called directly by `ThreatIntelService`, a new `VirusTotalProvider`
   class wraps a `VirusTotalClient` instance (composition, not inheritance — keeps
   `VirusTotalClient` a plain, still-independently-testable HTTP client) and its single
   `lookup(ioc: IOC) -> ProviderResult` method dispatches to the correct
   `self._client.lookup_*` method based on `ioc.type`, then translates that method's existing
   return dict into a `ProviderResult` per the mapping table in §6.
2. **Sync-to-async bridge (PROPOSED, concrete open question for implementation, not resolved
   here):** `ThreatIntelProvider.lookup` is `async def` (§4), but `VirusTotalClient` is built
   on synchronous `requests`. Two realistic options, neither chosen by this document:
   (a) wrap each synchronous call in `asyncio.to_thread(...)` inside `VirusTotalProvider.lookup`,
   keeping `VirusTotalClient` completely unchanged; or (b) migrate `VirusTotalClient` itself to
   `httpx.AsyncClient`. Option (a) is lower-risk for Phase 4C specifically (zero changes to
   77-test-covered code, "preserve existing VirusTotal behavior" satisfied literally), but this
   is flagged as a decision for implementation planning, not settled here.
3. **`ThreatIntelService` becomes the orchestrator** described in §3/§9: constructed with
   `providers: list[ThreatIntelProvider] | None = None`, defaulting to
   `[VirusTotalProvider()]` when not injected (mirroring today's
   `virustotal: VirusTotalClient | None = None` default-construction pattern exactly, so
   existing call sites that do `ThreatIntelService()` with no arguments keep working
   unchanged).
4. **Exceptions migrate per §10** — `VirusTotalError` subclasses either become aliases of new
   provider-neutral exceptions or are retired, per whatever the transition window in §14
   requires.

---

## 14. Compatibility Strategy (PROPOSED)

The stated Phase 4C objective is "introduce a genuinely provider-agnostic architecture *while
preserving existing VirusTotal behavior*." Concretely, that means:

- **`analyzer.py`'s call site does not change its call shape.**
  `with ThreatIntelService() as service: service.enrich_results(extracted_iocs)` continues to
  work with zero-argument construction and the same `enrich_results(dict) -> dict` signature —
  the dict-in/dict-out interface is preserved even though internally it's now backed by
  `ProviderResult`/`Verdict` objects that get converted back into the existing dict shape
  (`{"sha256": ..., "found": ..., "malicious": ..., ..., "verdict": ..., "detection_ratio":
  ...}`) at the `enrich_results` boundary. This is a deliberate compatibility seam: every
  downstream consumer identified in §1/§12 (scoring, correlation, risk explanation, GUI
  widgets, the database's JSON-blob persistence) reads that dict shape, and none of them are
  in Phase 4C's stated scope to modify.
- **`"Malicious"` / `"Suspicious"` / `"Clean"` strings are preserved exactly**, per §5's
  legacy-string-compatibility note — this is non-negotiable for the exact-match consumers
  identified in §12, none of which are being touched this phase.
- **A new `"Not Found"` string is added, not substituted for an existing one** — old,
  un-migrated code paths that don't know about the new value will simply treat it the way
  they treat any unrecognized string today (§12's `_VERDICT_COLORS` default-gray example) —
  degrading gracefully rather than crashing or misclassifying, but not yet *correctly*
  surfacing the distinction until those consumers get their own follow-up updates (explicitly
  out of Phase 4C scope; see §18 backlog note).
- **Persisted investigations (old JSON blobs in `database/soc_iq.db`) are read as-is.**
  `Investigation.threat_intelligence` is a raw JSON blob (CONFIRMED, `app/database/repository.py`)
  with no version tag. Old rows will contain the old two-and-a-half-state verdict shape
  (`"Malicious"`/`"Suspicious"`/`"Clean"`, with pre-existing not-found records already
  mislabeled `"Clean"` forever, since the mislabeling happened at write time and cannot be
  retroactively corrected without re-querying VirusTotal). This document does **not** propose
  a backfill/migration of historical investigation records — that is a product decision (does
  it matter that old investigations show stale "Clean" for what were actually not-found
  results?) outside this document's architecture scope, flagged here so it isn't silently
  assumed away.
- **`VirusTotalClient` itself is not deleted or renamed** — `VirusTotalProvider` wraps it
  (§13.1), so any code that (like `threat_intel_page.py`, §1) constructs and uses
  `VirusTotalClient` directly, bypassing `ThreatIntelService` entirely, keeps working
  unmodified. `threat_intel_page.py`'s existing correct `found` handling is untouched by this
  refactor and is not a compatibility risk.

---

## 15. Testing Strategy (PROPOSED)

1. **New test, first priority, before any refactor is considered complete (per §2.3's
   confirmed gap):** an `enrich_results`-level test asserting that a not-found lookup
   (`found: False`, all counts zero) produces the new not-found verdict string end-to-end
   through `ThreatIntelService`, not just at the `VirusTotalClient` layer where it's already
   covered. This closes the exact gap identified in §2.3 and is the single test that would
   have caught today's bug had it existed.
2. **Aggregation-policy unit tests**, independent of any provider — feed `aggregate()`
   (§9) synthetic `ProviderResult` lists directly (multiple malicious, mixed
   malicious+not-found, all-not-found, all-unavailable, etc.) without going through a real or
   fake provider at all. This satisfies the Master Plan §26 Phase 4C exit criterion ("new unit
   tests for verdict policy") literally.
3. **Existing 542-test baseline (388 confirmed collected/passing outside `tests/gui/` this
   phase; GUI suite not re-run this phase since no GUI code changes — consistent with
   `PHASE4B_EXIT_CRITERIA.md`'s own reported baseline) must remain green throughout.** In
   particular:
   - `tests/test_virustotal.py`'s 77 tests should require **zero changes** if §13.1's
     "preserve almost verbatim" plan is followed — `VirusTotalClient`'s public interface
     doesn't change, only who calls it.
   - `tests/test_threat_intel.py`'s 20 tests, which construct `ThreatIntelService(virustotal=
     fake_client)` with a fake client object, will need updating to the new constructor shape
     (`ThreatIntelService(providers=[fake_provider])` or equivalent) — this is an **expected,
     planned** test-file change, not an unplanned regression, since the constructor signature
     is intentionally changing per §13.3. Every existing assertion in that file (verdict
     strings, coverage counters, rate-limit/invalid-key stop-everything behavior,
     status values) should still hold once the fakes are updated to the new shape — the
     *behavior* being tested is preserved even though the *construction* of the test double
     changes.
4. **Provider-contract test:** a `ThreatIntelProvider`-protocol compliance check (structural,
   e.g. via `typing.Protocol` runtime-checkable or a shared test-suite-as-function pattern)
   that `VirusTotalProvider` — and any future provider — can be run against, so a second
   provider's onboarding (§18) gets correctness assurance for free rather than needing bespoke
   tests reinvented per provider.
5. **Legacy-string regression tests:** explicit tests asserting `"Malicious"`/`"Suspicious"`/
   `"Clean"` are byte-for-byte unchanged and that the new not-found string does not equal any
   of them — directly guarding the §14 compatibility guarantee, not just hoping it holds.

---

## 16. Migration Risks (PROPOSED — risk register for this specific phase)

| Risk | Why it matters here | Mitigation |
|---|---|---|
| `ThreatIntelService` constructor signature change breaks a caller outside `analyzer.py` that this document didn't find | `grep` this phase found exactly one production call site (`analyzer.py`) and one test file — but a missed call site would silently break | Re-run a fresh `grep -rn "ThreatIntelService("` immediately before implementation as a final check, not just at documentation time |
| Legacy verdict strings drift (e.g. `"Malicious"` accidentally becomes `"malicious"` during the enum→string mapping) | Breaks every exact-string consumer identified in §5/§12/§14 silently — no exception, just wrong counts/colors | §15.5's explicit regression tests |
| Sync-to-async bridge (§13.2) introduces a behavioral change in timeout/exception semantics | `asyncio.to_thread` and direct `httpx` async calls have different cancellation/timeout edge cases than `requests` | Whichever option is chosen, add tests specifically for timeout-under-async before considering VT migration done |
| Aggregation policy's error-class precedence (§9 UNKNOWN) gets decided ad hoc during implementation without documentation | Silent, undocumented decision becomes de facto architecture no one signed off on | Resolve explicitly and document the decision (even if it's a short ADR amendment) before Phase 4C is called done |
| Historical `Investigation.threat_intelligence` JSON blobs remain permanently mislabeled (§14) | Could surprise a future developer who assumes all persisted `"Clean"` verdicts are trustworthy | Explicit non-decision recorded here (§14) rather than silently assumed; product call needed, not an architecture call |
| `_enrich_sha256_hashes`/`_enrich_ips`/`_enrich_domains`/`_enrich_urls` (§2.7) removed but something outside the `grep`'d scope depended on them via dynamic dispatch (e.g. `getattr`) | Low probability (no such pattern found this phase) but a silent-removal risk if wrong | Keep as thin deprecated wrappers one phase longer if any doubt surfaces during implementation, rather than deleting outright |

---

## 17. Rollback Strategy (PROPOSED)

- **Source control checkpoint:** per `PHASE4B_GIT_BASELINE_NOTE.md`, a local git repository
  was initialized during Phase 4B specifically to produce verifiable diffs going forward.
  Phase 4C implementation should land as a reviewable, revertible commit (or small commit
  series) on top of that baseline — not as an unreviewable bulk rewrite — so a straight `git
  revert` is sufficient to return to the pre-4C `ThreatIntelService`/`VirusTotalClient` pair
  if the refactor is found to regress behavior after landing.
- **Behavioral rollback safety net:** because §14's compatibility strategy keeps
  `enrich_results(dict) -> dict`'s external shape unchanged, every downstream consumer
  (scoring, correlation, reporting, GUI, persistence) is insulated from the internal
  refactor — a revert of `threat_intel/*` alone, without touching any other module, is
  expected to be sufficient. This is a direct consequence of confirming (§1, §12) that no
  downstream consumer imports `VirusTotalClient`-specific *types* (only the dict-shaped
  output), aside from `threat_intel_page.py`'s direct use for the unrelated ad-hoc lookup page
  (§1). `settings_page.py` appeared in an earlier grep for `VirusTotalClient` but, on direct
  read, only contains a **comment** referencing "Threat Intelligence page builds its
  VirusTotalClient" — it does not import or construct `VirusTotalClient` itself; it only
  reads/writes `ApplicationSettings.virustotal_api_key` and emits a `settings_changed` event.
  Confirmed this phase, not a remaining unknown.
- **No data migration to roll back:** since §14 explicitly proposes no backfill of historical
  `Investigation.threat_intelligence` records, there is no destructive data migration whose
  rollback needs separate planning — old rows are read as-is before, during, and after this
  phase.
- **Test-suite gate:** per Master Plan §26's stated rule (no phase leaves the Python test
  baseline broken), the existing 542-test run (adjusted for the planned `test_threat_intel.py`
  updates in §15.3) passing is the concrete, mechanical rollback trigger — if it cannot be
  made green, the phase is not complete and should not be merged past the checkpoint, per the
  same discipline `PHASE4B_EXIT_CRITERIA.md` already established.

---

## 18. Future Provider Onboarding Procedure (PROPOSED)

Once Phase 4C ships `ThreatIntelProvider` + `VirusTotalProvider` + the verdict/aggregation
model, adding a second provider (AbuseIPDB or OTX, per Master Plan §5.1's examples — **not**
built in Phase 4C itself, per §30.F) should require only:

1. Implement `ThreatIntelProvider` for the new service: `name`, `supported_ioc_types`,
   `is_configured()`, and `lookup()` translating that provider's response shape into
   `ProviderResult` — following the exact translation-table pattern §6 established for VT, not
   inventing a new pattern per provider.
2. Add the new provider's credential field to `ApplicationSettings` following the
   `virustotal_api_key` pattern (§8) — same redaction, same atomic-write persistence, no new
   settings-subsystem work needed.
3. Register the new provider instance in `ThreatIntelService`'s default provider list (or via
   dependency injection for tests, mirroring how `VirusTotalClient`/`VirusTotalProvider` is
   injectable today).
4. Run the provider-contract compliance test (§15.4) against the new adapter — no new
   orchestration, aggregation, or verdict-mapping code should be needed, since that logic is
   provider-neutral by construction once Phase 4C lands. If adding a provider *does* require
   touching `ThreatIntelService`'s orchestration logic itself, that is a signal the Phase 4C
   abstraction was designed too VirusTotal-shaped (Master Plan's own top-10 architectural risk
   #7) and needs correction before a third provider is attempted, not a green light to
   special-case the second provider in place.
5. Extend the aggregation-policy tests (§15.2) with real two-provider-disagreement cases now
   that a second provider actually exists to disagree with the first — this is the point at
   which §9's currently-untested-in-production multi-provider branches get real coverage.
6. Update `docs/architecture/08-threat-intelligence-architecture.md` and this document's §3/§7
   tables to reflect the newly-registered provider and any IOC types it newly supports.

---

## Summary of labeling used throughout this document

- **CONFIRMED** — verified by direct source read this phase (files listed in the Method Note),
  or by an existing test currently passing against that source.
- **PROPOSED** — target-state design carried forward from ADR-007/Master Plan §5 where source
  reading found no reason to deviate, or newly specified in this document where the older
  docs left a gap (e.g. §5's legacy-string mapping, §7's IOC-type-support table, §14's
  compatibility strategy, §17's rollback plan).
- **UNKNOWN** — explicitly not resolved by this document; each instance states exactly what
  question remains open and why it wasn't answered here, rather than being silently assumed.
