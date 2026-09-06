# Phase 3E: Backend Parity Closeout

## Purpose

Phase 3D (see `docs/PHASE3_PART3D.md`) added VirusTotal *enrichment*
for IPv4, domain, and URL indicators alongside the original
SHA256-only support, and taught the GUI's IOC drill-down and
enrichment-status surfaces to recognize all four types.

What Phase 3D did **not** do is update every *consumer* of
`threat_intelligence` to read anything beyond
`threat_intelligence["hashes"]`. As a result, a malicious IPv4,
domain, or URL that VirusTotal correctly flagged could:

- contribute nothing to the risk score,
- generate no evidence-correlation link,
- be invisible in the "why this risk?" explanation,
- fail to display or be selectable in parts of the GUI, and
- be silently missing from the HTML, Markdown, and PDF reports,

even though it was fully enriched and present in the underlying
data. Phase 3E is a backend/reporting **parity** closeout: it makes
every consumer treat all four enrichable categories identically to
how hashes were already treated. It is explicitly not a new
scoring formula, a new provider, or a redesign of any kind.

## Four-Category TI Mapping

Every consumer updated in this phase uses the same canonical
mapping from `threat_intelligence` category key to the record field
holding the indicator's value:

| Category (`threat_intelligence` key) | Value field | Display label |
| --- | --- | --- |
| `hashes` | `sha256` | SHA256 |
| `ips` | `ip` | IPv4 |
| `domains` | `domain` | Domain |
| `urls` | `url` | URL |

`hashes` is always ordered/handled first everywhere this mapping
appears, so a hash-only investigation (the pre-Phase-3E shape)
produces byte-for-byte-equivalent output to before.

## Scope

### Scoring parity (already complete on checkpoint entry)
`RiskScoringEngine._calculate_threat_intel_score()` iterates
`TI_CATEGORIES = ("hashes", "ips", "domains", "urls")` and scores
each category's records with the same
`malicious * 5 + suspicious * 2 + abs(negative reputation)` formula
previously applied only to hashes. No formula change; existing
hash-only behavior is unchanged (see
`tests/test_scoring.py::test_threat_intel_score_existing_hash_only_behavior_unchanged`).

### Correlation parity (already complete on checkpoint entry)
`CorrelationService._TI_LINK_CATEGORIES` maps
`("sha256", "hashes", "sha256")`, `("ipv4", "ips", "ip")`,
`("domains", "domains", "domain")`, `("urls", "urls", "url")` and
generates a `RELATIONSHIP_THREAT_INTEL_LINK` result for any IOC
value that has a matching enrichment record, regardless of which of
the four categories it belongs to.

### Risk explanation parity (already complete on checkpoint entry)
`RiskExplanationService._count_threat_intel_verdicts()` counts
`"Malicious"`/`"Suspicious"` verdicts across all four categories
(`_TI_VERDICT_CATEGORIES`). The public field names
(`threat_intel_malicious_hash_count`,
`threat_intel_suspicious_hash_count`) are unchanged for backward
compatibility, but the counts they report now span every
enrichable category.

### GUI parity
- `InvestigationWorkspacePage.load_investigation()` already built
  `_threat_intel_by_value` from all four categories, and
  `_on_ioc_selected()` already attached the threat-intel lookup for
  `sha256`, `ipv4`, `domains`, and `urls` IOC categories on
  checkpoint entry.
- **Fixed in this phase:** `ThreatIntelligenceWidget.select_hash()`
  was left over from before `_threat_data` became a list of
  `{"record", "value_field", "type_label"}` wrapper entries -- it
  still read `result.get("sha256")` directly on the wrapper, which
  is never present there, so it always returned `False` and the
  "Investigation -> IOC -> Threat Intelligence" drill-down was
  broken for every indicator, including hashes. Added
  `select_indicator(value)`, which checks each entry's own
  `record.get(entry["value_field"])`, and kept `select_hash()` as a
  backward-compatible alias calling it.
  `InvestigationWorkspacePage._on_threat_intel_requested()` now
  calls `select_indicator()` directly since it may be handed any of
  the four indicator types.
- `ThreatIntelligenceWidget._open_details()` and the aggregate
  table already worked against the generalized wrapper shape and
  needed no change.

### Reporting parity (the primary gap closed in this phase)
`app/reporting/html_exporter.py`, `markdown_exporter.py`, and
`pdf_exporter.py` each still built their Threat Intelligence table
from `threat_intelligence["hashes"]` only. All three now iterate
the canonical four-category mapping and render an
Indicator / Type / Verdict / Detection Ratio row for every enriched
record in every category:

- **HTML**: `_build_threat_summary()` generalized; table header
  gained a "Type" column; the summary "Threat Entries" count now
  sums across all four categories; the click-to-view-details JS
  panel now shows "Indicator" and "Type" (`data-indicator`,
  `data-type` attributes) instead of a hardcoded SHA256 field.
