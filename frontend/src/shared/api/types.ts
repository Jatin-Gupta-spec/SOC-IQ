/**
 * API boundary types — foundation only.
 *
 * Mirrors the envelope contract in `docs/contracts/response-model.md`
 * and `docs/contracts/error-model.md`. This module defines SHAPES only;
 * it does not implement transport (see `client.ts` for why).
 */

export interface ApiError {
  code: string;
  message: string;
}

export interface ApiSuccess<T> {
  success: true;
  data: T;
  error: null;
}

export interface ApiFailure {
  success: false;
  data: null;
  error: ApiError;
}

export type ApiResponse<T> = ApiSuccess<T> | ApiFailure;

export function isApiSuccess<T>(
  response: ApiResponse<T>,
): response is ApiSuccess<T> {
  return response.success;
}

/**
 * Command contract map — Phase 4E-P1.
 *
 * Mirrors, field-for-field, the source of truth in
 * `app/application/dto.py` (request DTOs) and the `ok(...)` payloads
 * built by each handler in `app/application/handlers.py` (response
 * shapes). Nothing here is invented: every field name/type is a
 * mechanical transcription of the Python dataclass or dict literal it
 * comes from, and every command name is a 1:1 match for
 * `app/application/handlers.py::COMMAND_HANDLERS`'s ten keys.
 *
 * Fields whose backend shape is an opaque, not-yet-DTO'd dict
 * (`Investigation.iocs`, `Investigation.threat_intelligence`,
 * `ThreatIntelService.lookup_indicator`'s return value) are typed as
 * `Record<string, unknown>` rather than guessed at — inventing a
 * fine-grained shape for those would be exactly the kind of type
 * fabrication `PHASE4E_ARCHITECTURE.md` warns against ("do not invent
 * types where backend types can be derived from the existing source
 * contract").
 */

// ---------------------------------------------------------------------------
// Shared response fragments
// ---------------------------------------------------------------------------

/** Mirrors `InvestigationSummaryDTO.to_dict()` (app/application/dto.py). */
export interface InvestigationSummary {
  investigation_id: number | null;
  report_name: string;
  risk_score: number;
  severity: string;
  confidence: number;
  status: string;
  analyzed_at: string;
}

export const VALID_EXPORT_FORMATS = [
  "html",
  "pdf",
  "json",
  "markdown",
] as const;
export type ExportFormat = (typeof VALID_EXPORT_FORMATS)[number];

/**
 * The ten persisted IOC categories, mirroring `app/extractor.py`'s
 * extraction schema (the canonical source for `Investigation.iocs`'s
 * keys) field-for-field. This is the same list `get_iocs` and
 * `get_threat_intelligence`'s `states` projection both group by, so
 * it is the one frontend union both response shapes key on.
 *
 * Not to be confused with `VALID_IOC_TYPES`/`IocType` below, which is
 * `enrich_ioc`'s own narrower request-payload contract
 * (`EnrichIocRequest`'s four VirusTotal-enrichable types) and is left
 * as-is here.
 */
export const PERSISTED_IOC_TYPES = [
  "ipv4",
  "domains",
  "urls",
  "emails",
  "md5",
  "sha1",
  "sha256",
  "cves",
  "windows_file_paths",
  "windows_registry_keys",
] as const;
export type PersistedIocType = (typeof PERSISTED_IOC_TYPES)[number];

/** Mirrors `get_iocs`'s response shape: `Investigation.iocs`, keyed by
 * `PersistedIocType`, each value a list of persisted indicator strings. */
export type IocsByType = Partial<Record<PersistedIocType, string[]>>;

export const VALID_IOC_TYPES = ["sha256", "ipv4", "domain", "url"] as const;
export type IocType = (typeof VALID_IOC_TYPES)[number];

/**
 * The six TI_STATE_* constants, mirroring
 * `app/services/threat_intel_state.py`'s canonical vocabulary
 * exactly. Deliberately not collapsed into a CLEAN/MALICIOUS/UNKNOWN
 * style enum -- that would lose the semantic distinction the backend
 * (and Phase 4J-2's `states` projection) draws between e.g. "not yet
 * enriched" and "no API key configured".
 */
