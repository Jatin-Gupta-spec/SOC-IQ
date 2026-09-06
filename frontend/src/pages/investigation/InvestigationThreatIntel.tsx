/**
 * Investigation Workspace — Threat Intel tab content — Phase 4J-6
 * Part 3A, extended by Part 3B.
 *
 * # Part 3B — result summary (task brief §6/§9)
 *
 * Part 3B adds one thing on top of Part 3A's Status/Supporting
 * information sections: a "Result summary" row of `MetricCard`s
 * giving the real, already-computed `countTiStates()` totals (total
 * indicators, and each real state's count) a quantitative,
 * scan-at-a-glance presentation. It intentionally reuses the exact
 * same counts Part 3A's Status/Supporting sections already render —
 * no new count is computed, no percentage is derived, and no field is
 * read out of `rawThreatIntelligence` itself.
 *
 * `rawThreatIntelligence` stays untyped (`Record<string, unknown>`,
 * `shared/api/types.ts`) by design — the backend's own persisted
 * `Investigation.threat_intelligence` shape is deliberately not
 * DTO'd, so this component (like `InvestigationOverviewThreatIntel`
 * before it) never reads a key out of it directly. Doing so would
 * mean guessing at an unstated schema and silently coupling this UI
 * to today's provider's field names — exactly the "provider-specific
 * schema" and "reconstruct provider semantics from raw strings" the
 * task brief warns against (§3/§7/§9). The one piece of real,
 * strongly-typed TI signal this module has is each indicator's
 * `tiState`, attached by `normalizeInvestigationWorkspace()`
 * (Phase 4J-5) from the backend's own typed `states` projection — so
 * that remains the sole source for every count and label below, same
 * as Part 3A.
 *
 * For the same reason, no IOC-level *raw TI result* (e.g. a
 * VirusTotal verdict, detection count, or scan timestamp) is
 * presented here: the normalized model attaches only `tiState` to
 * each indicator (`InvestigationWorkspaceIndicator`, no raw record),
 * so there is no explicit IOC-to-raw-TI-result relationship in the
 * existing model to present (task brief §7's "if the normalized data
 * does NOT contain an IOC-to-TI relationship, do not invent one").
 * The per-indicator `tiState` *is* already presented, via Part 3A's
 * existing Status/Supporting sections and the IOC workspace's own
 * per-indicator display (Part 2C/2D) — not duplicated a third time
 * here.
 *
 * No real `provider` field exists anywhere in the *typed* contract
 * (`GetThreatIntelligenceResult`, `shared/api/types.ts`) -- if the
 * real runtime payload happens to carry one, Part 3C's `ProviderDetail`
 * (below) surfaces it like any other real field it finds, but this
 * component never assumes one is present.
 *
 * # Part 3C — provider details (task brief §6/§7/§13)
 *
 * Every branch that has real `rawThreatIntelligence` (not `null`) now
 * also renders `<ProviderDetail raw={...} />`: a collapsed-by-default
 * disclosure presenting the payload's own real keys/values as a
 * readable hierarchy -- never `JSON.stringify(...)`, never a key name
 * this component invents, and never a sensitive-looking key (see
 * `ProviderDetail.tsx`'s own doc comment for the full safety/shape
 * rules). This is additive only: the Status/Supporting
 * information/Result summary sections above are unchanged from Part
 * 3A/3B.
 *
 * The Threat Intel tab's real (foundation) content, rendered when the
 * workspace's "Threat Intel" tab is selected
 * (`InvestigationWorkspacePage.tsx`). Built exclusively from the
 * already-normalized `InvestigationWorkspaceData` -- `iocsByType`
 * (each indicator's real `tiState`) and `rawThreatIntelligence`'s
 * null-vs-object distinction (`normalizeInvestigationWorkspace()`,
 * Phase 4J-5) -- no second `get_threat_intelligence` fetch, no
 * `runCommand()`, no re-normalization, and no new `TiState` values
 * beyond the real six the normalization layer already assigns (task
 * brief §6/§7).
 *
 * This is Part 3A's *foundation* only: an honest, investigation-level
 * presentation of the same per-indicator TI classification data the
 * compact `InvestigationOverviewThreatIntel` summary (Part 1D) already
 * shows, but structured for this tab's fuller role (task brief §16)
 * and with real, per-state explanatory text (task brief §8-§13) so a
 * person can understand what each canonical state actually means
 * without following the badge into somewhere else. It deliberately
 * does NOT implement per-IOC/provider detail views, a raw JSON
 * payload viewer, VirusTotal lookups, enrichment actions, or
 * correlations -- those remain later 4J-6 parts' scope (task brief
 * §3/§19).
 *
 * # Why there is no single "investigation-level TiState" (task brief §6)
 *
 * `normalizeInvestigationWorkspace()` never produces one summary
 * `TiState` for the whole investigation -- `TiState` is only ever
 * attached per indicator (`InvestigationWorkspaceIndicator.tiState`,
 * `investigationWorkspaceModel.ts`). Different indicators in the same
 * investigation can genuinely be in different real states at once
 * (e.g. some `enriched`, some `no_api_key`) -- collapsing that into
 * one fabricated overall status would misrepresent the real data, so
 * this component does not attempt to construct new TI state logic of
 * its own (task brief §6): it groups indicators by whichever of the
 * six real canonical states each one genuinely carries, the same
 * grouping approach `InvestigationOverviewThreatIntel` already
 * established, and renders one real, honestly-labeled group per
 * distinct state that actually occurs.
 *
 * # States kept honestly distinguishable (task brief §14/§15, mirrors
 * `InvestigationOverviewThreatIntel`'s own state handling)
 *
 * - `rawThreatIntelligence === null` -- no successful
 *   `get_threat_intelligence` response has been normalized
 *   (missing/failed data): renders "Threat Intelligence data
 *   unavailable", never converted into "Not enriched" or any other
 *   real state (task brief §14).
 * - `rawThreatIntelligence` is real but `iocsByType === null` -- TI
 *   itself succeeded, but the per-indicator breakdown depends on IOC
 *   data that failed independently: renders an honest note saying so,
 *   never a fabricated breakdown with no indicators to attach states
 *   to.
 * - Real data with zero indicators to classify: an honest "No
 *   indicators to enrich" empty state (a successful-but-empty result,
 *   never confused with the unavailable state above, task brief §15).
 * - Real data with real indicators: a "Status" section naming every
 *   real state present, plus a "Supporting information" section with
 *   the real per-state counts and a short, honest description of what
 *   each canonical state means (task brief §17) -- never a fabricated
 *   confidence, reputation, provider name, timestamp, or verdict
 *   (task brief §4's fabrication rules).
 *
 * # Phase 4K-3 -- typed verdict presentation
 *
 * `PHASE4_NEXT_GENERATION_ARCHITECTURE_MASTER_PLAN.md` §26 names
 * Phase 4K's exit criteria: "Multi-provider display, NOT_FOUND vs
 * CLEAN visibly distinct." Part 3A-3D's `tiState` sections above
 * describe whether TI *lookup* completed, not what a provider
 * actually *concluded* -- that conclusion is the real, strongly-typed
 * `typedVerdict` field Phase 4K-1 (backend) computes server-side and
 * Phase 4K-2 (frontend model) attaches directly to each normalized
 * indicator (`InvestigationWorkspaceIndicator.typedVerdict`,
 * `investigationWorkspaceModel.ts`) -- see `investigationVerdicts.ts`'s
 * own doc comment for the full reasoning and the real backend source.
 *
 * Two sections below read that field, both via
 * `investigationVerdicts.ts`'s helpers -- never a raw-payload read or
 * a second normalization pass of their own:
 *
 * - "Result verdicts": an investigation-level aggregate, built from
 *   `countTypedVerdicts(data.iocsByType)` -- an honest count per real
 *   verdict, the same "group and count" approach `countTiStates()`
 *   above already established, reusing the exact tone mapping
 *   `IocExplorerPage.tsx` already assigned to these verdicts
 *   (critical/warning/success/neutral) rather than inventing a new
 *   one. `not_found` gets the `neutral` tone -- visibly distinct from
 *   `clean`'s `success` tone, never merged with it, and always
 *   labeled "Not Found" (never "Clean"). Omitted entirely when there
 *   is nothing real to count (`countTypedVerdicts()` returns `null`
 *   or `total === 0`) -- never an empty/zeroed section for its own
 *   sake.
 * - "Indicator verdicts": which indicator carries which verdict, built
 *   from `listIndicatorVerdicts(data.iocsByType)` -- a direct read of
 *   the same field each already-normalized indicator carries, not a
 *   match/lookup against anything (see that function's own doc
 *   comment for why Part 4K Part 2's old identity-string matching is
 *   no longer needed). Only indicators with a real `typedVerdict`
 *   appear; `null` is simply absent from this table, never shown with
 *   an invented verdict. Omitted entirely (like "Result verdicts")
 *   when nothing real exists to show.
 *
 * `typed_verdicts` carries no provider-identity field (confirmed by
 * reading `app/threat_intel/verdict_from_persisted.py` and
 * `GetThreatIntelligenceResult` directly) -- unlike the old
 * raw-payload path, there is no real field left to label "Provider:
 * VirusTotal" here, so neither section names a provider. Real
 * multi-provider aggregation still depends on a second
 * `ThreatIntelProvider` adapter being wired into `ThreatIntelService`
 * (`app/threat_intel/service.py`'s own doc comment: "reserved for
 * future multi-provider aggregation, not yet wired up anywhere") --
 * backend work outside this frontend-only phase's scope.
 *
 * The "Result verdicts" list and the existing "Status" list both use
 * the shared `investigation-threat-intel__badges` class for their
 * flex/wrap layout, but each also carries its own modifier class
 * (`--verdicts` / `--status`) so the two lists remain distinguishable
 * by selector -- no visual or behavioral change, just an unambiguous
 * hook for tests (and any future styling that should target one list
 * without the other).
 */

