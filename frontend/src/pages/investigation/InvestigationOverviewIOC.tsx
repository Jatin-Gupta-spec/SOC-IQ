/**
 * Investigation Overview — IOC Summary region — Phase 4J-6 Part 1D.
 *
 * A compact, high-level IOC distribution summary, built exclusively
 * from the already-normalized `iocsByType`
 * (`normalizeInvestigationWorkspace()`, Phase 4J-5) -- no second fetch,
 * no `runCommand()`, no re-normalization, and no new IOC-type
 * vocabulary beyond the real `PersistedIocType` categories the
 * normalization layer already groups by (task brief §5).
 *
 * This is a *summary* only: total + per-category counts and a small
 * proportional distribution bar. It deliberately does not implement an
 * IOC table, search, filters, pagination, or per-indicator detail --
 * those remain a later IOC workspace's scope (task brief §7).
 *
 * # Three honestly-distinguished states (task brief §6)
 *
 * - `iocsByType === null` -- no successful `get_iocs` response has
 *   been normalized (missing/failed data): renders "IOC data
 *   unavailable", never fabricated zero counts.
 * - `iocsByType` is a real object with every category genuinely empty
 *   (real total of `0`): renders an honest "No IOCs found" empty
 *   state -- this is a successful response, not an error, and is
 *   never confused with the unavailable state above.
 * - `iocsByType` contains real indicators: renders the real total,
 *   real per-category counts (including real zero categories), and a
 *   small distribution visualization.
 */

import type { ReactElement } from "react";
import { Card } from "../components/Card";
import { MetricCard } from "../components/MetricCard";
import { InfoNote } from "../components/InfoNote";
import { PERSISTED_IOC_TYPES, type PersistedIocType } from "../../shared/api/types";
import type { InvestigationWorkspaceData, InvestigationWorkspaceIocsByType } from "./investigationWorkspaceModel";
import "./InvestigationOverviewIOC.css";

export interface InvestigationOverviewIOCProps {
  readonly data: InvestigationWorkspaceData;
}

/** The same real-category groupings the task brief names (§5): each
 * group is a label over one or more real `PersistedIocType` keys, not
 * a second IOC-type vocabulary. Windows file paths/registry keys are
 * folded into the real total but not given their own headline metric,
 * matching the task brief's own named list. Paired with an existing
 * design token so the distribution bar's segments use the project's
 * real color system rather than inventing one. */
const IOC_DISTRIBUTION_GROUPS: ReadonlyArray<{
  readonly label: string;
  readonly types: readonly PersistedIocType[];
  readonly colorVar: string;
}> = [
  { label: "IPs", types: ["ipv4"], colorVar: "var(--color-status-info)" },
  { label: "Domains", types: ["domains"], colorVar: "var(--color-status-success)" },
  { label: "URLs", types: ["urls"], colorVar: "var(--color-brand-primary)" },
  { label: "Emails", types: ["emails"], colorVar: "var(--color-status-warning)" },
  { label: "Hashes", types: ["md5", "sha1", "sha256"], colorVar: "var(--color-severity-critical)" },
  { label: "CVEs", types: ["cves"], colorVar: "var(--color-verdict-no-api-key)" },
];

function countForTypes(
  iocsByType: InvestigationWorkspaceIocsByType,
  types: readonly PersistedIocType[],
): number {
  return types.reduce((sum, type) => sum + (iocsByType[type]?.length ?? 0), 0);
}

function totalIocCount(iocsByType: InvestigationWorkspaceIocsByType): number {
  return countForTypes(iocsByType, PERSISTED_IOC_TYPES);
}

interface DistributionBarProps {
  readonly iocsByType: InvestigationWorkspaceIocsByType;
  readonly total: number;
}

/** Purely decorative, proportional distribution bar over the real
 * per-category counts -- every accessible fact it depicts (label,
 * count) is already available as text via the `MetricCard`s above it,
 * so the bar itself is `aria-hidden` rather than a second, competing
 * source of truth (task brief §18: "do not communicate status through
 * color alone"). Categories with a genuine zero count contribute no
 * segment. */
function DistributionBar({ iocsByType, total }: DistributionBarProps): ReactElement | null {
  if (total === 0) {
    return null;
  }

  const segments = IOC_DISTRIBUTION_GROUPS.map((group) => ({
    label: group.label,
    colorVar: group.colorVar,
    count: countForTypes(iocsByType, group.types),
  })).filter((segment) => segment.count > 0);

  return (
    <div className="investigation-overview-ioc__bar" aria-hidden="true">
      {segments.map((segment) => (
        <div
          key={segment.label}
          className="investigation-overview-ioc__bar-segment"
          style={{ width: `${(segment.count / total) * 100}%`, backgroundColor: segment.colorVar }}
          title={segment.label}
        />
      ))}
    </div>
  );
}

/**
 * Renders the Overview's compact IOC distribution summary. Callers
 * only render this once `InvestigationWorkspaceData` actually exists
 * (`useInvestigation()`'s `"success"`/`"partial"` states) -- matches
 * every other Overview region's convention.
 */
export function InvestigationOverviewIOC({ data }: InvestigationOverviewIOCProps): ReactElement {
  const { iocsByType } = data;

  if (iocsByType === null) {
    return (
      <Card title="IOC Summary" className="investigation-overview-ioc">
        <InfoNote>IOC data unavailable for this investigation.</InfoNote>
      </Card>
    );
  }

  const total = totalIocCount(iocsByType);

  if (total === 0) {
    return (
      <Card title="IOC Summary" className="investigation-overview-ioc">
        <InfoNote>No IOCs found for this investigation.</InfoNote>
      </Card>
    );
  }

  return (
    <Card title="IOC Summary" className="investigation-overview-ioc">
      <DistributionBar iocsByType={iocsByType} total={total} />
      <div className="investigation-overview-ioc__metrics">
        <MetricCard label="Total" value={String(total)} />
        {IOC_DISTRIBUTION_GROUPS.map((group) => (
          <MetricCard
            key={group.label}
            label={group.label}
            value={String(countForTypes(iocsByType, group.types))}
          />
        ))}
      </div>
    </Card>
  );
}