export const TI_STATES = [
  "enriched",
  "not_enriched",
  "no_api_key",
  "provider_error",
  "incomplete_check",
  "unsupported_type",
] as const;
export type TiState = (typeof TI_STATES)[number];

/** Mirrors `build_investigation_indicator_states()`'s return shape:
 * per-indicator TI_STATE_* classification, grouped by `ioc_type` to
 * match `Investigation.iocs`'s own shape. */
export type InvestigationIndicatorStates = Partial<
  Record<PersistedIocType, Record<string, TiState>>
>;

/**
 * The four `Verdict.value` strings `build_investigation_typed_verdicts()`
 * (`app/threat_intel/verdict_from_persisted.py`, Phase 4K-1) can
 * actually produce -- a strict subset of `app/threat_intel/models.py`'s
 * nine-member `Verdict` enum, mirrored byte-for-byte (not renamed, not
 * reordered). That module derives every value via
 * `virustotal_provider.translate_verdict`, whose found-first branching
 * only ever returns `MALICIOUS` / `SUSPICIOUS` / `CLEAN` / `NOT_FOUND`
 * -- the other five `Verdict` members (`UNSUPPORTED`, `NO_API_KEY`,
 * `UNAVAILABLE`, `RATE_LIMITED`, `ERROR`) describe live-lookup outcomes
 * that path never reaches, so they are deliberately not included here.
 * `NOT_FOUND` is a distinct, first-class value -- never collapsed into
 * `CLEAN` (`Verdict`'s own docstring).
 */
export const TYPED_VERDICTS = ["malicious", "suspicious", "clean", "not_found"] as const;
export type TypedVerdict = (typeof TYPED_VERDICTS)[number];

/** Mirrors `build_investigation_typed_verdicts()`'s return shape:
 * `{ioc_type: {value: TypedVerdict | null}}`, grouped by `ioc_type` to
 * match `Investigation.iocs`'s own shape (same grouping
 * `InvestigationIndicatorStates` uses). `null` means the persisted
 * data for that indicator was insufficient to classify honestly (no
 * record, or a record predating the raw `found` field) -- never a
 * fabricated verdict. */
export type InvestigationTypedVerdicts = Partial<
  Record<PersistedIocType, Record<string, TypedVerdict | null>>
>;

/**
 * Mirrors `DashboardMetricsDTO.to_dict()` (app/application/dto.py,
 * Phase 4H Part 1). `threat_intel_coverage_percent` is `null` (not
 * `0`) when no threat-intelligence lookups were ever requested across
 * any investigation -- see that DTO's docstring for why `0` is
 * reserved for the genuine "every request failed" case.
 */
export interface DashboardMetrics {
  total_reports: number;
  total_iocs: number;
  high_risk_count: number;
  threat_intel_coverage_percent: number | null;
}

/**
 * Mirrors `DashboardSummaryDTO.to_dict()` (app/application/dto.py,
 * Phase 4H Part 1) -- the `get_dashboard_summary` aggregate command's
 * response shape.
 *
 * `investigation_status_counts` is keyed by the REAL, persisted
 * `Investigation.status` value (today, in practice, always
 * `"COMPLETED"` -- see `app/services/dashboard_aggregation.py`'s
 * `compute_status_counts` docstring) and is a wholly different
 * concept from `mock/investigations.ts`'s `InvestigationStatus`
 * (`open`/`in_progress`/`closed`) -- that workflow vocabulary does
 * not exist in persisted backend data today, so it is deliberately
 * NOT what this field represents. `risk_distribution` and
 * `ioc_distribution` are both `Record<string, number>` keyed by
 * `severity` and `PersistedIocType` respectively.
 *
 * Timeline data and operational status are deliberately absent --
 * see `DashboardSummaryDTO`'s own docstring (Timeline is an
 * unresolved product decision per the Phase 4H readiness review;
 * operational status already has a live, real-time source via
 * `useSidecarStatus()`/`projectSidecarStatusView()`).
 */
