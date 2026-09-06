/**
 * Investigation Overview — Threat Intelligence Summary region —
 * Phase 4J-6 Part 1D.
 *
 * A compact, high-level summary of this investigation's real TI
 * classification state, built exclusively from the already-normalized
 * `iocsByType` (each indicator's `tiState`, attached by
 * `normalizeInvestigationWorkspace()`, Phase 4J-5) and
 * `rawThreatIntelligence`'s null-vs-object distinction -- no second
 * `get_threat_intelligence` fetch, no `runCommand()`, and no raw
 * provider payload rendering (task brief §8/§11).
 *
 * Uses the same canonical `TiState` vocabulary and tone grouping the
 * existing Threat Intel mock page already established
 * (`ThreatIntelPage.tsx`: enriched -> success, no-api-key/
 * incomplete-check -> warning, provider-error -> error, not-enriched/
 * unsupported -> neutral) -- no seventh invented `TiState`.
 *
 * # States kept honestly distinguishable (task brief §9/§10)
 *
 * - `rawThreatIntelligence === null` -- no successful
 *   `get_threat_intelligence` response has been normalized
 *   (missing/failed data): renders "Threat Intelligence data
 *   unavailable", never converted into "Not enriched".
 * - `rawThreatIntelligence` is real but `iocsByType === null` -- TI
 *   itself succeeded, but the per-indicator breakdown depends on IOC
 *   data that failed independently: renders an honest note saying so,
 *   rather than fabricating a breakdown with no indicators to attach
 *   states to.
 * - Real data with zero indicators to classify: an honest "No
 *   indicators to enrich" empty state (a successful-but-empty result,
 *   not an error).
 * - Real data with real indicators: one row per canonical `TiState`
 *   that actually occurs, using its real count -- plus a distinct
 *   "Not yet classified" row for indicators whose `tiState` is `null`
 *   (the model's own seventh, distinct condition -- see
 *   `investigationWorkspaceModel.ts` -- never merged into
 *   `not_enriched`).
 */

import type { ReactElement } from "react";
import { Card } from "../components/Card";
import { StatusBadge, type StatusTone } from "../components/StatusBadge";
import { InfoNote } from "../components/InfoNote";
import { TI_STATES, type TiState } from "../../shared/api/types";
import type { InvestigationWorkspaceData, InvestigationWorkspaceIocsByType } from "./investigationWorkspaceModel";
import "./InvestigationOverviewThreatIntel.css";

export interface InvestigationOverviewThreatIntelProps {
  readonly data: InvestigationWorkspaceData;
}

/** Human-readable labels for the six real `TiState` values -- mirrors
 * the existing `ThreatIntelPage.tsx`/`mock/threatIntel.ts` vocabulary
 * exactly, not a competing set of names. */
const TI_STATE_LABELS: Record<TiState, string> = {
  enriched: "Enriched",
  not_enriched: "Not enriched",
  no_api_key: "No API key",
  provider_error: "Provider error",
  incomplete_check: "Incomplete check",
  unsupported_type: "Unsupported type",
};

/** Same tone grouping `ThreatIntelPage.tsx` already established --
 * reused here rather than redefined independently, so a provider
 * error is never made to look like a success (task brief §9). */
const TI_STATE_TONE: Record<TiState, StatusTone> = {
  enriched: "success",
  not_enriched: "neutral",
  no_api_key: "warning",
  provider_error: "error",
  incomplete_check: "warning",
  unsupported_type: "neutral",
};

function countTiStates(iocsByType: InvestigationWorkspaceIocsByType): {
  readonly byState: Partial<Record<TiState, number>>;
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

  return { byState, unclassified, total };
}

/**
 * Renders the Overview's compact Threat Intelligence state summary.
 * Callers only render this once `InvestigationWorkspaceData` actually
 * exists (`useInvestigation()`'s `"success"`/`"partial"` states).
 */
export function InvestigationOverviewThreatIntel({
  data,
}: InvestigationOverviewThreatIntelProps): ReactElement {
  if (data.rawThreatIntelligence === null) {
    return (
      <Card title="Threat Intelligence Summary" className="investigation-overview-ti">
        <InfoNote>Threat Intelligence data unavailable for this investigation.</InfoNote>
      </Card>
    );
  }

  if (data.iocsByType === null) {
    return (
      <Card title="Threat Intelligence Summary" className="investigation-overview-ti">
        <InfoNote>
          Threat Intelligence data was received, but a per-indicator breakdown is unavailable
          because IOC data for this investigation failed to load.
        </InfoNote>
      </Card>
    );
  }

  const { byState, unclassified, total } = countTiStates(data.iocsByType);

  if (total === 0) {
    return (
      <Card title="Threat Intelligence Summary" className="investigation-overview-ti">
        <InfoNote>No indicators to enrich for this investigation.</InfoNote>
      </Card>
    );
  }

  return (
    <Card title="Threat Intelligence Summary" className="investigation-overview-ti">
      <ul className="investigation-overview-ti__rows">
        {TI_STATES.filter((state) => (byState[state] ?? 0) > 0).map((state) => (
          <li key={state} className="investigation-overview-ti__row">
            <StatusBadge label={TI_STATE_LABELS[state]} tone={TI_STATE_TONE[state]} />
            <span className="investigation-overview-ti__row-count">{byState[state]}</span>
          </li>
        ))}
        {unclassified > 0 ? (
          <li className="investigation-overview-ti__row">
            <StatusBadge label="Not yet classified" tone="neutral" />
            <span className="investigation-overview-ti__row-count">{unclassified}</span>
          </li>
        ) : null}
      </ul>
    </Card>
  );
}
