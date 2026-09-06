/**
 * Investigation Workspace normalization layer — Phase 4J-5.
 *
 * The smallest framework-independent transform from the three verified
 * command results (`get_investigation` / `get_iocs` /
 * `get_threat_intelligence`, `shared/api/types.ts`) into one stable
 * shape the eventual Investigation Workspace UI will render. Plain
 * functions and types only — no React, no hooks, no state — so it can
 * be unit-tested independently of `useInvestigation` and of any
 * component, mirroring the existing `dashboardViewModel.ts` boundary
 * (domain data -> view model -> components).
 *
 * # Why this exists as a separate module from `useInvestigation`
 *
 * `useInvestigation` (Phase 4J-4) is the fetch/state-management layer:
 * it owns loading/retry/cancellation and exposes the three raw
 * per-command results (`investigation`, `iocs`, `threatIntelligence`)
 * largely as-is. It intentionally does *not* merge IOC values with
 * their TI states, or decide what "the Workspace's data" looks like as
 * a single object — that shaping is what this module does instead, so
 * the fetch layer stays responsible only for fetching (task brief
 * §9) and this layer stays responsible only for shaping data that has
 * already been returned. Nothing here calls `runCommand()`, and no new
 * command or transport is introduced (task brief §10).
 *
 * # What "normalized" means here — and what it deliberately does not
 *
 * This is a *reshape*, not a reinterpretation:
 *
 * - `investigation_id` / `report_name` / `analyzed_at` / `status` /
 *   `risk_score` / `confidence` are carried over unchanged from
 *   `GetInvestigationResult` (`InvestigationSummary`,
 *   `shared/api/types.ts`).
 * - `severity` is carried over unchanged, including the `"NOT_SCORED"`
 *   sentinel `app/analyzer.py` writes when `score_risk` was disabled
 *   (see that module's comment) — never collapsed into, or treated
 *   the same as, one of the four real LOW/MEDIUM/HIGH/CRITICAL values.
 *   Mirrors the same non-confusion `AnalysisResultSummary.tsx` already
 *   relies on for this exact sentinel.
 * - IOC values are grouped by their real persisted `PersistedIocType`
 *   (`shared/api/types.ts`, mirroring `app/extractor.py`'s ten
 *   categories) — the same union `get_iocs` and `get_threat_intelligence`
 *   both key on, so no second IOC-type vocabulary is invented.
 * - Each indicator's TI state is attached from `states`
 *   (`InvestigationIndicatorStates`) by exact `(ioc_type, value)`
 *   lookup — never recomputed, inferred, or defaulted to a "safe"
 *   guess. One of the six canonical `TiState` values
 *   (`ENRICHED`/`NOT_ENRICHED`/`NO_API_KEY`/`PROVIDER_ERROR`/
 *   `INCOMPLETE_CHECK`/`UNSUPPORTED_TYPE`) if `states` has an entry for
 *   that exact indicator, or `null` if it does not — `null` is a
 *   seventh, distinct condition ("we have no TI classification for
 *   this indicator at all") that must never be confused with any of
 *   the six real states, and specifically never with `"not_enriched"`.
 * - Each indicator's typed verdict (Phase 4K-2) is attached the same
 *   way, from `typed_verdicts` (`InvestigationTypedVerdicts`) by exact
 *   `(ioc_type, value)` lookup — one of the four `TypedVerdict` values
 *   the backend actually classified it as, or `null` for every "we
 *   have no honest verdict for this indicator" case (see
 *   `InvestigationWorkspaceIndicator`'s doc comment). It is a sibling
 *   of `tiState`, never a replacement, and never derived from
 *   `tiState`, from `rawThreatIntelligence`, or from anything else —
 *   only from the backend's own `typed_verdicts` field. This model
 *   does not yet expose the typed verdict through any new top-level
 *   or rendering-facing shape beyond this per-indicator field;
 *   presentation is Phase 4K-3's job.
 * - `rawThreatIntelligence` is `GetThreatIntelligenceResult`'s
 *   `threat_intelligence` field, exposed unchanged — no VirusTotal
 *   schema is fabricated on top of it (task brief §3/§7, mirroring
 *   `types.ts`'s own `Record<string, unknown>` choice for that field).
 * - `correlations` (Phase 4J-6) is `GetInvestigationResult["correlations"]`
 *   carried over with a pure field-rename to this module's camelCase
 *   convention — no relationship is added, dropped, or reordered, and
 *   none is inferred here; every item already came from
 *   `CorrelationService`'s deterministic, explicit-only output.
 *
 * # The four states this module keeps distinguishable (task brief §4)
 *
 * - **Missing data**: `iocs === null` (no successful `get_iocs`
 *   response yet — fetch pending or failed) and, separately,
 *   `rawThreatIntelligence === null` (no successful
 *   `get_threat_intelligence` response yet). Neither is ever
 *   backfilled with a fabricated `{}` standing in for "not fetched".
 * - **Empty IOC type**: a `PersistedIocType` key that *is* present on
 *   the backend's `IocsByType` with a zero-length array — kept as
 *   `[]` in the normalized output, distinct from the type being
 *   entirely absent from the backend response (see below). Never
 *   read as, or converted to, "clean"/"not malicious" (task brief §5)
 *   — an empty IOC list only ever means "no indicators of this type
 *   were extracted", nothing about any indicator's disposition.
 * - **Unsupported IOC type**: not a *shape* this module invents —
 *   it is one of the six canonical `TiState` values,
 *   `"unsupported_type"`, that the backend
 *   (`app/services/threat_intel_state.py::TI_STATE_UNSUPPORTED_TYPE`)
 *   already assigns per-indicator for the six `PersistedIocType`
 *   categories `ThreatIntelService` never enriches (everything outside
 *   `ENRICHABLE_IOC_TYPES` — `sha256`/`ipv4`/`domains`/`urls`). Reused
 *   as-is via the exact-lookup rule above, not recomputed from
 *   `ENRICHABLE_IOC_TYPES` here (that would duplicate backend business
 *   logic that could diverge from it — task brief §7).
 * - A `PersistedIocType` key **absent** from the backend's `IocsByType`
 *   entirely (no key at all, not even `[]`) is left absent from
 *   `iocsByType` here too — never synthesized as `[]`. Backfilling
 *   every one of the ten categories would erase the distinction
 *   between "extractor found zero of this type" and "this key was
 *   never in the response", a distinction this module has no basis to
 *   collapse (task brief §6's fabrication warning covers this shape
 *   choice as much as it covers TI states).
 *
 * # Determinism
 *
 * `PERSISTED_IOC_TYPES`' fixed order (`shared/api/types.ts`) drives
 * iteration, and each type's indicator array preserves the backend's
 * own array order — so normalizing the same input twice always
 * produces deeply-equal output, with no dependency on JS object-key
 * enumeration order for correctness.
 */

