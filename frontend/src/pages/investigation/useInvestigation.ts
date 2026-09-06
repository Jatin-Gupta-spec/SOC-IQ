/**
 * Investigation Workspace data-fetch layer — Phase 4J-4.
 *
 * The one place that composes `get_investigation` / `get_iocs` /
 * `get_threat_intelligence` (Phase 4J-2/4J-3's already-existing
 * command contracts, `shared/api/types.ts`) behind a single hook for
 * the eventual Investigation Workspace UI. Reuses the existing
 * `runCommand<K>()` transport (`shared/api/client.ts`) exclusively —
 * no second API client, no direct `fetch()`, no new backend command.
 *
 * # Contract discrepancy found and corrected (API type discipline)
 *
 * The task brief's example return shape was
 * `investigation: GetInvestigationResult["investigation"] | null`.
 * That does not compile: `GetInvestigationResult` is a type alias for
 * `InvestigationSummary` (`export type GetInvestigationResult =
 * InvestigationSummary`, `shared/api/types.ts`) — a flat DTO with no
 * `investigation` property of its own (confirmed by reading
 * `types.ts` and its source comment, "Mirrors
 * `InvestigationSummaryDTO.to_dict()`"). There is no backend
 * inconsistency here — `GetInvestigationResult` *is* the investigation
 * summary, not a wrapper around one. The smallest correct fix is used
 * below: `investigation: GetInvestigationResult | null`. No backend or
 * `types.ts` file was touched; the "prove it before invoking API type
 * discipline" step is this comment plus the regression test in
 * `useInvestigation.test.tsx` ("returns GetInvestigationResult
 * directly, not a nested `.investigation` field").
 *
 * # Fetch behavior
 *
 * All four reads (`get_investigation` / `get_iocs` /
 * `get_threat_intelligence` / `get_timeline`, the last added in
 * A4-P2-P3 Part 5A on top of the existing three) are independent and
 * started together via `Promise.allSettled()` (never `Promise.all()`,
 * which would let one rejected sub-fetch erase three otherwise-
 * successful results). The investigation fetch is treated as
 * authoritative for existence: an `INVESTIGATION_NOT_FOUND`
 * `CommandFailedError` (the existing, established typed-error
 * mechanism — `app/application/errors.py`'s `INVESTIGATION_NOT_FOUND`
 * code, surfaced via `CommandFailedError`, `shared/api/client.ts`)
 * resolves to `"notFound"`; any other investigation failure resolves
 * to `"error"`; in both cases the IOC/TI/timeline settlements are
 * ignored (their own errors/data are irrelevant once the investigation
 * itself can't be shown). An IOC and/or TI and/or timeline failure
 * alongside investigation success resolves to `"partial"`, with each
 * failed section's error kept distinct from the others' and from the
 * surviving successful data (`iocsError` / `threatIntelligenceError` /
 * `timelineError`) — never collapsed into one generic error, and never
 * backfilled with a fabricated empty result (an empty IOC list/empty
 * timeline and a failed IOC/timeline fetch are different states and
 * stay distinguishable in the returned shape). A `get_timeline`
 * failure specifically can never fail the investigation outright (it
 * can only ever push `"success"` down to `"partial"`, the same as an
 * IOC or TI failure does today) — it is never treated as
 * investigation-authoritative the way `get_investigation` itself is.
 *
 * # Stale-response / unmount / duplicate-request protection
 *
 * Follows the same closure-scoped `cancelled` flag +
 * effect-cleanup pattern already established by this checkpoint's
 * other async-fetch hooks (`pages/analyze/useAnalysisExecution.ts`'s
 * `mountedRef`/`runId` comparison), adapted slightly: rather than a
 * single shared `mountedRef` (which React 18 Strict Mode's mandatory
 * mount→cleanup→mount dev-only double-invocation can permanently flip
 * to `false` with no code path that ever flips it back — a real trap
 * for a *shared* ref, not exercised by any existing test in this
 * checkpoint), each effect invocation gets its own `cancelled`
 * variable captured in that invocation's closure alone. Strict Mode's
 * discarded first invocation cancels only itself; the second
 * (surviving) invocation's own flag is unaffected. This also
 * subsumes true unmount (the same cleanup fires, permanently, when the
 * component actually unmounts) without a second bookkeeping
 * mechanism. A monotonically increasing `generationRef` additionally
 * guards the `investigationId`-changes-mid-flight and
 * retry-while-in-flight races (mirrors `runId` in
 * `useAnalysisExecution.ts`): a settlement only applies if it is both
 * not cancelled *and* still the current generation.
 *
 * No new dependency, no global cache (the task brief explicitly rules
 * one out for hiding duplicate requests) — Strict Mode's double
 * invocation still issues two real request cycles in dev, by design;
 * this hook only guarantees the discarded cycle's results can never be
 * observed.
 *
 * # Retry
 *
 * `retry()` starts a fresh request cycle for the same
 * `investigationId` (bumps a `retryNonce` the fetch effect depends on)
 * and resets to `"loading"` with all data/errors cleared — per the
 * task brief's own stated preference ("Prefer predictable behavior
 * over clever caching"), stale partial data is not retained across a
 * retry, so the UI can never show last-attempt data next to
 * this-attempt's loading state and have them look like the same
 * attempt.
 *
 * # Invalid investigationId
 *
 * `investigationId` is expected to already be validated by the route
 * layer (`app/investigationRouteParams.ts`'s `parseInvestigationId()`,
 * Phase 4J-3) before this hook is ever called with it — this hook does
 * not re-parse a raw route string (that would duplicate route-parsing
 * logic the brief explicitly says not to duplicate). It still
 * defensively re-checks the numeric contract that parser already
 * enforces (`Number.isSafeInteger`, `> 0`) so a caller passing an
 * invalid id by some other path can never reach the backend: the hook
 * short-circuits to `"idle"` with no `runCommand()` call at all.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { runCommand, CommandFailedError } from "../../shared/api/client";
import type {
  GetInvestigationResult,
  GetInvestigationRiskExplanationResult,
  IocSignificanceByType,
  IocsByType,
  InvestigationIndicatorStates,
  InvestigationTypedVerdicts,
  TimelineEvent,
} from "../../shared/api/types";

/** The error code `get_investigation` (`app/application/handlers.py`)
 * returns via `CommandFailedError.code` when no investigation exists
 * for the given id (`app/application/errors.py::INVESTIGATION_NOT_FOUND`).
 * Compared as a literal, per the same established pattern
 * `analysisExecutionError.ts`'s `INVALID_INPUT_CODES` already uses for
 * backend error codes -- no invented error-code enum is introduced
 * here. */
