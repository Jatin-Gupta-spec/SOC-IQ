/**
 * Investigation Workspace — Correlations tab content — Phase 4J-6
 * Part 4A, extended Part 4B (UX + interaction only).
 *
 * Renders the Correlations section's foundation: an honest
 * presentation of whatever explicit relationships
 * `deriveInvestigationCorrelations()` (`investigationCorrelationsModel.ts`)
 * finds in the already-normalized `InvestigationWorkspaceData` -- no
 * second fetch, no `runCommand()`, no graph visualization, and no
 * relationship inferred from proximity, shared type, or any other
 * non-explicit signal (task brief §4).
 *
 * Reuses the existing `Card`/`StatusBadge`/`InfoNote` primitives
 * exclusively, matching every other workspace section's visual
 * language (task brief §7/§15) -- no new card style, no new badge
 * system, no graph library (task brief §14).
 *
 * # Part 4B — what changed and what didn't
 *
 * `investigationCorrelationsModel.ts`'s data contract is untouched
 * (task brief §2/§21): as of Phase 4J-6, `extractExplicitCorrelations`
 * reads a real `data.correlations` field populated by
 * `CorrelationService`, so the `"available"` branch below is reachable
 * through real investigation data whenever that service finds at
 * least one deterministic relationship -- it is no longer the
 * unconditionally-empty state Part 4A shipped with. Part 4B adds the
 * presentation/interaction that renders that branch:
 *
 * - a real, per-item disclosure for `context` (a plain `<button>`
 *   with `aria-expanded`/`aria-controls`, task brief §7/§17) so
 *   context isn't dumped inline for every item regardless of length;
 * - slightly fuller empty/unavailable copy (task brief §8/§9)
 *   clarifying *when* this section would show something, without
 *   changing what condition triggers each state.
 *
 * No filter, search, or sort control was added (task brief §12/§13/
 * §14): even though the data model can now populate `correlations`,
 * a single investigation's relationship count remains small enough
 * that such a control would have nothing meaningful to operate on --
 * exactly the "unnecessary controls" §12 warns against. The
 * `InvestigationCorrelation` shape already carries a real
 * `relationshipType` per item, so a filter can be introduced later
 * without another pass over this module once real data justifies it.
 *
 * # Part 4C — cross-investigation disclosure-state leak (MAX-21B-4C-F1)
 *
 * `CorrelationItem` owns its own `expanded` disclosure state locally.
 * Because `WorkspaceTabs` keeps this component mounted in the same
 * tree position across an investigation switch (the same pattern
 * `InvestigationIocWorkspace.tsx`'s own module comment describes for
 * its local filter state), keying each `CorrelationItem` by array
 * index alone let React reuse a component instance -- and its
 * `expanded` state -- across investigations whenever the new
 * investigation's list happened to have an item at the same position.
 * The list below now keys each item by `data.investigationId` combined
 * with its index, so an investigation switch always mounts a fresh
 * `CorrelationItem` per position with disclosure state starting
 * collapsed, matching the "local display state must not leak between
 * investigations" rule `InvestigationIocWorkspace.tsx` already
 * establishes -- without lifting `expanded` out of `CorrelationItem`
 * or introducing a second reset mechanism.
 */

import { useState, type ReactElement } from "react";
import { Card } from "../components/Card";
import { StatusBadge } from "../components/StatusBadge";
import { InfoNote } from "../components/InfoNote";
import { deriveInvestigationCorrelations, type InvestigationCorrelation } from "./investigationCorrelationsModel";
import type { InvestigationWorkspaceData } from "./investigationWorkspaceModel";
import "./InvestigationCorrelations.css";

export interface InvestigationCorrelationsProps {
  readonly data: InvestigationWorkspaceData;
}

export interface CorrelationItemProps {
  readonly correlation: InvestigationCorrelation;
  /** Used only to build a stable-enough DOM id for `aria-controls`
   * (task brief §7); has no bearing on ordering or semantics. */
  readonly index: number;
}

