/**
 * Investigation Overview — Risk region — Phase 4J-6 Part 1C, extended
 * in PD-08-P2 with the deterministic Risk Explanation narrative and
 * IOC category breakdown.
 *
 * The Overview's risk presentation: real risk score, severity, and
 * confidence, exactly as `normalizeInvestigationWorkspace()` (Phase
 * 4J-5) already shaped them for `InvestigationWorkspaceData`. Reuses
 * the same scored/not-scored distinction and tone mappings the Part
 * 1B header already established (`isInvestigationScored`,
 * `severityTone`, `formatConfidence` from `./InvestigationHeaderCard`)
 * rather than redefining them — task brief §3/§13 ("reuse", "do not
 * duplicate normalization logic").
 *
 * # PD-08-P2 addition — Risk Explanation
 *
 * `data.riskExplanation` (PD-08-P1's `get_investigation_risk_explanation`,
 * normalized by `investigationWorkspaceModel.ts`) carries the same
 * deterministic explanation the legacy `RiskExplanationWidget` already
 * shows: the narrative lines the backend's `RiskExplanationService`
 * produced, and the IOC category point breakdown. This component only
 * renders that explanation when the investigation is actually scored
 * (`isInvestigationScored`) and a successful explanation fetch has
 * been normalized (`riskExplanation !== null`) — an unscored
 * investigation already gets its own honest "scoring was disabled"
 * note below, and a still-loading/unavailable explanation is left for
 * `InvestigationWorkspacePage`'s existing partial-data warning banner
 * ("Risk explanation unavailable") to report, never silently hidden
 * nor backfilled with an invented narrative (task brief §9/§10/§11).
 *
 * The category breakdown is only presented as verified when
 * `iocBreakdownVerified` is `true` — matching `RiskExplanationService`'s
 * own honesty contract (`RiskExplanation.ioc_breakdown_verified`,
 * PD-08-P1: the service cross-checks that every category's `points`
 * sums to the investigation's stored `ioc_score` before treating the
 * decomposition as reliable). When it is `false`, the categories still
 * render (they are still the backend's own real data, not fabricated)
 * but with an explicit caveat rather than an implied guarantee — this
 * component never claims more certainty than the backend itself does
 * (task brief §7: "do not make the narrative more dramatic than the
 * underlying data").
 *
 * The narrative is rendered as the backend's own ordered list of
 * lines, verbatim — no added interpretation, no invented causality,
 * no reordering (task brief §7).
 *
 * Presentation-only: no fetching, no routing, no risk calculation, no
 * `runCommand()` (task brief §5/§6).
 */

import type { ReactElement } from "react";
import { Card } from "../components/Card";
import { MetricCard } from "../components/MetricCard";
import { StatusBadge } from "../components/StatusBadge";
import { InfoNote } from "../components/InfoNote";
import type {
  InvestigationWorkspaceData,
  InvestigationWorkspaceIocCategoryContribution,
  InvestigationWorkspaceRiskExplanation,
} from "./investigationWorkspaceModel";
import { isInvestigationScored, severityTone, formatConfidence } from "./InvestigationHeaderCard";
import "./InvestigationOverviewRisk.css";

export interface InvestigationOverviewRiskProps {
  readonly data: InvestigationWorkspaceData;
}

/** Renders `RiskExplanation.narrative` verbatim, in the backend's own
 * order -- no line is reworded, dropped, or reordered here. */
function RiskExplanationNarrative({
  narrative,
}: {
  readonly narrative: readonly string[];
}): ReactElement | null {
  if (narrative.length === 0) {
    return null;
  }
  return (
    <ul className="investigation-overview-risk__narrative">
      {narrative.map((line, index) => (
        // Narrative lines are backend-ordered prose, not identified by
        // any stable id of their own (`RiskExplanationDTO.narrative`
        // is `list[str]`) -- index is a safe React key here because
        // this list is never reordered or edited in place, only
        // replaced wholesale on the next successful fetch.
        // eslint-disable-next-line react/no-array-index-key
        <li key={index} className="investigation-overview-risk__narrative-line">
          {line}
        </li>
      ))}
    </ul>
  );
}

/** Renders `RiskExplanation.ioc_categories`' point breakdown in the
 * backend's own deterministic order (highest point contribution
 * first, tie-broken by category key -- `RiskExplanationDTO`'s own doc
 * comment). Never re-sorted, re-grouped, or recomputed here. */