const INVESTIGATION_NOT_FOUND_CODE = "INVESTIGATION_NOT_FOUND";

export type InvestigationLoadState =
  | "idle"
  | "loading"
  | "success"
  | "notFound"
  | "error"
  | "partial";

/** Mirrors `GetThreatIntelligenceResult`'s data fields, minus the
 * redundant `investigation_id` (already carried by `investigation`
 * above once loaded). `typedVerdicts` is optional for the same reason
 * `GetThreatIntelligenceResult["typed_verdicts"]` is (Phase 4K-1/4K-2):
 * an older backend response omits the key entirely rather than
 * sending an explicit empty value. */
export interface UseInvestigationThreatIntelligence {
  readonly raw: Record<string, unknown>;
  readonly states: InvestigationIndicatorStates;
  readonly typedVerdicts?: InvestigationTypedVerdicts;
}

export interface UseInvestigationData {
  /** `null` until a successful `get_investigation` response has been
   * applied (including while `state` is `"loading"`, `"notFound"`, or
   * `"error"`). See the module doc comment's "contract discrepancy"
   * section for why this is `GetInvestigationResult` directly rather
   * than a nested `.investigation` field. */
  readonly investigation: GetInvestigationResult | null;
  /** `null` on initial load, on a failed `get_iocs` fetch (see
   * `iocsError`), or before the investigation itself has resolved --
   * never a fabricated empty object standing in for "not fetched yet"
   * vs. "fetched and genuinely empty" (those remain distinguishable:
   * a successful-but-empty `get_iocs` response is `{}`, not `null`). */
  readonly iocs: IocsByType | null;
  /** `get_iocs`'s additive `significance` field (PD-08-P3), populated
   * from the exact same `get_iocs` fetch as `iocs` above -- never a
   * second/separate request (this hook's own "no new backend command"
   * rule, module doc comment). `null` under the same conditions as
   * `iocs` (initial load, a failed `get_iocs` fetch -- see `iocsError`
   * -- or before the investigation itself has resolved), and for the
   * same "not fetched yet" vs. "fetched and genuinely `{}`" reason
   * `iocs`'s own doc comment gives.
   *
   * Declared optional (`iocSignificance?:`), for the same
   * smallest-footprint reason `timeline?:`/`riskExplanation?:` are
   * (see those fields' own doc comments) -- this hook always sets it
   * (to `null` or a real object, never `undefined`) on every code
   * path. */
  readonly iocSignificance?: IocSignificanceByType | null;
  /** `null` under the same conditions as `iocs`, for the same reason. */
  readonly threatIntelligence: UseInvestigationThreatIntelligence | null;
  /** `null` on initial load, on a failed `get_timeline` fetch (see
   * `timelineError`), or before the investigation itself has resolved --
   * same "not fetched yet" vs. "fetched and genuinely empty"
   * distinction as `iocs`/`threatIntelligence`: a successful-but-empty
   * `get_timeline` response is `[]`, not `null`. Ordering is whatever
   * `get_timeline` returned (oldest -> newest, per
   * `GetTimelineResult`'s own contract) -- never re-sorted here.
   *
   * Declared optional (`timeline?:`), unlike `iocs`/`threatIntelligence`,
   * deliberately: this hook always sets it (to `null` or an array, never
   * `undefined`) on every code path, so at runtime it behaves exactly
   * like the other two required-but-nullable fields. It is typed
   * optional here only so a pre-existing `UseInvestigationData` object
   * literal written before Part 5A (e.g. a test double for this hook,
   * out of Part 5A's scope -- workspace page/model integration is Part
   * 5B) keeps compiling without every such literal needing a
   * same-day, unrelated edit purely to add `timeline: null`. This is
   * the smallest-footprint way to add the field without expanding
   * Part 5A into files Part 5A is explicitly not scoped to touch. */
  readonly timeline?: TimelineEvent[] | null;
  /** `null` on initial load, on a failed `get_investigation_risk_explanation`
   * fetch (see `riskExplanationError`), or before the investigation
   * itself has resolved -- same "not fetched yet" vs. "fetched and
   * genuinely unavailable" distinction as `timeline`. Unlike
   * `timeline`, this section has no "genuinely empty" state to
   * distinguish: `RiskExplanationService.explain()` always returns a
   * complete `RiskExplanation` for any investigation it is given
   * (PD-08-P1's backend contract, `app/services/risk_explanation_service.py`),
   * so a `null` here only ever means "this fetch has not succeeded
   * yet", never "the backend explained that there is nothing to
   * explain".
   *
   * Declared optional (`riskExplanation?:`), for the same
   * smallest-footprint reason `timeline?:` is (see that field's own
   * doc comment) -- this hook always sets it (to `null` or a real
   * result, never `undefined`) on every code path. */
  readonly riskExplanation?: GetInvestigationRiskExplanationResult | null;
}

