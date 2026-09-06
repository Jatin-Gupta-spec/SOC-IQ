/**
 * Investigation Workspace — Threat Intel typed verdict presentation
 * helpers — Phase 4K-3.
 *
 * # Why this file changed shape
 *
 * Phase 4K Part 1/2 (this file's original form, predating the
 * unrelated "4K-1"/"4K-2" checkpoint numbering used from here on)
 * recovered verdict information by parsing the raw
 * `threat_intelligence` payload's own legacy `verdict` string field
 * (`"Malicious"/"Suspicious"/"Clean"/"Not Found"`,
 * `app/threat_intel/service.py::ThreatIntelService._format_verdict()`)
 * and matching it back to a persisted indicator by exact
 * identity-string equality (`matchIndicatorVerdicts()`, e.g.
 * `results["hashes"][0]["sha256"] === indicator.value`). That was the
 * only real, non-fabricated verdict signal available to the frontend
 * at the time -- the normalized model attached nothing but `tiState`
 * to each indicator.
 *
 * Phase 4K-1 (backend, `app/threat_intel/verdict_from_persisted.py`)
 * and Phase 4K-2 (frontend model) since made a better signal
 * available: a typed `Verdict.value` is now attached directly to each
 * normalized indicator as `typedVerdict`
 * (`InvestigationWorkspaceIndicator`, `investigationWorkspaceModel.ts`)
 * -- no raw-payload parsing, no identity-string matching, no legacy
 * capitalized strings, no risk of a match silently failing because a
 * provider's identity field changed shape. Phase 4K-3 migrates this
 * module to that field. There must be exactly one authoritative
 * verdict source for the investigation workspace UI, never two
 * independent ones computing the same thing from different data (the
 * checkpoint's own audit flagged this as the central risk to resolve
 * before touching the UI) -- so the old raw-payload-based
 * `countVerdicts()`/`matchIndicatorVerdicts()`/`isVerdictString()` are
 * removed entirely here, not kept alongside the new functions.
 * Keeping both would silently reintroduce the second source of truth
 * this phase exists to eliminate, and would let a legacy `"Clean"`
 * raw string disagree with a real `typedVerdict: "not_found"` with no
 * way for either presentation layer to know.
 *
 * `typedVerdict` is a *sibling* of `tiState`, never a replacement:
 * `tiState` answers "did the lookup succeed?"; this module's exports
 * answer "what did the provider conclude?" (see
 * `InvestigationWorkspaceIndicator`'s own doc comment,
 * `investigationWorkspaceModel.ts`). Both remain independently visible
 * in `InvestigationThreatIntel.tsx`, each from its own field on the
 * same indicator -- never merged, and never inferred from one
 * another. An `enriched` indicator with `typedVerdict: null` (real
 * lookup, no honest classification yet) and a `not_enriched` indicator
 * with `typedVerdict: null` (no lookup at all) both simply omit that
 * indicator from every count/list below -- this module cannot and
 * does not distinguish those two cases; that distinction is `tiState`'s
 * job alone.
 *
 * # What this module still does NOT do
 *
 * - Never fabricates a verdict: `typedVerdict === null` (no honest
 *   classification available for that indicator) is simply omitted
 *   from every count and list here, never coerced into `clean`,
 *   `not_found`, or a zero placeholder standing in for a real value.
 * - Never invents a provider identity or label. `typed_verdicts`
 *   carries no provider field (confirmed by reading
 *   `app/threat_intel/verdict_from_persisted.py` and
 *   `GetThreatIntelligenceResult`/`InvestigationTypedVerdicts`
 *   directly) -- Part 4K-1's old "Provider: VirusTotal" label was a
 *   true statement about the raw-payload path (only VT actually
 *   populates it) but has no equivalent real field on this path, so
 *   it is not carried over into the typed-verdict presentation.
 * - Never invents a fifth verdict category, and no longer needs an
 *   "unrecognized" bucket. `TypedVerdict` (`shared/api/types.ts`) is a
 *   closed, strongly-typed union of exactly the four real values
 *   `build_investigation_typed_verdicts()` can produce -- there is no
 *   untyped string here that could fail to match one of them.
 */