import type { ReactElement } from "react";
import { Card } from "../components/Card";
import { StatusBadge, type StatusTone } from "../components/StatusBadge";
import { InfoNote } from "../components/InfoNote";
import { MetricCard } from "../components/MetricCard";
import { DataTable, type DataTableColumn } from "../components/DataTable";
import { ProviderDetail } from "./ProviderDetail";
import { TI_STATES, type TiState, type TypedVerdict } from "../../shared/api/types";
import type { InvestigationWorkspaceData, InvestigationWorkspaceIocsByType } from "./investigationWorkspaceModel";
import { countTypedVerdicts, listIndicatorVerdicts, type IndicatorVerdict } from "./investigationVerdicts";
import "./InvestigationThreatIntel.css";

/** Human-readable labels for the four real `TypedVerdict` values --
 * "Not Found" is always rendered as its own two-word label, never
 * collapsed into or reusing "Clean"'s label (the master plan's own
 * "NOT_FOUND vs CLEAN visibly distinct" exit criterion, task brief's
 * hard requirement). */
const TYPED_VERDICT_LABELS: Record<TypedVerdict, string> = {
  malicious: "Malicious",
  suspicious: "Suspicious",
  clean: "Clean",
  not_found: "Not Found",
};

/** Same verdict tone mapping `IocExplorerPage.tsx` already
 * established for these four verdicts -- reused by value, not
 * redefined, so a verdict never renders a different tone depending on
 * which page happens to show it. `not_found` stays `neutral`,
 * deliberately never `success` (never sharing a tone with `clean`). */