export interface DashboardSummaryResult {
  metrics: DashboardMetrics;
  investigation_status_counts: Record<string, number>;
  risk_distribution: Record<string, number>;
  ioc_distribution: Record<string, number>;
  recent_investigations: InvestigationSummary[];
}

/**
 * Mirrors `GetDashboardSummaryRequest` -- no fields today. Sent as
 * `{}`, per that DTO's own docstring (mirroring
 * `ListInvestigationsRequest`'s "kept as an explicit type ... so a
 * future filter is an additive field, not a payload-shape change").
 */
export type GetDashboardSummaryPayload = Record<string, never>;

/**
 * Mirrors `InvestigationAggregateSummaryDTO.to_dict()`
 * (app/application/dto.py, PD-04) -- the
 * `get_investigation_aggregate_summary` command's response shape.
 * That command was already registered backend-side
 * (`GetInvestigationAggregateSummaryCommandHandler`) with no frontend
 * contract; this closes that pre-existing gap (MAX-5 Dashboard Data +
 * Visualization Foundation) rather than adding a new backend command.
 *
 * `status_counts`, `severity_distribution`, and `ioc_distribution`
 * duplicate values `get_dashboard_summary` already provides under
 * different field names -- this contract exists solely for the one
 * field the Dashboard has no other source for:
 * `investigations_by_date`, a REAL day-bucketed count of
 * investigations grouped by the calendar-date portion of each
 * investigation's persisted `analyzed_at`
 * (`compute_investigation_activity_by_date`,
 * `app/services/dashboard_aggregation.py`). It is deliberately not
 * the Dashboard's separate, still-unresolved Timeline feature, and it
 * carries no risk-trend or IOC-trend series -- no such backend
 * aggregate exists, so the Dashboard must not display one.
 */
export interface InvestigationAggregateSummaryResult {
  total_investigations: number;
  status_counts: Record<string, number>;
  severity_distribution: Record<string, number>;
  ioc_distribution: Record<string, number>;
  threat_intel_coverage_percent: number | null;
  /** Keyed by `YYYY-MM-DD` (UTC-naive calendar date). */
  investigations_by_date: Record<string, number>;
}

/**
 * Mirrors `GetInvestigationAggregateSummaryRequest` -- no fields
 * today, for the same reason `GetDashboardSummaryPayload` has none
 * (see that type's own doc comment).
 */
export type GetInvestigationAggregateSummaryPayload = Record<string, never>;

// ---------------------------------------------------------------------------
// Command names
// ---------------------------------------------------------------------------

/**
 * Command names mirrored here from
 * `app/application/handlers.py::COMMAND_HANDLERS`. Not every backend
 * command has a frontend contract yet -- e.g.
 * `get_investigation_integrity` and `get_investigation_provenance`
 * are already registered backend-side but have no entry below (a
 * pre-existing gap, not something this addition changes or is
 * responsible for closing).
 *
 * `get_investigation_aggregate_summary` added per MAX-5 (Dashboard
 * Data + Visualization Foundation): the handler and
 * `COMMAND_HANDLERS` entry already existed on the backend (PD-04) but
 * had no frontend contract yet -- this closes that gap so the
 * Dashboard can render the one real temporal series SOC-IQ has
 * (`investigations_by_date`), the same pattern `get_settings` and
 * `get_timeline` below already established for pre-existing backend
 * gaps.
 *
 * `get_settings` added per SOC-IQ Part 2B-1 (Settings implementation):
 * the handler and `COMMAND_HANDLERS` entry already existed on the
 * backend (Part 2A, `GetSettingsCommandHandler`) but had no frontend
 * contract yet -- this closes that gap rather than inventing a new
 * command.
 *
 * `get_timeline` added per A4-P2-P3 Part 3 (Application/API
 * integration for the Investigation Timeline): mirrors
 * `GetTimelineCommandHandler`'s response shape 1:1, per this file's
 * own "nothing here is invented" rule.
 *
 * `get_investigation_risk_explanation` added per PD-08-P1 (Risk
 * Explanation backend contract) / PD-08-P2 (this frontend
 * integration): mirrors `GetInvestigationRiskExplanationCommandHandler`'s
 * response shape (`RiskExplanationDTO.to_dict()`,
 * `app/application/dto.py`) 1:1.
 *
 * `export_investigations_csv` added per PD-08-P5.1 (Bulk Investigation
 * CSV Export backend contract) / PD-08-P5.3 (this frontend
 * integration): mirrors `ExportInvestigationsCsvRequest`/
 * `ExportInvestigationsCsvCommandHandler`'s response shape 1:1 (see
 * `docs/phase4/PD08_P5_1_BULK_CSV_EXPORT_BACKEND_CONTRACT.md`). Same
 * "no HTTP download, writes to disk via a caller-supplied absolute
 * `output_path`" convention `export_report` already established --
 * not a new transport shape.
 */