/** One real relationship, rendered with an explicit "Source →
 * Target" text line (task brief §16: a directional indicator must
 * never be the only explanation) plus its own real relationship-type
 * badge.
 *
 * `context`, when the underlying data actually supplies one, sits
 * behind a real, keyboard-accessible disclosure button rather than
 * always being shown inline -- collapsed by default, `aria-expanded`
 * kept in sync with visible state, and the revealed content is
 * un-rendered (not just visually hidden) while collapsed so it's
 * unambiguously hidden from assistive tech too (task brief §7/§17).
 * No animation (task brief §7's "no unnecessary animation"): this is
 * a discrete state change, not motion that needs to communicate
 * anything on its own. Exported so this disclosure behavior can be
 * unit-tested directly against a type-correct `InvestigationCorrelation`
 * fixture without needing `extractExplicitCorrelations` to actually
 * produce one (task brief §19's "do not manufacture a test fixture
 * solely to force this feature" is about the investigation-data
 * pipeline, not about unit-testing this presentational piece on its
 * own well-typed props). */
export function CorrelationItem({ correlation, index }: CorrelationItemProps): ReactElement {
  const hasContext = typeof correlation.context === "string" && correlation.context.length > 0;
  const [expanded, setExpanded] = useState(false);
  const contextId = `investigation-correlation-context-${index}`;

  return (
    <li className="investigation-correlations__item">
      <StatusBadge label={correlation.relationshipType} tone="neutral" />
      <p className="investigation-correlations__relationship">
        {correlation.source} → {correlation.target}
      </p>
      {hasContext ? (
        <>
          <button
            type="button"
            className="investigation-correlations__toggle"
            aria-expanded={expanded}
            aria-controls={contextId}
            onClick={() => setExpanded((current) => !current)}
          >
            {expanded ? "Hide context" : "View context"}
          </button>
          {expanded ? (
            <p id={contextId} className="investigation-correlations__context">
              {correlation.context}
            </p>
          ) : null}
        </>
      ) : null}
    </li>
  );
}

/**
 * Renders the workspace's Correlations tab content. Callers only
 * render this once `InvestigationWorkspaceData` actually exists
 * (`useInvestigation()`'s `"success"`/`"partial"` states), matching
 * every other workspace region's convention.
 */
export function InvestigationCorrelations({ data }: InvestigationCorrelationsProps): ReactElement {
  const result = deriveInvestigationCorrelations(data);

  if (result.status === "unavailable") {
    return (
      <Card title="Correlations" className="investigation-correlations">
        <InfoNote>
          Correlation data unavailable for this investigation. This means the underlying
          indicator and threat-intelligence data needed to look for a relationship did not load
          -- not that a relationship search came back empty.
        </InfoNote>
      </Card>
    );
  }

  if (result.status === "empty") {
    return (
      <Card title="Correlations" className="investigation-correlations">
        <InfoNote>
          No explicit correlations found for this investigation. This does not mean the
          investigation is clean -- it means no explicit relationship exists in the current data.
          Correlation relationships are shown here only when the investigation's own data
          explicitly provides them, never inferred from indicators simply appearing together.
        </InfoNote>
      </Card>
    );
  }

  return (
    <Card title="Correlations" className="investigation-correlations">
      <ul className="investigation-correlations__list">
        {result.correlations.map((correlation, index) => (
          // Real relationships carry no stable identifier of their own
          // in the current model -- same rationale as `ProviderDetail`'s
          // array rendering (`ProviderDetail.tsx`) -- so `index` is still
          // part of this key. It is no longer the *entire* key (MAX-21B-4C-F1):
          // `WorkspaceTabs` keeps this component mounted in the same tree
          // position across investigations, so a plain `index` key let
          // React reuse a `CorrelationItem` instance -- and its local
          // `expanded` disclosure state -- across an investigation switch
          // whenever the new investigation's correlation list happened to
          // occupy the same position. Folding `data.investigationId` into
          // the key gives every item a distinct identity per investigation,
          // so switching investigations always mounts fresh `CorrelationItem`
          // instances with disclosure state starting collapsed, while still
          // never using array index as a correlation's *own* identity across
          // renders of the same investigation's data.
          // eslint-disable-next-line react/no-array-index-key
          <CorrelationItem key={`${data.investigationId ?? "none"}-${index}`} correlation={correlation} index={index} />
        ))}
      </ul>
    </Card>
  );
}