export interface UseInvestigationResult {
  readonly state: InvestigationLoadState;
  readonly data: UseInvestigationData;
  /** Set only when `state` is `"notFound"` or `"error"` -- the raw
   * rejection from `get_investigation` (a `CommandFailedError` or one
   * of the other `CommandClientError` subclasses / `SidecarNotConnectedError`
   * -- never re-typed or narrowed here, so a caller that needs the
   * backend's exact error code can still get it via
   * `instanceof CommandFailedError`). */
  readonly investigationError: unknown | null;
  /** Set only when `get_iocs` failed and `state` is `"partial"`. */
  readonly iocsError: unknown | null;
  /** Set only when `get_threat_intelligence` failed and `state` is `"partial"`. */
  readonly threatIntelligenceError: unknown | null;
  /** Set only when `get_timeline` failed and `state` is `"partial"`. Optional
   * for the same reason `UseInvestigationData["timeline"]` is (see that
   * field's doc comment) -- this hook always sets it, never leaves it
   * `undefined`. */
  readonly timelineError?: unknown | null;
  /** Set only when `get_investigation_risk_explanation` failed and
   * `state` is `"partial"`. Optional for the same reason
   * `timelineError` is -- this hook always sets it, never leaves it
   * `undefined`. */
  readonly riskExplanationError?: unknown | null;
  /** Starts a fresh request cycle for the same `investigationId` --
   * see the module doc comment's "Retry" section. A no-op call from
   * the caller's side is safe at any time (it simply re-runs the same
   * fetch cycle); it does not validate that a prior attempt actually
   * failed, mirroring `get_investigation`'s own statelessness. */
  readonly retry: () => void;
}

const EMPTY_DATA: UseInvestigationData = {
  investigation: null,
  iocs: null,
  iocSignificance: null,
  threatIntelligence: null,
  timeline: null,
  riskExplanation: null,
};

function isValidInvestigationId(investigationId: number): boolean {
  return Number.isSafeInteger(investigationId) && investigationId > 0;
}

function isInvestigationNotFound(error: unknown): boolean {
  return (
    error instanceof CommandFailedError && error.code === INVESTIGATION_NOT_FOUND_CODE
  );
}

interface InternalState {
  readonly state: InvestigationLoadState;
  readonly data: UseInvestigationData;
  readonly investigationError: unknown | null;
  readonly iocsError: unknown | null;
  readonly threatIntelligenceError: unknown | null;
  readonly timelineError: unknown | null;
  readonly riskExplanationError: unknown | null;
}

function idleState(): InternalState {
  return {
    state: "idle",
    data: EMPTY_DATA,
    investigationError: null,
    iocsError: null,
    threatIntelligenceError: null,
    timelineError: null,
    riskExplanationError: null,
  };
}

function loadingState(): InternalState {
  return {
    state: "loading",
    data: EMPTY_DATA,
    investigationError: null,
    iocsError: null,
    threatIntelligenceError: null,
    timelineError: null,
    riskExplanationError: null,
  };
}