export type CommandName =
  | "get_investigation"
  | "get_iocs"
  | "get_threat_intelligence"
  | "get_timeline"
  | "get_investigation_risk_explanation"
  | "get_settings"
  | "save_settings"
  | "list_investigations"
  | "get_dashboard_summary"
  | "get_investigation_aggregate_summary"
  | "delete_investigation"
  | "search_investigations"
  | "analyze_report"
  | "export_report"
  | "export_investigations_csv"
  | "enrich_ioc";

// ---------------------------------------------------------------------------
// Request payloads — mirrors app/application/dto.py request DTOs
// ---------------------------------------------------------------------------

/**
 * Mirrors `AnalyzeReportRequest`. `options` is optional and, when
 * omitted, defaults server-side to `AnalysisOptions`'s all-`true`
 * defaults (see `app/application/dto.py`) -- so existing callers that
 * only send `report_path` keep getting the full pipeline unchanged.
 *
 * This is contract-foundation only (Phase 4I Blocker B, Part 2A): no UI
 * yet reads or writes `options` (Part 3), and the backend does not yet
 * enforce it against the analyzer pipeline (Part 2B).
 */
export interface AnalyzeReportPayload {
  report_path: string;
  options?: AnalysisOptions;
}

/** Mirrors `AnalysisOptions` (app/application/dto.py). All fields
 * default to `true` server-side when `options` is omitted entirely. */
export interface AnalysisOptions {
  extract_iocs: boolean;
  enrich_ti: boolean;
  score_risk: boolean;
}

/** Mirrors `GetInvestigationRequest`. */
export interface GetInvestigationPayload {
  investigation_id: number;
}

/**
 * Mirrors `ListInvestigationsRequest` — no fields today. Sent as `{}`,
 * per the DTO's own docstring ("kept as an explicit type ... so a
 * future filter is an additive field, not a payload-shape change").
 */
export type ListInvestigationsPayload = Record<string, never>;

/** Mirrors `SearchInvestigationsRequest`. */
export interface SearchInvestigationsPayload {
  report_name: string;
}

/** Mirrors `GetIocsRequest`. */
export interface GetIocsPayload {
  investigation_id: number;
}

/** Mirrors `GetThreatIntelligenceRequest`. */
export interface GetThreatIntelligencePayload {
  investigation_id: number;
}

/** Mirrors `GetTimelineRequest` (A4-P2-P3 Part 3). */
export interface GetTimelinePayload {
  investigation_id: number;
}

/** Mirrors `GetInvestigationRiskExplanationRequest` (PD-08-P1). */
export interface GetInvestigationRiskExplanationPayload {
  investigation_id: number;
}

/**
 * Mirrors `GetSettingsRequest` -- no fields today, sent as `{}`, per
 * the DTO's own docstring (matching `ListInvestigationsPayload`'s
 * reasoning).
 */
export type GetSettingsPayload = Record<string, never>;