import { PERSISTED_IOC_TYPES, TYPED_VERDICTS, type PersistedIocType, type TypedVerdict } from "../../shared/api/types";
import type { InvestigationWorkspaceIocsByType } from "./investigationWorkspaceModel";

export interface VerdictGroup {
  readonly verdict: TypedVerdict;
  readonly count: number;
}

export interface VerdictCounts {
  readonly groups: readonly VerdictGroup[];
  readonly total: number;
}

/**
 * Counts real `typedVerdict` values across every persisted indicator
 * in `iocsByType`. Returns `null` only when there is no per-indicator
 * breakdown at all (mirrors `InvestigationThreatIntel`'s own
 * `iocsByType === null` handling) -- an honest "nothing to count"
 * rather than a fabricated zero.
 *
 * An indicator whose `typedVerdict` is `null` is skipped entirely --
 * `total` here means "indicators with a real typed verdict", not
 * "indicators examined" (that count already exists, unchanged, as
 * `countTiStates()`'s own `total` in this same tab, from `tiState`
 * alone).
 */
export function countTypedVerdicts(iocsByType: InvestigationWorkspaceIocsByType | null): VerdictCounts | null {
  if (iocsByType === null) {
    return null;
  }

  const byVerdict: Partial<Record<TypedVerdict, number>> = {};
  let total = 0;

  for (const iocType of PERSISTED_IOC_TYPES) {
    const indicators = iocsByType[iocType];
    if (indicators === undefined) {
      continue;
    }
    for (const indicator of indicators) {
      if (indicator.typedVerdict === null) {
        continue;
      }
      byVerdict[indicator.typedVerdict] = (byVerdict[indicator.typedVerdict] ?? 0) + 1;
      total += 1;
    }
  }

  const groups = TYPED_VERDICTS.filter((verdict) => (byVerdict[verdict] ?? 0) > 0).map((verdict) => ({
    verdict,
    count: byVerdict[verdict] as number,
  }));

  return { groups, total };
}

export interface IndicatorVerdict {
  readonly type: PersistedIocType;
  readonly value: string;
  readonly verdict: TypedVerdict;
}

/**
 * Lists one `IndicatorVerdict` per persisted indicator that carries a
 * real `typedVerdict` -- a direct read of already-normalized data, not
 * a match/lookup. Phase 4K Part 2's `matchIndicatorVerdicts()` needed
 * identity-string matching only because the raw payload had no
 * indicator-identity relationship the normalized model itself
 * carried; `typedVerdict` is attached to the exact indicator it
 * describes by `normalizeInvestigationWorkspace()` already, so no
 * matching step exists here to fail or silently miss anything.
 *
 * An indicator whose `typedVerdict` is `null` is simply omitted, never
 * given a fabricated verdict. Returns `null` only when there is no
 * per-indicator breakdown at all (`iocsByType === null`) -- an empty
 * array is a distinct, honest "nothing classified yet" result once
 * real indicator data exists (same distinction `countTypedVerdicts()`
 * above preserves).
 */
export function listIndicatorVerdicts(
  iocsByType: InvestigationWorkspaceIocsByType | null,
): readonly IndicatorVerdict[] | null {
  if (iocsByType === null) {
    return null;
  }

  const results: IndicatorVerdict[] = [];

  for (const iocType of PERSISTED_IOC_TYPES) {
    const indicators = iocsByType[iocType];
    if (indicators === undefined) {
      continue;
    }
    for (const indicator of indicators) {
      if (indicator.typedVerdict !== null) {
        results.push({ type: iocType, value: indicator.value, verdict: indicator.typedVerdict });
      }
    }
  }

  return results;
}