export function useInvestigation(investigationId: number): UseInvestigationResult {
  const [internal, setInternal] = useState<InternalState>(() =>
    isValidInvestigationId(investigationId) ? loadingState() : idleState(),
  );
  const generationRef = useRef(0);
  const [retryNonce, setRetryNonce] = useState(0);

  useEffect(() => {
    if (!isValidInvestigationId(investigationId)) {
      // Defensive only -- the route layer (Phase 4J-3) already never
      // hands this hook an invalid id in production. Never calls
      // runCommand() for an id that would fail GetInvestigationRequest's
      // own `investigation_id <= 0` validation.
      setInternal(idleState());
      return;
    }

    let cancelled = false;
    const generation = ++generationRef.current;

    setInternal(loadingState());

    void Promise.allSettled([
      runCommand("get_investigation", { investigation_id: investigationId }),
      runCommand("get_iocs", { investigation_id: investigationId }),
      runCommand("get_threat_intelligence", { investigation_id: investigationId }),
      runCommand("get_timeline", { investigation_id: investigationId }),
      runCommand("get_investigation_risk_explanation", { investigation_id: investigationId }),
    ]).then(([investigationResult, iocsResult, threatIntelligenceResult, timelineResult, riskExplanationResult]) => {
      if (cancelled || generation !== generationRef.current) {
        // Superseded by unmount, Strict Mode's discarded first
        // invocation, an investigationId change, or a retry -- this
        // settlement is stale and must never overwrite newer state.
        return;
      }

      if (investigationResult.status === "rejected") {
        setInternal({
          state: isInvestigationNotFound(investigationResult.reason) ? "notFound" : "error",
          data: EMPTY_DATA,
          investigationError: investigationResult.reason,
          iocsError: null,
          threatIntelligenceError: null,
          timelineError: null,
          riskExplanationError: null,
        });
        return;
      }

      const iocs = iocsResult.status === "fulfilled" ? iocsResult.value.iocs : null;
      // Derived from the same settled `get_iocs` result as `iocs` above
      // -- no second `runCommand()` call, per this hook's own "no new
      // backend command" rule (module doc comment). `null` under the
      // exact same condition as `iocs` (see `UseInvestigationData
      // .iocSignificance`'s own doc comment).
      const iocSignificance =
        iocsResult.status === "fulfilled" ? iocsResult.value.significance : null;
      const iocsError = iocsResult.status === "rejected" ? iocsResult.reason : null;

      const threatIntelligence =
        threatIntelligenceResult.status === "fulfilled"
          ? {
              raw: threatIntelligenceResult.value.threat_intelligence,
              states: threatIntelligenceResult.value.states,
              // Spread only when present -- `exactOptionalPropertyTypes`
              // (tsconfig.json) forbids assigning an explicit `undefined`
              // to `typedVerdicts?:`, and an older backend response
              // omits `typed_verdicts` entirely rather than sending it
              // as `undefined`, so the key must be genuinely absent
              // here too, not present-with-`undefined`.
              ...(threatIntelligenceResult.value.typed_verdicts !== undefined
                ? { typedVerdicts: threatIntelligenceResult.value.typed_verdicts }
                : {}),
            }
          : null;
      const threatIntelligenceError =
        threatIntelligenceResult.status === "rejected" ? threatIntelligenceResult.reason : null;

      const timeline =
        timelineResult.status === "fulfilled" ? timelineResult.value.events : null;
      const timelineError = timelineResult.status === "rejected" ? timelineResult.reason : null;

      const riskExplanation =
        riskExplanationResult.status === "fulfilled" ? riskExplanationResult.value : null;
      const riskExplanationError =
        riskExplanationResult.status === "rejected" ? riskExplanationResult.reason : null;

      const anySubFetchFailed =
        iocsResult.status === "rejected" ||
        threatIntelligenceResult.status === "rejected" ||
        timelineResult.status === "rejected" ||
        riskExplanationResult.status === "rejected";

      setInternal({
        state: anySubFetchFailed ? "partial" : "success",
        data: {
          investigation: investigationResult.value,
          iocs,
          iocSignificance,
          threatIntelligence,
          timeline,
          riskExplanation,
        },
        investigationError: null,
        iocsError,
        threatIntelligenceError,
        timelineError,
        riskExplanationError,
      });
    });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [investigationId, retryNonce]);

  const retry = useCallback(() => {
    setRetryNonce((current) => current + 1);
  }, []);

  return {
    state: internal.state,
    data: internal.data,
    investigationError: internal.investigationError,
    iocsError: internal.iocsError,
    threatIntelligenceError: internal.threatIntelligenceError,
    timelineError: internal.timelineError,
    riskExplanationError: internal.riskExplanationError,
    retry,
  };
}