/**
 * Mirrors `SaveSettingsRequest`'s discriminated, exactly-one-field
 * contract (`__post_init__` rejects any payload that doesn't set
 * exactly one of the two fields below).
 *
 * MAX19A-F-02: this union no longer has a `virustotal_api_key`
 * variant. No shipped UI code ever constructed one -- credential
 * writes go through `keystore_set_secret` (direct Tauri IPC) via
 * `VirustotalControl`/`useVirustotalKeySave`, never through
 * `runCommand("save_settings", …)` -- but the backend's DTO used to
 * accept the field anyway (MAX19A-F-01), so this typed client union
 * used to permit constructing a call shape that was guaranteed to
 * fail. Narrowed to match the backend now that `SaveSettingsRequest
 * .__post_init__` rejects that field outright.
 */
export type SaveSettingsPayload =
  | { export_directory: string; theme?: never }
  | { theme: string; export_directory?: never };

/** Mirrors `ExportReportRequest`. */
export interface ExportReportPayload {
  investigation_id: number;
  export_format: ExportFormat;
  output_path: string;
}

/**
 * Mirrors `ExportInvestigationsCsvRequest`. `search`, when omitted or
 * blank, means "no filter" (export every investigation) -- identical
 * to the backend's own `None`/blank convention, see that DTO's
 * docstring.
 */
export interface ExportInvestigationsCsvPayload {
  output_path: string;
  search?: string;
}

/** Mirrors `EnrichIocRequest`. */
export interface EnrichIocPayload {
  ioc_type: IocType;
  value: string;
}

/** Mirrors `DeleteInvestigationRequest`. */
export interface DeleteInvestigationPayload {
  investigation_id: number;
}

// ---------------------------------------------------------------------------
// Response data — mirrors the `ok(...)` payload built by each handler in
// app/application/handlers.py
// ---------------------------------------------------------------------------

/** Mirrors one item of `get_investigation`'s additive `correlations`
 * field (`InvestigationCorrelationDTO.to_dict()`, `app/application/dto.py`,
 * Phase 4J-6). A deterministic, explicit-only relationship between two
 * pieces of evidence already present in the investigation — see
 * `app.services.correlation_service.CorrelationService`'s own docstring
 * for the determinism/no-inference guarantees this shape carries. */
export interface InvestigationCorrelation {
  relationship_type: string;
  source: string;
  target: string;
  context: string;
}

/** `InvestigationSummary` plus `get_investigation`'s additive
 * `correlations` field (Phase 4J-6). Deliberately NOT added to
 * `InvestigationSummary` itself — that interface is reused unchanged by
 * `ListInvestigationsResult`, `SearchInvestigationsResult`, and
 * `DashboardSummaryResult["recent_investigations"]`, none of which the
 * backend computes a correlation report for (see
 * `InvestigationCorrelationDTO`'s own docstring). */
export type GetInvestigationResult = InvestigationSummary & {
  correlations: InvestigationCorrelation[];
};

/**
 * Mirrors one value of `GetIocsCommandHandler.handle()`'s additive
 * `significance` field (PD-08-P3, `app/application/handlers.py`):
 * the scoring engine's weight and `app.services.ioc_significance
 * .ioc_type_significance()`'s presentation label for one IOC
 * *category*. Both are pure functions of the category only (never
 * of an individual indicator value) -- see that handler's own
 * docstring. `significance` is left as `string`, not a closed union,
 * for the same backend-owns-the-vocabulary reason
 * `IocCategoryContribution["significance"]` is (see that field's
 * doc comment): the controlled vocabulary
 * (`app.services.ioc_significance`) is backend-owned, not duplicated
 * here as a second, drift-prone copy. The frontend never recomputes
 * either field from `RiskScoringEngine.IOC_WEIGHTS` or any other
 * source -- both travel from the backend unchanged.
 */
export interface IocTypeSignificance {
  weight: number;
  significance: string;
}

/**
 * Mirrors `GetIocsCommandHandler.handle()`'s additive `significance`
 * field shape (PD-08-P3): one `IocTypeSignificance` entry per IOC
 * category actually present on the investigation (i.e. each key of
 * `investigation.iocs`) -- never an entry for a category this
 * investigation has no IOCs of, and never one entry per individual
 * indicator value (mirrors `InvestigationIndicatorStates`'s own
 * `Partial<Record<PersistedIocType, ...>>` grouping convention for a
 * category-keyed, not-necessarily-complete map).
 */