const VERDICT_TONE: Record<TypedVerdict, StatusTone> = {
  malicious: "critical",
  suspicious: "warning",
  clean: "success",
  not_found: "neutral",
};

const INDICATOR_VERDICT_COLUMNS: readonly DataTableColumn<IndicatorVerdict>[] = [
  { key: "value", header: "Indicator", render: (row) => row.value },
  { key: "type", header: "Type", render: (row) => row.type },
  {
    key: "verdict",
    header: "Verdict",
    render: (row) => <StatusBadge label={TYPED_VERDICT_LABELS[row.verdict]} tone={VERDICT_TONE[row.verdict]} />,
  },
];

export interface InvestigationThreatIntelProps {
  readonly data: InvestigationWorkspaceData;
}

/** Same canonical labels `InvestigationOverviewThreatIntel.tsx`/
 * `ThreatIntelPage.tsx` already established -- reused by value, not
 * redefined with different wording (task brief §7's "use the existing
 * canonical state values"). */
const TI_STATE_LABELS: Record<TiState, string> = {
  enriched: "Enriched",
  not_enriched: "Not enriched",
  no_api_key: "No API key",
  provider_error: "Provider error",
  incomplete_check: "Incomplete check",
  unsupported_type: "Unsupported type",
};

/** Same tone grouping already established elsewhere in the project --
 * a provider error is never made to look like a success, and an
 * informational state (not enriched / unsupported type) never
 * borrows the success/error tones (task brief §9/§13/§18). */