import type {
  GetInvestigationResult,
  GetInvestigationRiskExplanationResult,
  InvestigationIndicatorStates,
  InvestigationTypedVerdicts,
  IocCategoryContribution,
  IocSignificanceByType,
  IocsByType,
  PersistedIocType,
  TiState,
  TimelineEvent,
  TypedVerdict,
} from "../../shared/api/types";
import { PERSISTED_IOC_TYPES } from "../../shared/api/types";
import type { InvestigationCorrelation } from "./investigationCorrelationsModel";

/**
 * The raw threat-intelligence sub-fetch shape this module consumes —
 * `GetThreatIntelligenceResult`'s two data fields, the same pairing
 * `UseInvestigationThreatIntelligence` (`useInvestigation.ts`) already
 * exposes. Declared locally rather than imported from
 * `useInvestigation.ts` so this module has no dependency on the fetch
 * layer (task brief §8) — the two shapes are structurally identical by
 * design, not by import.
 */
export interface InvestigationWorkspaceThreatIntelligenceInput {
  readonly raw: Record<string, unknown>;
  readonly states: InvestigationIndicatorStates;
  /** Optional, mirroring `GetThreatIntelligenceResult["typed_verdicts"]`
   * (Phase 4K-1): absent when normalizing an older backend response
   * that predates the field. Handled identically to `undefined` `iocs`/
   * `threatIntelligence` elsewhere in this module -- never backfilled
   * with a fabricated `{}`. */
  readonly typedVerdicts?: InvestigationTypedVerdicts;
}