export type IocSignificanceByType = Partial<
  Record<PersistedIocType, IocTypeSignificance>
>;

export interface GetIocsResult {
  investigation_id: number | null;
  iocs: IocsByType;
  /** Additive, PD-08-P3. See `IocSignificanceByType`'s doc comment. */
  significance: IocSignificanceByType;
}

/**
 * Mirrors `GetThreatIntelligenceCommandHandler.handle()`'s response
 * (Phase 4J-2): `threat_intelligence` is the raw, already-persisted
 * dict, exposed as-is, unchanged, for full backward compatibility --
 * left as `Record<string, unknown>` rather than a fabricated
 * VirusTotal schema (no such contract has been verified against the
 * backend source). `states` is the additive Phase 4J-2 projection and
 * is strongly typed, per `InvestigationIndicatorStates`.
 *
 * Phase 4K-1 additionally adds `typed_verdicts` (see
 * `InvestigationTypedVerdicts`). It is typed optional, not
 * `| undefined`-unioned-in-value, because older backend responses
 * predating Phase 4K-1 omit the key entirely rather than sending it
 * as an explicit `undefined` -- a real JSON response either has this
 * key or does not.
 */
export interface GetThreatIntelligenceResult {
  investigation_id: number | null;
  threat_intelligence: Record<string, unknown>;
  states: InvestigationIndicatorStates;
  typed_verdicts?: InvestigationTypedVerdicts;
}

/**
 * Mirrors `TimelineEventDTO.to_dict()` (`app/application/dto.py`,
 * A4-P2-P3 Part 3) -- one event in `get_timeline`'s `events` list.
 *
 * `event_type` is left as `string`, not a closed union, deliberately:
 * the controlled vocabulary
 * (`app.timeline.domain.TimelineEventType`) is owned and enforced by
 * the backend domain layer and its database `CHECK` constraint, not
 * duplicated here as a second, drift-prone copy -- matching this
 * file's own precedent for `EnrichIocResult` and
 * `GetThreatIntelligenceResult["threat_intelligence"]`, which stay
 * loosely typed for backend-owned/evolving shapes rather than
 * guessed at.
 */
export interface TimelineEvent {
  event_id: string;
  investigation_id: number;
  event_type: string;
  timestamp: string;
  source: string;
  summary: string;
  metadata: Record<string, unknown>;
  semantics: string;
}

/** Mirrors `GetTimelineCommandHandler.handle()`'s response
 * (A4-P2-P3 Part 3): the investigation's complete timeline, ordered
 * oldest -> newest (see `TimelineRepository.list_for_investigation`'s
 * own ordering contract) -- never re-sorted client-side. */
export interface GetTimelineResult {
  investigation_id: number;
  events: TimelineEvent[];
}

/**
 * Mirrors `IocCategoryContributionDTO.to_dict()` (`app/application/dto.py`,
 * PD-08-P1) -- one item of `GetInvestigationRiskExplanationResult`'s
 * `ioc_categories`. `significance` is left as `string`, not a closed
 * union, for the same reason `TimelineEvent["event_type"]` is (see
 * that field's doc comment): the controlled vocabulary
 * (`app.services.ioc_significance`) is backend-owned, not duplicated
 * here as a second, drift-prone copy.
 */
export interface IocCategoryContribution {
  ioc_type: string;
  ioc_type_title: string;
  count: number;
  weight: number;
  significance: string;
  points: number;
}

/**
 * Mirrors `RiskExplanationDTO.to_dict()` (`app/application/dto.py`,
 * PD-08-P1) -- `get_investigation_risk_explanation`'s response,
 * field-for-field. Nothing here is invented: every field name/type is
 * a mechanical transcription of the DTO's own `to_dict()`, per this
 * file's own "nothing here is invented" rule.
 */