- **Markdown**: the TI section now builds an
  `Indicator | Type | Verdict | Detection Ratio` table from all
  four categories; falls back to "No threat intelligence available."
  only when every category is empty.
- **PDF**: the `Table`/`TableStyle` threat-intel block gained a
  "Type" column and now iterates all four categories; the
  fallback "No Threat Intelligence" row is unchanged in shape when
  every category is empty.

JSON export was intentionally left unchanged -- it already
serializes the full `threat_intelligence` dict as-is and never
filtered by category.

## Tests Added

- `tests/test_scoring.py`: malicious/suspicious IPv4, domain, and
  URL contribution; combined four-category sum; non-hash-only
  contribution with zero hashes present; explicit hash-only
  regression check.
- `tests/test_correlation_service.py`: TI-link creation for IPv4,
  domain, and URL indicators; combined three-non-hash-link case
  with no SHA256 present at all.
- `tests/test_risk_explanation_service.py`: malicious/suspicious
  counts spanning IPv4, domain, and URL records, individually and
  combined with a hash record.
- `tests/gui/test_investigation_workspace_threat_intel.py`: table
  display of all four category type labels and values;
  `select_indicator()` for each of the four categories;
  `select_hash()` alias behavior for a non-hash value;
  `_open_details()` success for every category (via a monkeypatched
  dialog capturing what was opened).
- `tests/test_reporting.py`: HTML/Markdown/PDF all-four-category
  inclusion tests using a synthetic multi-type report; a hash-only
  regression test confirming no stray IPv4/Domain/URL rows appear
  in the Markdown TI section when those categories are empty; the
  HTML "Threat Entries" summary count spanning all categories.
- `tests/gui/test_phase3e_acceptance.py`: end-to-end acceptance
  test (see below).

## Acceptance Scenario

`tests/gui/test_phase3e_acceptance.py` builds one synthetic
investigation with **no malicious SHA256 hash** and one malicious
IPv4, domain, and URL each, then proves the non-hash TI is not
silently lost at any layer:

| Check | Result |
| --- | --- |
| A. Scoring produces non-zero TI contribution | PASS |
| B. Correlation produces a TI-link per non-hash indicator (3) | PASS |
| C. Risk explanation counts non-hash malicious indicators (3) | PASS |
| D. GUI Threat Intelligence tab displays all 3 records | PASS |
| E. GUI selection (`select_indicator`, drill-down) works for each | PASS |
| F. HTML report includes all 3 indicators | PASS |
| G. Markdown report includes all 3 indicators | PASS |
| H. PDF report includes all 3 indicators | PASS |

## Repository-Wide SHA256-Only Audit

Searched for `.get("hashes", [])`, `record.get("sha256")`,
`"hash indicator"`, and related patterns across `app/`. Every
remaining occurrence was classified:

- **Legitimately SHA256-specific** (left unchanged):
  - `app/threat_intel/service.py` -- `_enrich_sha256_hashes()` is
    one of four parallel per-category enrichment methods
    (`_enrich_ips`, `_enrich_domains`, `_enrich_urls` are its
    siblings); this is enrichment, not consumption, and is correct
    as SHA256-specific code.
  - `app/gui/pages/threat_intel_page.py` -- the manual VirusTotal
    lookup page already branches on `query_type` for all four types
    and its result-rendering line
    (`result.get("sha256") or result.get("ip") or ...`) already
    falls through every value field; this is unrelated to
    investigation-level TI aggregation.
  - `app/gui/pages/investigation_workspace.py` line ~306
    (`for record in ti.get("hashes", []):`) -- this is the first of
    four sequential per-category loops (hashes, then ips, domains,
    urls) that together build `_threat_intel_by_value`; each loop
    individually mentions its own category by name, which is
    expected and correct.
- **Accidental single-category consumption** (fixed in this phase):
  - `ThreatIntelligenceWidget.select_hash()` (see GUI parity above).
  - `html_exporter.py`, `markdown_exporter.py`, `pdf_exporter.py`
    (see Reporting parity above).
- **Stale documentation/comments**: none found requiring correction
  beyond the docstrings updated alongside the code changes above
  (e.g. `select_hash()`'s docstring now describes it as an alias).

No further accidental single-category consumption remains.

## Final Verification Result

Full suite: `python -m pytest --tb=short -q`

```
542 passed in 5.20s
```

(Checkpoint entry state was 504 passed, 2 failed -- the two
`select_hash()` regressions described above.)

## Intentionally Left Outside Phase 3E Scope

- No new threat-intelligence provider or provider architecture
  change.
- No scoring *formula* change -- only category coverage.
- No database/schema redesign; `threat_intelligence` remains the
  same JSON shape.
- No change to JSON export (`json_exporter.py`), which already
  serializes the complete `threat_intelligence` structure.
- No change to `ThreatIntelService`'s enrichment logic itself
  (`app/threat_intel/service.py`, `virustotal.py`) -- Phase 3D
  already covers enrichment; Phase 3E covers consumption of
  already-enriched data.