/** One persisted indicator, with its TI classification and typed
 * verdict attached.
 *
 * `tiState` is `null` when `states` has no entry for this exact
 * `(ioc_type, value)` pair — distinct from all six real `TiState`
 * values (see module doc comment).
 *
 * `typedVerdict` (Phase 4K-2) is a *sibling* of `tiState`, not a
 * replacement for it — `tiState` answers "what happened with the
 * lookup?" while `typedVerdict` answers "what did the provider/domain
 * model determine?" (`app/threat_intel/models.py::Verdict`'s own
 * distinction). It is `null` whenever the backend has no honest
 * classification to offer for this exact `(ioc_type, value)` pair —
 * an explicit `null` in `typed_verdicts`, no entry at all, or
 * `typed_verdicts` missing from the response entirely (an older
 * backend) — all three collapse to this module's one "no typed
 * verdict available" value, the same convention `tiState`'s `null`
 * already establishes for its own three analogous "no data" cases.
 * Never inferred from `tiState`, from `rawThreatIntelligence`, or from
 * anything other than the backend's own `typed_verdicts` field. */
export interface InvestigationWorkspaceIndicator {
  readonly value: string;
  readonly tiState: TiState | null;
  readonly typedVerdict: TypedVerdict | null;
}

/** IOC values grouped by their real persisted type, each with its TI
 * state attached. A `PersistedIocType` key is present here if and only
 * if it was present on the backend's `IocsByType` (possibly with an
 * empty array) — never synthesized for a type the backend omitted. */
export type InvestigationWorkspaceIocsByType = Partial<
  Record<PersistedIocType, readonly InvestigationWorkspaceIndicator[]>
>;

/** `get_iocs`'s additive `significance` field (PD-08-P3), carried over
 * unchanged (no field rename needed -- `weight`/`significance` are
 * already this module's own casing convention). One entry per real
 * `PersistedIocType` category present on the investigation, mirroring
 * `IocSignificanceByType`'s own doc comment (`shared/api/types.ts`)
 * exactly -- never one entry per individual indicator value, and
 * never a category the backend didn't include. This is a pure,
 * backend-owned pass-through: it is never computed, reinterpreted, or
 * recalculated here from `RiskScoringEngine.IOC_WEIGHTS` or anything
 * else. */
export type InvestigationWorkspaceIocSignificance = IocSignificanceByType;

/** One real timeline event (A4-P2-P3 Part 5B), a pure field-rename of
 * `TimelineEvent` (`shared/api/types.ts`) to this module's camelCase
 * convention -- the same treatment `correlations` already gets below
 * (`relationship_type` -> `relationshipType`). No field is added,
 * dropped, reordered, or reinterpreted: `eventType` and `semantics`
 * stay the backend's own strings, unchanged, for the same
 * backend-owns-the-vocabulary reason `TimelineEvent["event_type"]`'s
 * own doc comment gives. */
export interface InvestigationWorkspaceTimelineEvent {
  readonly eventId: string;
  readonly investigationId: number;
  readonly eventType: string;
  readonly timestamp: string;
  readonly source: string;
  readonly summary: string;
  readonly metadata: Record<string, unknown>;
  readonly semantics: string;
}

/**
 * The stable Investigation Workspace data contract: everything the
 * future Workspace UI needs from one investigation, already merged
 * across the three source commands.
 */