const TI_STATE_TONE: Record<TiState, StatusTone> = {
  enriched: "success",
  not_enriched: "neutral",
  no_api_key: "warning",
  provider_error: "error",
  incomplete_check: "warning",
  unsupported_type: "neutral",
};

/** Short, honest description of what each canonical state means --
 * describing the *indicators in that state*, never the investigation
 * as a whole (task brief §11: a provider error must not imply the
 * investigation itself failed) and never inventing a specific reason
 * beyond the state's own real meaning (task brief §9's "do not invent
 * a reason"). */
const TI_STATE_DESCRIPTIONS: Record<TiState, string> = {
  enriched: "Threat intelligence data is available for these indicators.",
  not_enriched: "These indicators have not been enriched with threat intelligence.",
  no_api_key: "Threat intelligence enrichment did not run because no provider API key is configured.",
  provider_error: "Threat intelligence enrichment failed for these indicators due to a provider error.",
  incomplete_check: "Threat intelligence enrichment for these indicators did not complete.",
  unsupported_type: "Threat intelligence enrichment does not support this indicator type.",
};

const UNCLASSIFIED_LABEL = "Not yet classified";
const UNCLASSIFIED_DESCRIPTION = "No threat intelligence classification is recorded yet for these indicators.";

interface TiStateGroup {
  readonly state: TiState;
  readonly count: number;
}

/** Groups indicators by their real, already-attached `tiState` --
 * counting only, never recomputing or inferring a state
 * (`lookupTiState()` in `investigationWorkspaceModel.ts` already did
 * that exact-lookup work; task brief §6). */
function countTiStates(iocsByType: InvestigationWorkspaceIocsByType): {
  readonly groups: readonly TiStateGroup[];
  readonly unclassified: number;
  readonly total: number;
} {
  const byState: Partial<Record<TiState, number>> = {};
  let unclassified = 0;
  let total = 0;

  for (const indicators of Object.values(iocsByType)) {
    for (const indicator of indicators ?? []) {
      total += 1;
      if (indicator.tiState === null) {
        unclassified += 1;
      } else {
        byState[indicator.tiState] = (byState[indicator.tiState] ?? 0) + 1;
      }
    }
  }

  const groups = TI_STATES.filter((state) => (byState[state] ?? 0) > 0).map((state) => ({
    state,
    count: byState[state] as number,
  }));

  return { groups, unclassified, total };
}

/**
 * Renders the workspace's real Threat Intel tab content (Part 3A
 * foundation). Callers only render this once `InvestigationWorkspaceData`
 * actually exists (`useInvestigation()`'s `"success"`/`"partial"`
 * states) and the Threat Intel tab is selected -- matches every other
 * workspace region's convention.
 */