function RiskExplanationCategoryBreakdown({
  categories,
  verified,
}: {
  readonly categories: readonly InvestigationWorkspaceIocCategoryContribution[];
  readonly verified: boolean;
}): ReactElement | null {
  if (categories.length === 0) {
    return null;
  }
  return (
    <>
      <table className="investigation-overview-risk__breakdown">
        <caption className="investigation-overview-risk__breakdown-caption">
          IOC category contribution to risk score
        </caption>
        <thead>
          <tr>
            <th scope="col">Category</th>
            <th scope="col">Count</th>
            <th scope="col">Weight</th>
            <th scope="col">Significance</th>
            <th scope="col">Points</th>
          </tr>
        </thead>
        <tbody>
          {categories.map((category) => (
            <tr key={category.iocType}>
              <th scope="row">{category.iocTypeTitle}</th>
              <td>{category.count}</td>
              <td>{category.weight}</td>
              <td>{category.significance}</td>
              <td>{category.points}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {!verified ? (
        <InfoNote>
          This category breakdown could not be verified against the investigation&rsquo;s stored
          IOC score, so treat the individual point values as approximate.
        </InfoNote>
      ) : null}
    </>
  );
}

/** Renders the PD-08-P1 Risk Explanation: narrative first, then the
 * IOC category breakdown, matching the legacy `RiskExplanationWidget`'s
 * own section order. Only rendered once the investigation is scored
 * and a real explanation has been normalized (see this module's doc
 * comment). */
function RiskExplanationDetail({
  explanation,
}: {
  readonly explanation: InvestigationWorkspaceRiskExplanation;
}): ReactElement {
  return (
    <div className="investigation-overview-risk__explanation">
      <h3 className="investigation-overview-risk__explanation-heading">Why this risk assessment</h3>
      <RiskExplanationNarrative narrative={explanation.narrative} />
      <RiskExplanationCategoryBreakdown
        categories={explanation.iocCategories}
        verified={explanation.iocBreakdownVerified}
      />
      {explanation.warnings.length > 0 ? (
        <ul className="investigation-overview-risk__explanation-warnings">
          {explanation.warnings.map((warning, index) => (
            // Same rationale as `RiskExplanationNarrative`'s key choice
            // -- `RiskExplanationDTO.warnings` is also a plain
            // `list[str]`.
            // eslint-disable-next-line react/no-array-index-key
            <li key={index}>
              <StatusBadge label={warning} tone="warning" />
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

/**
 * Renders the investigation's real risk score, severity, and
 * confidence when the risk stage actually ran, or one honest
 * "scoring was disabled" note when `severity` is the backend's
 * `NOT_SCORED` sentinel -- never a fabricated `0`/`0%` standing in
 * for a real value (task brief §6/§8/§9). When scored and a Risk
 * Explanation has been fetched successfully, also renders the
 * deterministic narrative and IOC category breakdown (PD-08-P2).
 */
export function InvestigationOverviewRisk({ data }: InvestigationOverviewRiskProps): ReactElement {
  const scored = isInvestigationScored(data.severity);
  const riskExplanation = data.riskExplanation ?? null;

  return (
    <Card title="Risk Overview" className="investigation-overview-risk">
      {scored ? (
        <>
          <div className="investigation-overview-risk__metrics">
            <MetricCard label="Risk score" value={String(data.riskScore)} />
            <MetricCard label="Confidence" value={formatConfidence(data.confidence)} />
          </div>
          <div className="investigation-overview-risk__severity">
            <span className="investigation-overview-risk__severity-label">Severity</span>
            <StatusBadge label={data.severity} tone={severityTone(data.severity)} />
          </div>
          {riskExplanation !== null ? <RiskExplanationDetail explanation={riskExplanation} /> : null}
        </>
      ) : (
        <>
          <div className="investigation-overview-risk__severity">
            <span className="investigation-overview-risk__severity-label">Severity</span>
            <StatusBadge label="Not scored" tone="neutral" />
          </div>
          <InfoNote>
            Risk scoring was disabled for this investigation, so no risk score or confidence
            was calculated.
          </InfoNote>
        </>
      )}
    </Card>
  );
}