export interface InvestigationWorkspaceData {
  readonly investigationId: number | null;
  readonly reportName: string;
  readonly analyzedAt: string;
  readonly status: string;
  readonly riskScore: number;
  /** Carried over verbatim, including the `"NOT_SCORED"` sentinel. */
  readonly severity: string;
  readonly confidence: number;
  /** `null` when no successful `get_iocs` response has been normalized
   * (missing data). `{}` is a real, distinct value: a successful
   * response that included no IOC type keys at all. */
  readonly iocsByType: InvestigationWorkspaceIocsByType | null;
  /** `get_iocs`'s additive `significance` field (PD-08-P3), attached
   * alongside `iocsByType` from the same `get_iocs` response -- both
   * share that command's own nullability: `null` when no successful
   * `get_iocs` response has been normalized (missing data, same
   * condition as `iocsByType === null`), and a real (possibly `{}`)
   * object once one has. Never desynchronized from `iocsByType`: both
   * fields are populated from the exact same `get_iocs` fetch, never
   * from a second/separate request (see `GetIocsCommandHandler`'s own
   * docstring, `app/application/handlers.py`, PD-08-P3, and this
   * module's own "no second fetch" convention). A `PersistedIocType`
   * key present in `iocsByType` is not guaranteed to also be present
   * here on an older backend response that predates PD-08-P3 --
   * callers must not assume every `iocsByType` key has a matching
   * `iocSignificance` entry.
   *
   * Declared optional (`iocSignificance?:`), for the same
   * smallest-footprint reason `timeline?:`/`riskExplanation?:` are
   * (see those fields' own doc comments) -- `normalizeInvestigationWorkspace()`
   * always sets it (to `null` or a real object, never `undefined`) on
   * every call, so at runtime it behaves exactly like a required
   * field. It is typed optional here only so the pre-existing
   * `InvestigationWorkspaceData` object literals already written
   * across this workspace's presentation test files keep compiling
   * without every one of them needing a same-day, unrelated edit
   * purely to add `iocSignificance: null`. */
  readonly iocSignificance?: InvestigationWorkspaceIocSignificance | null;
  /** `GetThreatIntelligenceResult["threat_intelligence"]`, unchanged.
   * `null` when no successful `get_threat_intelligence` response has
   * been normalized (missing data) — distinct from a successful
   * response whose payload happens to be `{}`. */
  readonly rawThreatIntelligence: Record<string, unknown> | null;
  /** `get_investigation`'s additive `correlations` field (Phase 4J-6),
   * carried over from `GetInvestigationResult["correlations"]` with
   * each item's snake_case wire fields renamed to this module's
   * camelCase convention (`relationship_type` -> `relationshipType`,
   * `source`/`target`/`context` unchanged). Always a real array —
   * `CorrelationService.correlate()` (via `GetInvestigationCommandHandler`)
   * always returns a `CorrelationReport`, safe to display even when
   * empty (see that service's own docstring) — so unlike `iocsByType`/
   * `rawThreatIntelligence` this is never `null`: `investigation` is
   * required by this function's own contract, and `correlations` loads
   * in the same request as every other identity/risk field on it. */
  readonly correlations: readonly InvestigationCorrelation[];
  /** `get_timeline`'s events (A4-P2-P3 Part 3/5A), carried over with
   * the same camelCase field-rename `correlations` gets, in the exact
   * order the backend returned them -- never re-sorted here (mirrors
   * `GetTimelineResult`'s own oldest -> newest ordering contract, see
   * `TimelineEvent`'s doc comment). `null` when no successful
   * `get_timeline` response has been normalized (missing data,
   * `UseInvestigationData["timeline"]` is `null` or `undefined`) --
   * distinct from `[]`, a successful response that genuinely contains
   * no events. No event is fabricated, dropped, or given an invented
   * timestamp: every item here came from the backend's own `events`
   * array, unchanged apart from the field-rename.
   *
   * Declared optional (`timeline?:`), unlike every other field on this
   * interface, for the same reason `UseInvestigationData["timeline"]`
   * is (see that field's own doc comment, `useInvestigation.ts`):
   * `normalizeInvestigationWorkspace()` always sets it (to `null` or a
   * real array, never `undefined`) on every call, so at runtime it
   * behaves exactly like a required field. It is typed optional here
   * only so the pre-existing `InvestigationWorkspaceData` object
   * literals already written across this workspace's presentation
   * test files (Part 1C/1D/2A/3A/4A, all out of Part 5B's scope --
   * presentation is Part 5C's job) keep compiling without every one
   * of them needing a same-day, unrelated edit purely to add
   * `timeline: null`. */
  readonly timeline?: readonly InvestigationWorkspaceTimelineEvent[] | null;
  /** `get_investigation_risk_explanation`'s result (PD-08-P1/PD-08-P2),
   * carried over with the same camelCase field-rename `correlations`/
   * `timeline` get -- no field is dropped, reordered, or reinterpreted,
   * and `ioc_categories` keeps the backend's own deterministic
   * ordering (highest point contribution first, tie-broken by category
   * key -- `RiskExplanationDTO`'s own doc comment) unchanged. `null`
   * when no successful `get_investigation_risk_explanation` response
   * has been normalized (missing data, `UseInvestigationData["riskExplanation"]`
   * is `null` or `undefined`) -- unlike `timeline`, there is no
   * separate "genuinely empty" case to distinguish here (see that
   * field's own doc comment on `useInvestigation.ts`): the backend
   * always returns a complete explanation for any investigation it is
   * given.
   *
   * Declared optional (`riskExplanation?:`), for the same
   * smallest-footprint reason `timeline?:` is (see that field's own
   * doc comment) -- this module always sets it (to `null` or a real
   * object, never `undefined`) on every call. */
  readonly riskExplanation?: InvestigationWorkspaceRiskExplanation | null;
}

