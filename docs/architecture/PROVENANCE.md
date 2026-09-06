# SOC-IQ Evidence Provenance & Investigation Integrity (Phase A4-P1)

## What provenance means in SOC-IQ

For a given investigation, SOC-IQ can state, honestly and separately:

1. What was **directly present** in the source report (OBSERVED).
2. What SOC-IQ **calculated** from that (DERIVED).
3. What an **external provider** reported about it (ENRICHED).
4. What SOC-IQ **attempted but could not establish** (UNAVAILABLE).

This is SOC-IQ's own processing provenance — a record of what its own
pipeline did with a given input — not a chain-of-custody, legal
evidence-handling, or forensic-certification claim. See "What
provenance does NOT guarantee" below.

## The four tiers

- **OBSERVED** — Every IOC in `Investigation.iocs`. This codebase has
  exactly one extraction path (`app.extractor.extract_iocs`, a single
  regex pass over the source report's decoded text), so every value
  there is, by construction, directly present in the source report.
- **DERIVED** — The risk score/severity (`app.scoring.engine
  .RiskScoringEngine`), computed by SOC-IQ from the observed and
  enriched data. `severity == "NOT_SCORED"` is the honest sentinel for
  "risk scoring was disabled for this analysis," never a real
  LOW/MEDIUM/HIGH/CRITICAL classification.
- **ENRICHED** — Threat-intelligence results from VirusTotal
  (`Investigation.threat_intelligence`), for the subset of IOC types
  `ThreatIntelService` can actually look up
  (`app.services.threat_intel_state.ENRICHABLE_IOC_TYPES`: `sha256`,
  `ipv4`, `domains`, `urls`).
- **UNAVAILABLE** — `threat_intelligence["status"] == "unavailable"`,
  with `reason` distinguishing *why*: `not_attempted` / `disabled`
  (never ran) vs. `missing_api_key` / `error` (ran, could not
  complete). An unavailable result is never converted into a positive
  or negative security conclusion.

## Source hashing

`app.extractor.compute_source_provenance()` computes a SHA-256 digest
over the exact bytes read from disk for a given report — before UTF-8
decoding, before any normalization — reusing the same pre-open,
`stat()`-based size check the existing §20 ingestion-size control
already enforces (`app.extractor.MAX_REPORT_SIZE_BYTES`). The file is
read from disk exactly once per analysis; the hash is never
recalculated per IOC or per query.

`Investigation.source_sha256` / `source_size_bytes` are nullable.
`None` means one specific, honest thing: this investigation was
persisted before Phase A4-P1, so the hash was never calculated — not
"unavailable due to an error," not a placeholder, and never backfilled
after the fact.

## IOC provenance

Every `Investigation.iocs` entry is OBSERVED, extracted by
`app.extractor.extract_iocs`'s single regex-based extractor. This
codebase does not track a fake line/column source location for IOCs —
none is available — and A4-P1 does not invent one.

## Risk provenance

Risk scoring (`RiskScoringEngine`) is unchanged by A4-P1. Provenance
here means correctly labeling *whether* a real score was computed
(`severity != "NOT_SCORED"`), not re-deriving or re-explaining the
scoring logic itself.

## Investigation Integrity Summary

`app.services.investigation_integrity.build_integrity_summary()`
derives, purely from an already-loaded `Investigation` (no DB access,
no provider call):

- Source report identified?
- Source hash available?
- Analysis completed?
- IOC extraction completed?
- Threat intelligence attempted?
- Threat intelligence complete?
- Risk calculation completed?

"Export generated?" is deliberately not included — no domain object in
this codebase currently records that an export happened for a given
investigation; inventing an answer would violate this module's own
"derived, never fabricated" rule. That belongs to a future phase, once
export events are actually tracked somewhere.

## Evidence Provenance Summary

`app.services.evidence_provenance.build_evidence_provenance_summary()`
derives the OBSERVED / ENRICHED / DERIVED counts described above,
reading `coverage.succeeded` from the persisted `threat_intelligence`
payload rather than re-deriving it, so it can never disagree with what
`ThreatIntelService` itself reported.

## API surface

`get_investigation_integrity` (new command, mirrors `get_iocs` /
`get_threat_intelligence`'s existing pattern) returns:

```json
{
  "investigation_id": 1,
  "report_name": "malware_report.txt",
  "source_sha256": "…64 hex chars, or null for a legacy record…",
  "source_size_bytes": 12345,
  "integrity": { "...InvestigationIntegritySummary fields..." },
  "evidence": { "...EvidenceProvenanceSummary fields..." }
}
```

`source_sha256` / `source_size_bytes` are also now present on
`InvestigationSummaryDTO` (used by `get_investigation`,
`list_investigations`, `search_investigations`, and the Dashboard's
`recent_investigations`) — both nullable scalars, so this is an
additive, backward-compatible field, not a shape change.

## What provenance does NOT guarantee

SOC-IQ's provenance model in this phase is **not**:

- Legal chain of custody
- Court admissibility
- Forensic certification
- Tamper-proof, cryptographically-signed evidence preservation
- Multi-user, audited case management

It documents what SOC-IQ's own pipeline did with a given input, using
plain SHA-256 integrity hashing and honest state labeling — nothing
more.

## Scope note

This phase (A4-P1) is backend/DB/DTO only: `app.extractor`,
`app.analyzer`, `app.database.models`/`repository`,
`app.application.dto`/`handlers`, and the two new
`app.services.investigation_integrity` /
`app.services.evidence_provenance` modules. The Qt desktop GUI
(`app/gui`) and the Tauri frontend (`frontend/`) do not yet surface
any of this — that is deliberately deferred to a later checkpoint.

## Phase A4-P2.1 — per-IOC provenance domain model

A4-P1 (above) is investigation-level: aggregate OBSERVED / ENRICHED /
DERIVED counts for a whole investigation. A4-P2.1 adds a
*per-IOC* domain model, in `app.services.ioc_provenance`, answering,
for one individual indicator value:

> Where did **this** indicator come from, and how was it produced?

This is domain-model-only — no SQLite table, no repository, no API/
DTO surface, no UI wiring. Those are deferred to A4-P2.2 (persistence),
A4-P2.3 (API/DTO), and A4-P2.4 (UI) respectively.

### Model

- **`ObservationState`** — `OBSERVED` (the value was directly present
  in the source report's decoded text) or `DERIVED` (SOC-IQ generated
  the value via a documented transformation). This codebase's only
  extraction path (`app.extractor.extract_iocs`, a single regex pass
  per IOC type) never transforms a value — it only locates and
  deduplicates ones already present — so `build_ioc_provenance()`
  never produces a `DERIVED` record today. The member exists so this
  vocabulary doesn't need reinventing once a real derivation path
  exists.
- **`SourceReference`** — `report_name` (the same identity
  `Investigation.report_name` already uses) plus the A4-P1
  `source_sha256` integrity hash when available (`None` for a legacy,
  pre-A4-P1 investigation — never fabricated or backfilled). No line/
  column/offset/page field: the extractor records no match position,
  so none is invented — "source = this report", not a fabricated
  location within it.
- **`ExtractionMethod`** — reuses `app.extractor.IOC_PATTERNS`'s
  existing `ioc_type` vocabulary as the extractor identity, rather
  than inventing a second, parallel taxonomy; this codebase has
  exactly one regex extractor per IOC type, so `ioc_type` alone
  already identifies it unambiguously.
- **`IOCProvenance`** — an immutable (frozen-dataclass) historical
  fact combining an IOC value with its `SourceReference`,
  `ExtractionMethod`, and `ObservationState`. It explains an existing
  `Investigation.iocs` value; it does not replace or duplicate that
  storage, and no second competing IOC model was introduced. A single
  IOC value can have more than one `IOCProvenance` record (e.g. the
  same value observed in two different reports) — the model does not
  assume one IOC has exactly one source forever.
- **`build_ioc_provenance(investigation)`** — a pure function (no DB/
  filesystem/network access, no mutation) deriving every
  `IOCProvenance` record for an already-loaded `Investigation`, one
  per `(ioc_type, value)` pair in `investigation.iocs`.

### What it deliberately does not do

Threat-intelligence enrichment remains a separate ENRICHED tier (see
A4-P1 above) — this module never treats a TI provider as an IOC's
provenance. It does not implement analyst/system audit logging ("what
did the application/user do"), and it makes no chain-of-custody,
legal-admissibility, or tamper-proof evidence claim — consistent with
"What provenance does NOT guarantee" above.

## Phase A4-P2 Part 2 — provenance query/read model

A4-P2.1 (above) is domain-model-only: `build_ioc_provenance()` exists,
but nothing yet calls it through the application boundary. Part 2 adds
exactly that — a `get_investigation_provenance` command, following the
same `handler → DTO → response envelope` path every other read
command in `app.application` already uses (no parallel API
architecture, no direct frontend-to-database path).

### Contract

`get_investigation_provenance` (`GetInvestigationProvenanceRequest` →
`GetInvestigationProvenanceCommandHandler`, registered in
`COMMAND_HANDLERS` and reachable through the existing generic
`POST /commands/{name}` route — no new route was added) returns:

```json
{
  "investigation_id": 1,
  "report_name": "malware_report.txt",
  "source_integrity": {
    "report_name": "malware_report.txt",
    "algorithm": "sha256",
    "sha256": "…64 hex chars, or null…",
    "size_bytes": 12345,
    "status": "AVAILABLE",
    "reason": null
  },
  "ioc_provenance": [
    {
      "ioc_value": "8.8.8.8",
      "ioc_type": "ipv4",
      "state": "OBSERVED",
      "report_name": "malware_report.txt",
      "source_sha256": "…or null…",
      "extraction_method": "regex:ipv4"
    }
  ]
}
```

- **`source_integrity`** (`SourceIntegrityDTO`) — wraps the A4-P1
  `source_sha256`/`source_size_bytes` fields with an explicit
  `AVAILABLE`/`UNAVAILABLE` `status`. `UNAVAILABLE` means exactly one
  honest thing — a legacy, pre-A4-P1 investigation whose hash was
  never calculated (`reason:
  "legacy_investigation_predates_source_hashing"`) — never a
  fabricated or backfilled value, and never "the investigation is
  invalid".
- **`ioc_provenance`** (`list[IOCProvenanceDTO]`) — one entry per
  `app.services.ioc_provenance.build_ioc_provenance()` record for the
  investigation, called purely in-memory against the already-loaded
  `Investigation` (no N+1 query per IOC). An investigation with no
  extracted IOCs returns `[]` here — a genuine **EMPTY** state,
  distinguishable from the **NOT_FOUND** failure envelope (unknown
  `investigation_id`) by `success`/`error` alone. Source-hash
  unavailability and IOC provenance availability vary independently —
  either can be present while the other is not (**PARTIAL**
  availability), and neither ever collapses into "no evidence" for
  the investigation as a whole.
- **Scoping** — every field above comes from the one `Investigation`
  row `InvestigationService.get_by_id(investigation_id)` loads;
  nothing here can pull in another investigation's rows. Covered by
  `test_investigation_a_never_returns_investigation_bs_provenance`.
- **Deliberately excluded**: the aggregate `integrity`/`evidence`
  summaries stay owned by `get_investigation_integrity` (A4-P1) —
  not duplicated here — and no `analysis_events`/audit-log section
  exists, since this codebase does not track one (see A4-P2.1's own
  "does not implement audit logging" note above).

### Frontend/Tauri

No frontend or Rust/Tauri file was changed in this part. Exactly as
`get_investigation_integrity` (A4-P1) was left unwired to the
frontend's `CommandName`/`CommandContracts` TypeScript contract —
deliberately, per this document's own A4-P1 scope note —
`get_investigation_provenance` is left unwired the same way: the
command is reachable over HTTP today, but the UI to consume it is a
later A4-P2 part's job, not this one's.
