# SOC-IQ Investigation Timeline — Domain & Database Foundation (Phase A4-P2-P3, Part 1/6)

## Purpose

The investigation timeline records **events that SOC-IQ itself knows
happened during an investigation** — an append-only history of the
application's own processing, not a malware-execution timeline. It
must never assert an unsupported security conclusion (e.g. "attacker
entered system", "persistence established") unless SOC-IQ's existing
pipeline actually establishes that fact. Today, nothing in the
codebase establishes attacker/malware-behavior facts, so no such
event type exists.

This document covers **only Part 1/6**: the domain model, controlled
vocabulary, and database/repository foundation. It does not cover
event emission, frontend rendering, or replay — see "What this part
intentionally does NOT include" below.

## Timeline event definition

`app.timeline.domain.TimelineEvent` (frozen dataclass):

| Field | Type | Notes |
|---|---|---|
| `event_id` | `str` | `uuid4().hex`, generated at construction — same strategy as `app.application.events.Event._new_event_id`. |
| `investigation_id` | `int` | The *existing* investigation identity (`Investigation.investigation_id`), not a new `CaseId`/`TimelineInvestigationId` type. Must be a positive int. |
| `event_type` | `TimelineEventType` | See vocabulary below. Unknown values raise `TimelineValidationError`. |
| `timestamp` | `datetime` | Must be timezone-aware (UTC). Naive datetimes are rejected, not silently assumed to be UTC. |
| `source` | `str` | Defaults to `"system"`. Must be non-empty. |
| `summary` | `str` | Must be non-empty and at most `MAX_SUMMARY_LENGTH` (512) characters — a short human-readable label, not a place to store report bodies or long text. |
| `metadata` | `dict[str, Any]` | See Metadata policy below. Defaults to `{}`. |

## Supported event types

Naming follows `docs/contracts/event-model.md`'s existing
`domain.action` convention. `ti.enrichment.completed` reuses that
document's exact reserved name for threat-intel enrichment
completion rather than introducing a second, differently-spelled
name for the same real-world occurrence — the specific duplication
that document warns against.

| Event Type | Value | Meaning |
|---|---|---|
| `INVESTIGATION_CREATED` | `investigation.created` | A new SOC-IQ investigation record was created. |
| `REPORT_IMPORTED` | `report.imported` | A source report's bytes were read and accepted for analysis. |
| `ANALYSIS_STARTED` | `analysis.started` | SOC-IQ's analysis pipeline began processing a report. |
| `ANALYSIS_COMPLETED` | `analysis.completed` | SOC-IQ's analysis pipeline completed successfully — **not** that the analyzed malware "completed execution". |
| `IOC_EXTRACTION_COMPLETED` | `ioc_extraction.completed` | SOC-IQ's extractor finished parsing indicators — does not assert they are malicious. |
| `TI_ENRICHMENT_COMPLETED` | `ti.enrichment.completed` | SOC-IQ's threat-intel enrichment step finished querying configured providers. |
| `RISK_CALCULATED` | `risk.calculated` | SOC-IQ's scoring engine computed a risk score from its own data. |
| `CORRELATION_COMPLETED` | `correlation.completed` | SOC-IQ's correlation service finished deriving relationships between this investigation's own extracted/enriched evidence (duplicate indicators, related threat-intelligence records, etc.) -- within this one investigation only, never against any other investigation SOC-IQ holds (revised in A4-P2-P3 Part 6 to match `CorrelationService`'s actual, verified scope; see that service's own docstring). |
| `REPORT_EXPORTED` | `report.exported` | SOC-IQ exported an investigation report to a file. |

This vocabulary is deliberately small and closed (enforced by a
database `CHECK` constraint, not just Python-side validation — see
below). Extending it requires a new migration.

## Timestamp policy

UTC, timezone-aware `datetime` in the domain layer; stored as ISO-8601
TEXT in SQLite — identical to `investigations.analyzed_at`'s existing
convention (`app/database/repository.py` stores
`datetime.isoformat()` / reads back with `datetime.fromisoformat()`).
No second timestamp representation was introduced.

## Ordering policy

`TimelineRepository.list_for_investigation()` returns events **oldest
→ newest**, ordered by `(timestamp, rowid)`. A timestamp alone is not
a sufficient sole ordering key since two events can share the same
stored instant; `rowid` (SQLite's implicit, strictly-increasing
insertion-order integer — the table is not `WITHOUT ROWID`) gives a
deterministic, stable tie-break without a redundant hand-maintained
sequence column. Same database state → same timeline ordering,
always.

## Metadata policy

Structured, JSON-compatible, bounded, and secret-free:

- Must be a `dict`; must be JSON-serializable with plain
  str/int/float/bool/None/dict/list values.
- Bounded to **4096 bytes** (`app.timeline.domain.MAX_METADATA_BYTES`)
  of its JSON-encoded form. This bound is established fresh for this
  feature (no pre-existing project-wide metadata-size limit was found
  to reuse) and is generous for the kind of payload this vocabulary
  needs (e.g. `{"ioc_count": 31}`), while preventing metadata from
  becoming a dumping ground for entire `Investigation.iocs` /
  `Investigation.threat_intelligence` objects, which already have
  their own dedicated, unbounded columns.
- Metadata key names are checked against a conservative,
  substring-based deny-list (`api_key`, `token`, `password`,
  `secret`, `private_key`, `credential`, and close variants) and
  rejected with `TimelineMetadataError` if matched. This is a
  name-based guard, not a value-scanning secret detector — SOC-IQ's
  actual credential storage
  (`app.secrets.RustKeystoreHandoffSecretStore`) has no generic
  scanning mechanism to reuse for this purpose, so this check is new
  and deliberately conservative.

## Append-only principle

Timeline events are historical records. `TimelineRepository` exposes
only `append()` and `list_for_investigation()` — no `update_event()`
or `delete_event()`. If a future correction is ever needed, the
intended pattern is to append a new, corrective event, never to
rewrite history in place. This is a deliberate product principle, not
an oversight, and is enforced by the repository's public surface.

## Database relationship

`timeline_events` (migration `0003_add_timeline_events.sql`):

- `event_id TEXT PRIMARY KEY` — Python-assigned identity, not
  `AUTOINCREMENT`.
- `investigation_id INTEGER NOT NULL REFERENCES investigations(id) ON
  DELETE CASCADE` — a per-investigation retention choice. SOC-IQ
  already hard-deletes investigations
  (`InvestigationRepository.delete`), which already destroys that
  investigation's IOCs/threat-intel/risk data outright; a timeline
  row for a deleted investigation records history about evidence
  that no longer exists, so it cascades with its parent rather than
  becoming an orphan. `PRAGMA foreign_keys = ON` is already the
  project-wide default (`app/database/connection.py`); this
  migration does not change that default, only adds a table that
  uses it.
- `event_type TEXT NOT NULL CHECK (...)` — the closed vocabulary
  above, enforced at the database layer as a defense-in-depth measure
  against a bug that bypasses `TimelineEventType` validation.
- `timestamp TEXT NOT NULL`, `source TEXT NOT NULL`, `summary TEXT
  NOT NULL`, `metadata TEXT NULL` (JSON, NULL meaning "no metadata").
- Index: `idx_timeline_events_investigation_timestamp` on
  `(investigation_id, timestamp)` — serves the dominant query
  ("timeline for investigation X, ordered by time").
- Migration 0003 is additive-only: no existing table, column, or row
  is altered, renamed, dropped, or rewritten. Verified against both a
  fresh database and a hand-built pre-migration ("legacy") database
  containing existing investigation data (`tests/test_timeline_database.py`).

## Retrieval & pagination

`TimelineRepository.list_for_investigation` returns the complete
timeline for one investigation in a single query — there is no
pagination/limit-offset parameter as of this checkpoint.

This is a deliberate scope decision, not an oversight: timeline
volume is bounded by what one investigation's own pipeline run can
append to it (the closed vocabulary in `TimelineEventType` currently
has 9 members, so a single investigation's history is realistically
in the tens of events, not thousands), and the query is already
scoped to one investigation via the
`(investigation_id, timestamp)` index rather than scanning the whole
table. Introducing limit/offset or keyset pagination now would add
API surface with no present caller and no present volume problem to
solve. If a future part finds investigations accumulating timelines
large enough that this stops holding, pagination should be added
then, against real usage data, rather than spec'd out speculatively
here.

## What this part intentionally does NOT include

Deferred to later parts of A4-P2-P3, per the Part 1 brief:

- Wiring `app.analyzer` / `app.extractor` / `app.reporting` /
  `app.threat_intel` to actually emit timeline events (Part 2).
- Any application/service-layer event emission or DTO/API contract
  for the timeline (Part 2).
- Frontend timeline component, cards, filters, or dashboard
  integration (Part 3).
- AI-generated timeline summaries or classification (explicitly out
  of scope for this capability).
- Deterministic replay (a separate, later portion of A4-P2-P3).

Nothing in `app/analyzer.py`, `app/extractor.py`,
`app/reporting/*`, or `app/threat_intel/*` imports `app.timeline` as
of this checkpoint.
