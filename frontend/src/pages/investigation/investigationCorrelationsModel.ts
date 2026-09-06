/**
 * Investigation Workspace — Correlations presentation model — Phase
 * 4J-6 Part 4A.
 *
 * A small, framework-free presentation layer over the existing
 * `InvestigationWorkspaceData` (`investigationWorkspaceModel.ts`,
 * Phase 4J-5) -- mirrors that module's own "plain functions and types
 * only" boundary so this can be unit-tested independently of any
 * component, and never becomes a second normalization layer of its
 * own (task brief §6/§17: "Do not move normalization into
 * components").
 *
 * # Where correlations come from (Phase 4J-6 update)
 *
 * `InvestigationWorkspaceData` now carries a real `correlations` field
 * (`investigationWorkspaceModel.ts`), sourced from
 * `GetInvestigationCommandHandler` -> `CorrelationService` ->
 * `InvestigationCorrelationDTO` (`app/application/handlers.py` /
 * `dto.py`). `iocsByType` (each indicator standing alone with its own
 * `value` and `tiState`) and `rawThreatIntelligence` (the provider
 * payload, deliberately kept opaque -- see `ProviderDetail.tsx`'s own
 * doc comment) still express no relationship of their own; they are
 * used below only to distinguish "no real data loaded at all"
 * (`"unavailable"`) from "real data loaded, no explicit relationship"
 * (`"empty"`).
 *
 * Two IOCs appearing in the same investigation, sharing a type, being
 * adjacent in a list, or an IOC merely having TI data are still
 * explicitly NOT relationships (task brief §4) -- inferring one from
 * any of those would be exactly the fabricated correlation this
 * module exists to avoid. `extractExplicitCorrelations` below reads
 * only the backend's own already-computed `correlations` field; it
 * never derives one independently, and no other module should either.
 *
 * # The three states kept distinguishable (task brief §9/§10)
 *
 * - `"unavailable"` -- neither `iocsByType` nor `rawThreatIntelligence`
 *   loaded successfully, so there is no real data to have looked for
 *   an explicit correlation in. Never silently converted into an
 *   empty result, which would misrepresent "we didn't check" as "we
 *   checked and found none".
 * - `"empty"` -- real data is present, but it contains no explicit
 *   relationship. This is the honest, expected result under the
 *   current data model (see above) -- never worded as "clean" or
 *   "no threats found" (task brief §9): an empty correlation result
 *   says nothing about whether the investigation's indicators are
 *   malicious.
 * - `"available"` -- one or more real, explicit relationships were
 *   found. Reachable as of Phase 4J-6: `data.correlations` is now
 *   populated whenever `CorrelationService` finds at least one
 *   deterministic relationship in the investigation's own IOCs/TI data.
 */

import type { InvestigationWorkspaceData } from "./investigationWorkspaceModel";

/** One real, explicit relationship between two entities already
 * present in the investigation's own data. Every field here must come
 * from data the model actually carries -- never a fabricated `type`,
 * `source`, or `target` (task brief §6: "ONLY use fields supported by
 * the actual data"). */
export interface InvestigationCorrelation {
  /** The real relationship's own kind, e.g. as named by the data that
   * supplied it -- never a generic invented label. */
  readonly relationshipType: string;
  readonly source: string;
  readonly target: string;
  /** Optional supporting context, only when the underlying data
   * actually supplies one. */
  readonly context?: string;
}

export type InvestigationCorrelationsResult =
  | { readonly status: "unavailable" }
  | { readonly status: "empty" }
  | { readonly status: "available"; readonly correlations: readonly InvestigationCorrelation[] };

/**
 * Reads explicit relationships out of the normalized workspace data.
 *
 * Phase 4J-6: `InvestigationWorkspaceData` now carries a real
 * `correlations` field (`GetInvestigationCommandHandler` ->
 * `CorrelationService`, `investigationWorkspaceModel.ts`), so this no
 * longer needs to honestly return `[]` unconditionally -- it returns
 * that field directly. This remains the one place a relationship
 * field is read from; no other module should reconstruct correlation
 * logic of its own. Still never infers a relationship from proximity,
 * shared IOC type, or any other non-explicit signal -- every item in
 * `data.correlations` already came from `CorrelationService`'s
 * deterministic, explicit-only output (see that service's own
 * docstring), so there is nothing to infer here.
 */
function extractExplicitCorrelations(
  data: InvestigationWorkspaceData,
): readonly InvestigationCorrelation[] {
  return data.correlations;
}

/**
 * Derives the Correlations section's presentation state from the
 * already-normalized workspace data. Callers only invoke this once
 * `InvestigationWorkspaceData` actually exists (`useInvestigation()`'s
 * `"success"`/`"partial"` states), matching every other workspace
 * region's convention.
 */
export function deriveInvestigationCorrelations(
  data: InvestigationWorkspaceData,
): InvestigationCorrelationsResult {
  if (data.iocsByType === null && data.rawThreatIntelligence === null) {
    return { status: "unavailable" };
  }

  const correlations = extractExplicitCorrelations(data);
  if (correlations.length === 0) {
    return { status: "empty" };
  }

  return { status: "available", correlations };
}