export function InvestigationThreatIntel({ data }: InvestigationThreatIntelProps): ReactElement {
  if (data.rawThreatIntelligence === null) {
    return (
      <Card title="Threat Intelligence" className="investigation-threat-intel">
        <InfoNote>Threat Intelligence data unavailable for this investigation.</InfoNote>
      </Card>
    );
  }

  if (data.iocsByType === null) {
    return (
      <Card title="Threat Intelligence" className="investigation-threat-intel">
        <InfoNote>
          Threat Intelligence data was received, but a per-indicator breakdown is unavailable
          because IOC data for this investigation failed to load.
        </InfoNote>
        <ProviderDetail raw={data.rawThreatIntelligence} />
      </Card>
    );
  }

  const { groups, unclassified, total } = countTiStates(data.iocsByType);

  if (total === 0) {
    return (
      <Card title="Threat Intelligence" className="investigation-threat-intel">
        <InfoNote>No indicators to enrich for this investigation.</InfoNote>
        <ProviderDetail raw={data.rawThreatIntelligence} />
      </Card>
    );
  }

  const verdictCounts = countTypedVerdicts(data.iocsByType);
  const hasVerdicts = verdictCounts !== null && verdictCounts.total > 0;
  const indicatorVerdicts = listIndicatorVerdicts(data.iocsByType);
  const hasIndicatorVerdicts = indicatorVerdicts !== null && indicatorVerdicts.length > 0;

  return (
    <Card title="Threat Intelligence" className="investigation-threat-intel">
      <section
        className="investigation-threat-intel__section"
        aria-labelledby="investigation-threat-intel-summary-heading"
      >
        <h3 id="investigation-threat-intel-summary-heading" className="investigation-threat-intel__heading">
          Result summary
        </h3>
        <div className="investigation-threat-intel__metrics">
          <MetricCard label="Total indicators" value={String(total)} />
          {groups.map(({ state, count }) => (
            <MetricCard key={state} label={TI_STATE_LABELS[state]} value={String(count)} />
          ))}
          {unclassified > 0 ? (
            <MetricCard label={UNCLASSIFIED_LABEL} value={String(unclassified)} />
          ) : null}
        </div>
      </section>
      {hasVerdicts ? (
        <section
          className="investigation-threat-intel__section"
          aria-labelledby="investigation-threat-intel-verdicts-heading"
        >
          <h3 id="investigation-threat-intel-verdicts-heading" className="investigation-threat-intel__heading">
            Result verdicts
          </h3>
          <ul className="investigation-threat-intel__badges investigation-threat-intel__badges--verdicts">
            {verdictCounts.groups.map(({ verdict, count }) => (
              <li key={verdict}>
                <StatusBadge label={`${TYPED_VERDICT_LABELS[verdict]} (${count})`} tone={VERDICT_TONE[verdict]} />
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      {hasIndicatorVerdicts ? (
        <section
          className="investigation-threat-intel__section"
          aria-labelledby="investigation-threat-intel-indicator-verdicts-heading"
        >
          <h3
            id="investigation-threat-intel-indicator-verdicts-heading"
            className="investigation-threat-intel__heading"
          >
            Indicator verdicts
          </h3>
          <DataTable
            caption="Indicators with a real typed threat intelligence verdict"
            columns={INDICATOR_VERDICT_COLUMNS}
            rows={indicatorVerdicts}
            getRowId={(row) => `${row.type}:${row.value}`}
          />
        </section>
      ) : null}
      <section className="investigation-threat-intel__section" aria-labelledby="investigation-threat-intel-status-heading">
        <h3 id="investigation-threat-intel-status-heading" className="investigation-threat-intel__heading">
          Status
        </h3>
        <ul className="investigation-threat-intel__badges investigation-threat-intel__badges--status">
          {groups.map(({ state }) => (
            <li key={state}>
              <StatusBadge label={TI_STATE_LABELS[state]} tone={TI_STATE_TONE[state]} />
            </li>
          ))}
          {unclassified > 0 ? (
            <li>
              <StatusBadge label={UNCLASSIFIED_LABEL} tone="neutral" />
            </li>
          ) : null}
        </ul>
      </section>
      <section
        className="investigation-threat-intel__section"
        aria-labelledby="investigation-threat-intel-support-heading"
      >
        <h3 id="investigation-threat-intel-support-heading" className="investigation-threat-intel__heading">
          Supporting information
        </h3>
        <dl className="investigation-threat-intel__support">
          {groups.map(({ state, count }) => (
            <div key={state} className="investigation-threat-intel__support-row">
              <dt>
                {TI_STATE_LABELS[state]} ({count})
              </dt>
              <dd>{TI_STATE_DESCRIPTIONS[state]}</dd>
            </div>
          ))}
          {unclassified > 0 ? (
            <div className="investigation-threat-intel__support-row">
              <dt>
                {UNCLASSIFIED_LABEL} ({unclassified})
              </dt>
              <dd>{UNCLASSIFIED_DESCRIPTION}</dd>
            </div>
          ) : null}
        </dl>
      </section>
      <section
        className="investigation-threat-intel__section"
        aria-labelledby="investigation-threat-intel-provider-heading"
      >
        <h3 id="investigation-threat-intel-provider-heading" className="investigation-threat-intel__heading">
          Provider details
        </h3>
        <ProviderDetail raw={data.rawThreatIntelligence} />
      </section>
    </Card>
  );
}