/** One item of `InvestigationWorkspaceRiskExplanation.iocCategories` --
 * mirrors `IocCategoryContribution` (`shared/api/types.ts`) with this
 * module's camelCase field-rename, no other change. */
export interface InvestigationWorkspaceIocCategoryContribution {
  readonly iocType: string;
  readonly iocTypeTitle: string;
  readonly count: number;
  readonly weight: number;
  readonly significance: string;
  readonly points: number;
}

/** `get_investigation_risk_explanation`'s result (PD-08-P1), renamed to
 * this module's camelCase convention field-for-field. See
 * `InvestigationWorkspaceData.riskExplanation`'s doc comment for the
 * nullability contract. */
export interface InvestigationWorkspaceRiskExplanation {
  readonly investigationId: number | null;
  readonly reportName: string;
  readonly score: number;
  readonly severity: string;
  readonly confidence: number;
  readonly iocScore: number;
  readonly threatIntelScore: number;
  readonly cveScore: number;
  readonly iocCategories: readonly InvestigationWorkspaceIocCategoryContribution[];
  readonly iocBreakdownVerified: boolean;
  readonly threatIntelState: string;
  readonly threatIntelMessage: string;
  readonly threatIntelShortLabel: string;
  readonly threatIntelRequested: number;
  readonly threatIntelSucceeded: number;
  readonly threatIntelMaliciousHashCount: number;
  readonly threatIntelSuspiciousHashCount: number;
  readonly correlationEvaluated: boolean;
  readonly correlationRelationshipCount: number;
  readonly correlationSummary: string;
  readonly engineReasons: readonly string[];
  readonly narrative: readonly string[];
  readonly warnings: readonly string[];
}

function lookupTiState(
  states: InvestigationIndicatorStates | null,
  iocType: PersistedIocType,
  value: string,
): TiState | null {
  return states?.[iocType]?.[value] ?? null;
}

/** Mirrors `lookupTiState` for the additive `typed_verdicts` field.
 * `typedVerdicts` itself may be `undefined` (field absent from an
 * older backend response); `?.[iocType]?.[value]` short-circuits to
 * `undefined` in that case exactly as it does for a present-but-
 * type-absent or present-but-value-absent lookup, and `?? null`
 * collapses all of those, plus a genuine backend `null`, to this
 * module's one "no typed verdict" value (see
 * `InvestigationWorkspaceIndicator`'s doc comment). */
