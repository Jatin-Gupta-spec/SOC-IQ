/**
 * Investigation Overview — Timeline region — Phase 4J-6 Part 1D,
 * extended in A4-P2-P3 Part 5C to render the real investigation
 * timeline.
 *
 * `InvestigationWorkspaceData.timeline` (A4-P2-P3 Part 5A/5B,
 * `investigationWorkspaceModel.ts`) now carries the investigation's
 * real, backend-ordered event history from `get_timeline`. This
 * component renders that data directly when it is available, and
 * keeps the original Part 1D single-event fallback (`analyzedAt` +
 * `status`) only for investigations that predate/lack real timeline
 * data -- never as a stand-in for a real timeline that is simply
 * empty, and never presented as if it were itself a real event
 * history (see the `__fallback-note` below).
 *
 * # Precedence (Part 5C task brief)
 *
 * 1. `timeline` populated (`length > 0`) -- render the real events,
 *    in the exact order supplied. Never sorted, reversed,
 *    deduplicated, or mutated here; the backend/application layer is
 *    authoritative for ordering (`GetTimelineResult`'s own contract,
 *    `shared/api/types.ts`).
 * 2. `timeline` genuinely empty (`[]`) -- an honest "no timeline
 *    events" state, distinct from "unavailable". A successful
 *    `get_timeline` response with zero events is real data, not a
 *    missing-data condition.
 * 3. `timeline` unavailable (`null`/`undefined`) -- the original Part
 *    1D fallback: one honest status/timestamp pair built from
 *    `analyzedAt`/`status` if a real timestamp exists, or the
 *    "Timeline data unavailable" note if it does not. Explicitly
 *    labeled as a fallback (`__fallback-note`) so it is never mistaken
 *    for real historical event data.
 *
 * Only `eventId` (React key), `eventType`, `timestamp`, `summary`, and
 * `semantics` are rendered -- the presentation-safe fields already
 * established by `InvestigationWorkspaceTimelineEvent`
 * (`investigationWorkspaceModel.ts`). `metadata` stays unrendered
 * here: it is an opaque `Record<string, unknown>` with no established
 * per-event-type shape (mirrors `rawThreatIntelligence`'s own
 * deliberately-opaque treatment, `ProviderDetail.tsx`), so rendering
 * it generically would either fabricate structure it doesn't have or
 * dump raw JSON, neither of which this component invents. No field is
 * fabricated for a missing value.
 *
 * Presentation-only: no fetching, no polling, no live-activity
 * animation, no new backend field.
 */

import type { ReactElement } from "react";
import { Card } from "../components/Card";
import { StatusBadge } from "../components/StatusBadge";
import { InfoNote } from "../components/InfoNote";
import type { InvestigationWorkspaceData, InvestigationWorkspaceTimelineEvent } from "./investigationWorkspaceModel";
import { statusTone } from "./InvestigationHeaderCard";
import "./InvestigationOverviewTimeline.css";

export interface InvestigationOverviewTimelineProps {
  readonly data: InvestigationWorkspaceData;
}

/** Renders the real, backend-ordered timeline events. Order is
 * rendered exactly as supplied -- no sort, no reverse, no dedup. */
function RealTimelineEvents({
  events,
}: {
  readonly events: readonly InvestigationWorkspaceTimelineEvent[];
}): ReactElement {
  return (
    <ol className="investigation-overview-timeline__events">
      {events.map((event) => (
        <li key={event.eventId} className="investigation-overview-timeline__event">
          <div className="investigation-overview-timeline__event-header">
            <span className="investigation-overview-timeline__event-type">{event.eventType}</span>
            <span className="investigation-overview-timeline__event-timestamp">{event.timestamp}</span>
          </div>
          <p className="investigation-overview-timeline__event-summary">{event.summary}</p>
          <span className="investigation-overview-timeline__event-semantics">{event.semantics}</span>
        </li>
      ))}
    </ol>
  );
}

/** The Part 1D single-event fallback, used only when `timeline` is
 * `null`/`undefined` (no real timeline data was ever normalized).
 * Explicitly labeled as a fallback via `__fallback-note` -- this is
 * "the latest known status", not a real event history, and must never
 * read as one. */
function FallbackStatusEvent({ data }: { readonly data: InvestigationWorkspaceData }): ReactElement {
  const hasTimestamp = data.analyzedAt.trim().length > 0;

  if (!hasTimestamp) {
    return <InfoNote>Timeline data unavailable for this investigation.</InfoNote>;
  }

  return (
    <>
      <InfoNote>
        Detailed event history is unavailable for this investigation. Showing its latest known status instead:
      </InfoNote>
      <ol className="investigation-overview-timeline__events">
        <li className="investigation-overview-timeline__event investigation-overview-timeline__event--fallback">
          <StatusBadge label={data.status} tone={statusTone(data.status)} />
          <span className="investigation-overview-timeline__event-timestamp">{data.analyzedAt}</span>
        </li>
      </ol>
    </>
  );
}

/**
 * Renders the Overview's timeline. Callers only render this once
 * `InvestigationWorkspaceData` actually exists (`useInvestigation()`'s
 * `"success"`/`"partial"` states).
 */
export function InvestigationOverviewTimeline({ data }: InvestigationOverviewTimelineProps): ReactElement {
  const timeline = data.timeline ?? null;

  let body: ReactElement;
  if (timeline !== null && timeline.length > 0) {
    // Precedence 1: real, populated timeline always wins -- never
    // replaced by the analyzedAt/status fallback, even when both are
    // present.
    body = <RealTimelineEvents events={timeline} />;
  } else if (timeline !== null) {
    // Precedence 2: a real, successful, genuinely empty timeline --
    // honest "no events" state, not "unavailable".
    body = <InfoNote>No timeline events have been recorded for this investigation.</InfoNote>;
  } else {
    // Precedence 3: no real timeline data was ever normalized --
    // fall back to the original Part 1D status/timestamp note.
    body = <FallbackStatusEvent data={data} />;
  }

  return (
    <Card title="Timeline" className="investigation-overview-timeline">
      {body}
    </Card>
  );
}
