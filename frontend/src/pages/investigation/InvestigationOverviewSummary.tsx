/**
 * Investigation Overview — Summary region — Phase 4J-6 Part 1C.
 *
 * A concise, genuinely-available metrics summary: IOC counts grouped
 * by the same real `PersistedIocType` categories
 * `normalizeInvestigationWorkspace()` (Phase 4J-5) already groups
 * `iocsByType` by -- no new IOC vocabulary, no IOC tables/detail
 * views (task brief §10/§13). This component only sums the lengths of
 * indicator arrays the normalization layer already produced; it does
 * not fetch, re-normalize, or interpret any indicator's disposition.
 *
 * # Empty vs. unavailable (task brief §11)
 *
 * `data.iocsByType === null` means no successful `get_iocs` response
 * has been normalized (missing data -- see
 * `investigationWorkspaceModel.ts`'s own doc comment on this exact
 * distinction) -- rendered here as an honest "unavailable" note, never
 * as `0`. `data.iocsByType` being a real object (possibly `{}`, or
 * with some/all counts genuinely `0`) is a successful response and is
 * rendered as real numbers, including real zeroes.
 */

import type { ReactElement } from "react";
import { Card } from "../components/Card";
import { MetricCard } from "../components/MetricCard";
import { InfoNote } from "../components/InfoNote";
import { PERSISTED_IOC_TYPES, type PersistedIocType } from "../../shared/api/types";
import type { InvestigationWorkspaceData, InvestigationWorkspaceIocsByType } from "./investigationWorkspaceModel";
import "./InvestigationOverviewSummary.css";

export interface InvestigationOverviewSummaryProps {
  readonly data: InvestigationWorkspaceData;
}

/** Groups the ten real `PersistedIocType` categories into the
 * task-brief-named metrics (§10: "IP count, Domain count, URL count,
 * Hash count, Email count, CVE count") without inventing a second IOC
 * type vocabulary -- each group is just a label over one or more real
 * `PersistedIocType` keys. Windows file paths/registry keys are
 * folded into the real total below but not given their own headline
 * metric, matching the task brief's own named list. */
const IOC_METRIC_GROUPS: ReadonlyArray<{
  readonly label: string;
  readonly types: readonly PersistedIocType[];
}> = [
  { label: "IPs", types: ["ipv4"] },
  { label: "Domains", types: ["domains"] },
  { label: "URLs", types: ["urls"] },
  { label: "Emails", types: ["emails"] },
  { label: "Hashes", types: ["md5", "sha1", "sha256"] },
  { label: "CVEs", types: ["cves"] },
];

/** Sums real indicator-array lengths for the given types. A type
 * key that's absent from `iocsByType` (never fabricated as `[]` by
 * the normalization layer) contributes `0` here, same as a type
 * present with a genuinely empty array -- both mean "no indicators of
 * this type in the real response", which is exactly what this count
 * displays. */
function countForTypes(
  iocsByType: InvestigationWorkspaceIocsByType,
  types: readonly PersistedIocType[],
): number {
  return types.reduce((sum, type) => sum + (iocsByType[type]?.length ?? 0), 0);
}

function totalIocCount(iocsByType: InvestigationWorkspaceIocsByType): number {
  return countForTypes(iocsByType, PERSISTED_IOC_TYPES);
}

/**
 * Renders real IOC-count metrics when a successful `get_iocs`
 * response has been normalized, or one honest "unavailable" note when
 * it hasn't -- never converting a failed/missing IOC fetch into fake
 * zero counts (task brief §11/§12).
 */
export function InvestigationOverviewSummary({ data }: InvestigationOverviewSummaryProps): ReactElement {
  const { iocsByType } = data;

  return (
    <Card title="Investigation Summary" className="investigation-overview-summary">
      {iocsByType === null ? (
        <InfoNote>IOC data is unavailable for this investigation.</InfoNote>
      ) : (
        <div className="investigation-overview-summary__metrics">
          <MetricCard label="Total IOCs" value={String(totalIocCount(iocsByType))} />
          {IOC_METRIC_GROUPS.map((group) => (
            <MetricCard
              key={group.label}
              label={group.label}
              value={String(countForTypes(iocsByType, group.types))}
            />
          ))}
        </div>
      )}
    </Card>
  );
}