function lookupTypedVerdict(
  typedVerdicts: InvestigationTypedVerdicts | undefined,
  iocType: PersistedIocType,
  value: string,
): TypedVerdict | null {
  return typedVerdicts?.[iocType]?.[value] ?? null;
}

function normalizeIocsByType(
  iocs: IocsByType | null,
  states: InvestigationIndicatorStates | null,
  typedVerdicts: InvestigationTypedVerdicts | undefined,
): InvestigationWorkspaceIocsByType | null {
  if (iocs === null) {
    return null;
  }

  const result: InvestigationWorkspaceIocsByType = {};

  for (const iocType of PERSISTED_IOC_TYPES) {
    const values = iocs[iocType];
    if (values === undefined) {
      // The backend never included this key -- leave it absent here
      // too, rather than fabricating an empty array for it.
      continue;
    }

    result[iocType] = values.map((value) => ({
      value,
      tiState: lookupTiState(states, iocType, value),
      typedVerdict: lookupTypedVerdict(typedVerdicts, iocType, value),
    }));
  }

  return result;
}

/**
 * Renames one backend `TimelineEvent`'s fields to this module's
 * camelCase convention -- no reordering, no re-sorting, no dropped or
 * invented fields (see `InvestigationWorkspaceTimelineEvent`'s doc
 * comment).
 */
function normalizeTimelineEvent(event: TimelineEvent): InvestigationWorkspaceTimelineEvent {
  return {
    eventId: event.event_id,
    investigationId: event.investigation_id,
    eventType: event.event_type,
    timestamp: event.timestamp,
    source: event.source,
    summary: event.summary,
    metadata: event.metadata,
    semantics: event.semantics,
  };
}

/**
 * Normalizes `get_timeline`'s events into this module's camelCase
 * convention, preserving the backend's own ordering exactly (task
 * brief: "no frontend re-sorting"). `timeline === null` (or
 * `undefined`, matching `UseInvestigationData["timeline"]`'s own
 * optionality) means no successful `get_timeline` response has been
 * normalized yet -- distinct from a real, successful `[]`, which is
 * mapped straight through as `[]`. Never fabricates an event or a
 * timestamp for either case.
 */
function normalizeTimeline(
  timeline: readonly TimelineEvent[] | null | undefined,
): readonly InvestigationWorkspaceTimelineEvent[] | null {
  if (timeline === null || timeline === undefined) {
    return null;
  }
  return timeline.map(normalizeTimelineEvent);
}

/**
 * Renames one backend `IocCategoryContribution`'s fields to this
 * module's camelCase convention -- no reordering, no recomputation
 * (see `InvestigationWorkspaceIocCategoryContribution`'s doc comment).
 */
function normalizeIocCategoryContribution(
  category: IocCategoryContribution,
): InvestigationWorkspaceIocCategoryContribution {
  return {
    iocType: category.ioc_type,
    iocTypeTitle: category.ioc_type_title,
    count: category.count,
    weight: category.weight,
    significance: category.significance,
    points: category.points,
  };
}

/**
 * Normalizes `get_investigation_risk_explanation`'s result into this
 * module's camelCase convention, field-for-field, preserving the
 * backend's own `ioc_categories` ordering exactly (task brief §6: "do
 * not calculate risk categories client-side"). `riskExplanation ===
 * null`/`undefined` means no successful
 * `get_investigation_risk_explanation` response has been normalized
 * yet -- see `InvestigationWorkspaceData.riskExplanation`'s doc
 * comment. Never fabricates a narrative line, warning, or category for
 * either case.
 */