export interface GetInvestigationRiskExplanationResult {
  investigation_id: number | null;
  report_name: string;
  score: number;
  severity: string;
  confidence: number;
  ioc_score: number;
  threat_intel_score: number;
  cve_score: number;
  ioc_categories: IocCategoryContribution[];
  ioc_breakdown_verified: boolean;
  threat_intel_state: string;
  threat_intel_message: string;
  threat_intel_short_label: string;
  threat_intel_requested: number;
  threat_intel_succeeded: number;
  threat_intel_malicious_hash_count: number;
  threat_intel_suspicious_hash_count: number;
  correlation_evaluated: boolean;
  correlation_relationship_count: number;
  correlation_summary: string;
  engine_reasons: string[];
  narrative: string[];
  warnings: string[];
}

export type SaveSettingsResult = {
  field: "export_directory" | "theme";
  updated: boolean;
};

/**
 * Mirrors `GetSettingsCommandHandler.handle()`'s response
 * (`app/application/handlers.py`): only the safe subset of
 * `ApplicationSettings` -- `virustotal_api_key` itself is never part
 * of this shape, on the read side exactly as `SaveSettingsResult`
 * never echoes it back on the write side.
 */
export interface GetSettingsResult {
  theme: string;
  export_directory: string;
  virustotal_api_key_configured: boolean;
}

export type ListInvestigationsResult = InvestigationSummary[];

export interface DeleteInvestigationResult {
  investigation_id: number;
  deleted: boolean;
}

export type SearchInvestigationsResult = InvestigationSummary[];

export interface AnalyzeReportResult {
  correlation_id: string;
  investigation: InvestigationSummary;
  existing: boolean;
  options: AnalysisOptions;
}

export interface ExportReportResult {
  investigation_id: number;
  export_format: ExportFormat;
  output_path: string;
}

/** Mirrors `ExportInvestigationsCsvCommandHandler.handle`'s `ok(...)` payload. */
export interface ExportInvestigationsCsvResult {
  output_path: string;
  row_count: number;
}

/** Mirrors `ThreatIntelService.lookup_indicator`'s VT-shaped, untyped dict. */
export type EnrichIocResult = Record<string, unknown>;

// ---------------------------------------------------------------------------
// Command name -> {payload, result} map, consumed by runCommand<K>()
// ---------------------------------------------------------------------------

export interface CommandContracts {
  get_investigation: {
    payload: GetInvestigationPayload;
    result: GetInvestigationResult;
  };
  get_iocs: {
    payload: GetIocsPayload;
    result: GetIocsResult;
  };
  get_threat_intelligence: {
    payload: GetThreatIntelligencePayload;
    result: GetThreatIntelligenceResult;
  };
  get_timeline: {
    payload: GetTimelinePayload;
    result: GetTimelineResult;
  };
  get_investigation_risk_explanation: {
    payload: GetInvestigationRiskExplanationPayload;
    result: GetInvestigationRiskExplanationResult;
  };
  get_settings: {
    payload: GetSettingsPayload;
    result: GetSettingsResult;
  };
  save_settings: {
    payload: SaveSettingsPayload;
    result: SaveSettingsResult;
  };
  list_investigations: {
    payload: ListInvestigationsPayload;
    result: ListInvestigationsResult;
  };
  get_dashboard_summary: {
    payload: GetDashboardSummaryPayload;
    result: DashboardSummaryResult;
  };
  get_investigation_aggregate_summary: {
    payload: GetInvestigationAggregateSummaryPayload;
    result: InvestigationAggregateSummaryResult;
  };
  delete_investigation: {
    payload: DeleteInvestigationPayload;
    result: DeleteInvestigationResult;
  };
  search_investigations: {
    payload: SearchInvestigationsPayload;
    result: SearchInvestigationsResult;
  };
  analyze_report: {
    payload: AnalyzeReportPayload;
    result: AnalyzeReportResult;
  };
  export_report: {
    payload: ExportReportPayload;
    result: ExportReportResult;
  };
  export_investigations_csv: {
    payload: ExportInvestigationsCsvPayload;
    result: ExportInvestigationsCsvResult;
  };
  enrich_ioc: {
    payload: EnrichIocPayload;
    result: EnrichIocResult;
  };
}

export type CommandPayload<K extends CommandName> =
  CommandContracts[K]["payload"];
export type CommandResult<K extends CommandName> =
  CommandContracts[K]["result"];