function normalizeRiskExplanation(
  riskExplanation: GetInvestigationRiskExplanationResult | null | undefined,
): InvestigationWorkspaceRiskExplanation | null {
  if (riskExplanation === null || riskExplanation === undefined) {
    return null;
  }
  return {
    investigationId: riskExplanation.investigation_id,
    reportName: riskExplanation.report_name,
    score: riskExplanation.score,
    severity: riskExplanation.severity,
    confidence: riskExplanation.confidence,
    iocScore: riskExplanation.ioc_score,
    threatIntelScore: riskExplanation.threat_intel_score,
    cveScore: riskExplanation.cve_score,
    iocCategories: riskExplanation.ioc_categories.map(normalizeIocCategoryContribution),
    iocBreakdownVerified: riskExplanation.ioc_breakdown_verified,
    threatIntelState: riskExplanation.threat_intel_state,
    threatIntelMessage: riskExplanation.threat_intel_message,
    threatIntelShortLabel: riskExplanation.threat_intel_short_label,
    threatIntelRequested: riskExplanation.threat_intel_requested,
    threatIntelSucceeded: riskExplanation.threat_intel_succeeded,
    threatIntelMaliciousHashCount: riskExplanation.threat_intel_malicious_hash_count,
    threatIntelSuspiciousHashCount: riskExplanation.threat_intel_suspicious_hash_count,
    correlationEvaluated: riskExplanation.correlation_evaluated,
    correlationRelationshipCount: riskExplanation.correlation_relationship_count,
    correlationSummary: riskExplanation.correlation_summary,
    engineReasons: [...riskExplanation.engine_reasons],
    narrative: [...riskExplanation.narrative],
    warnings: [...riskExplanation.warnings],
  };
}

/**
 * Builds the Investigation Workspace's normalized data contract from
 * the four already-fetched command results. `investigation` is
 * required (this module has no notion of "no investigation yet" — a
 * caller without a loaded investigation, e.g. `useInvestigation` in
 * its `"loading"`/`"notFound"`/`"error"` states, should not call this
 * at all). `iocs`, `threatIntelligence`, and `timeline` are each
 * independently nullable, matching `UseInvestigationData`'s own
 * per-section nullability (`useInvestigation.ts`) for the same
 * "missing data" reason documented there.
 *
 * `timeline` defaults to `null` (A4-P2-P3 Part 5B) so every
 * pre-existing three-argument call site -- in particular this
 * module's own test file's call sites, all written before the
 * Part 5 timeline work -- keeps compiling and behaving exactly as
 * before, without a same-day, unrelated signature-churn edit to every
 * caller just to pass an explicit `null` for a section that was never
 * fetched in those cases anyway.
 */
export function normalizeInvestigationWorkspace(
  investigation: GetInvestigationResult,
  iocs: IocsByType | null,
  threatIntelligence: InvestigationWorkspaceThreatIntelligenceInput | null,
  timeline: readonly TimelineEvent[] | null = null,
  riskExplanation: GetInvestigationRiskExplanationResult | null = null,
  iocSignificance: IocSignificanceByType | null = null,
): InvestigationWorkspaceData {
  return {
    investigationId: investigation.investigation_id,
    reportName: investigation.report_name,
    analyzedAt: investigation.analyzed_at,
    status: investigation.status,
    riskScore: investigation.risk_score,
    severity: investigation.severity,
    confidence: investigation.confidence,
    iocsByType: normalizeIocsByType(
      iocs,
      threatIntelligence?.states ?? null,
      threatIntelligence?.typedVerdicts,
    ),
    // Pass-through, unchanged -- see `InvestigationWorkspaceData
    // .iocSignificance`'s own doc comment for the shared-`get_iocs`-
    // response nullability contract this mirrors from `iocsByType`.
    iocSignificance,
    rawThreatIntelligence: threatIntelligence?.raw ?? null,
    correlations: investigation.correlations.map((correlation) => ({
      relationshipType: correlation.relationship_type,
      source: correlation.source,
      target: correlation.target,
      context: correlation.context,
    })),
    timeline: normalizeTimeline(timeline),
    riskExplanation: normalizeRiskExplanation(riskExplanation),
  };
}
