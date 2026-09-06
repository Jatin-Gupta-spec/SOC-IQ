/**
 * Investigation Workspace foundation — Phase 4J-6 Part 1A, extended in
 * Part 1B with the Investigation Header Card, in Part 1C with the
 * real Risk/Summary Overview content, in Part 1D with a compact IOC
 * summary, Threat Intelligence summary, and an honest timeline
 * foundation, in Part 2A with the real IOC workspace tab, in Part 3A
 * with the real Threat Intel tab foundation, and in Part 4A with the
 * Correlations tab foundation.
 *
 * Establishes the workspace page component itself, its state-machine
 * handling of every `useInvestigation()` (Phase 4J-4) load state, a
 * tab shell (Overview / IOCs / Threat Intel / Correlations, all four
 * real and selectable as of Part 4A) with the identity/risk/status header
 * (`InvestigationHeaderCard`, Part 1B), the Overview's real risk and
 * investigation-summary content
 * (`InvestigationOverviewRisk`/`InvestigationOverviewSummary`, Part
 * 1C), the Overview's compact IOC distribution summary
 * (`InvestigationOverviewIOC`), Threat Intelligence state summary
 * (`InvestigationOverviewThreatIntel`), and one-event-at-most honest
 * timeline (`InvestigationOverviewTimeline`, all Part 1D), (Part 2A)
 * the IOCs tab's real, detailed workspace
 * (`InvestigationIocWorkspace`) built from the same normalized data,
 * (Part 3A) the Threat Intel tab's real foundation content
 * (`InvestigationThreatIntel`), and (Part 4A) the Correlations tab's
 * honest relationship-presentation foundation
 * (`InvestigationCorrelations`) -- real explicit relationships if the
 * data ever carries one, an honest "no explicit correlations" state
 * otherwise, never a fabricated relationship. Deliberately does NOT
 * implement per-IOC/provider TI detail views, a raw JSON payload
 * viewer, enrichment actions, correlation graph visualization,
 * editing/deletion, bulk actions, or a multi-stage fabricated
 * activity feed — those remain later parts' scope (task brief §2/§3,
 * §22). This page only proves the
 * workspace mounts, reads real data through the existing
 * `useInvestigation()` / `normalizeInvestigationWorkspace()` boundary
 * (Phase 4J-4/4J-5), and never fabricates a value for data that
 * hasn't actually loaded.
 *
 * Reuses the existing design system exclusively (`PageLayout`,
 * `PageHeader`, `Card`, `StatusBadge`, `InvestigationHeaderCard`,
 * `InvestigationOverviewRisk`, `InvestigationOverviewSummary`,
 * `InvestigationOverviewIOC`, `InvestigationOverviewThreatIntel`,
 * `InvestigationOverviewTimeline`, `InvestigationIocWorkspace`,
 * `InvestigationThreatIntel`, `InvestigationCorrelations`) — no
 * second visual language is introduced, per the task brief's hard
 * rules.
 */

import { useCallback, useMemo, useRef, type KeyboardEvent, type ReactElement } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { PageLayout } from "../components/PageLayout";
import { PageHeader } from "../components/PageHeader";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { StatusBadge } from "../components/StatusBadge";
import { useReducedMotion } from "../../shared/hooks/useReducedMotion";
import { useInvestigation } from "./useInvestigation";
import { normalizeInvestigationWorkspace, type InvestigationWorkspaceData } from "./investigationWorkspaceModel";
import { InvestigationHeaderCard } from "./InvestigationHeaderCard";
import { InvestigationOverviewRisk } from "./InvestigationOverviewRisk";
import { InvestigationOverviewSummary } from "./InvestigationOverviewSummary";
import { InvestigationOverviewIOC } from "./InvestigationOverviewIOC";
import { InvestigationOverviewThreatIntel } from "./InvestigationOverviewThreatIntel";
import { InvestigationOverviewTimeline } from "./InvestigationOverviewTimeline";
import { InvestigationIocWorkspace } from "./InvestigationIocWorkspace";
import { InvestigationThreatIntel } from "./InvestigationThreatIntel";
import { InvestigationCorrelations } from "./InvestigationCorrelations";
import "./InvestigationWorkspacePage.css";

const INVESTIGATIONS_PATH = "/investigations";

/** The workspace's tabs -- all four are real and selectable as of
 * Part 4A (task brief §5/§21): Overview (Part 1C/1D), IOCs (Part
 * 2A-2D), Threat Intel (Part 3A-3D), and Correlations (Part 4A's
 * foundation content). */
const WORKSPACE_TABS = [
  { id: "overview", label: "Overview" },
  { id: "iocs", label: "IOCs" },
  { id: "threat-intel", label: "Threat Intel" },
  { id: "correlations", label: "Correlations" },
] as const;

type WorkspaceTabId = (typeof WORKSPACE_TABS)[number]["id"];

/** MAX7-F-02: the URL is the one source of truth for which tab is
 * active (see the `activeTab`/`setActiveTab` derivation below), so
 * any raw `?tab=` value read back off the URL -- typed straight from
 * the query string, hand-edited link, or a stale bookmark -- has to
 * be validated against the real tab id set before it's trusted.
 * Anything that isn't one of `WORKSPACE_TABS`' own ids (including a
 * missing/empty param) falls back to "overview", never a blank panel
 * or a thrown error. */
function isWorkspaceTabId(value: string | null): value is WorkspaceTabId {
  return WORKSPACE_TABS.some((tab) => tab.id === value);
}

const TAB_QUERY_PARAM = "tab";

export interface InvestigationWorkspacePageProps {
  /** The already-validated numeric investigation ID from the route
   * layer (`app/investigationRouteParams.ts`'s `parseInvestigationId()`,
   * Phase 4J-3). This page never re-parses a raw route string itself
   * -- see `useInvestigation.ts`'s own doc comment for why that would
   * duplicate route-parsing logic. */
  readonly investigationId: number;
}

/**
 * Renders the raw rejection `useInvestigation()` exposes as
 * `investigationError` into one human-readable line, preferring the
 * backend's own message (`CommandFailedError`/`CommandClientError`/
 * `SidecarNotConnectedError` are all real `Error` subclasses) over an
 * invented one -- task brief §7: "Do not invent an error message if a
 * useful existing message is available."
 */
function describeInvestigationError(error: unknown): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return "An unknown error occurred while loading this investigation.";
}

function WorkspaceSkeleton({ reducedMotion }: { readonly reducedMotion: boolean }): ReactElement {
  const pulseClass = reducedMotion
    ? "investigation-workspace__skeleton-block"
    : "investigation-workspace__skeleton-block investigation-workspace__skeleton-block--pulse";

  return (
    <div className="investigation-workspace__skeleton" aria-hidden="true">
      {/* Structural placeholder for the Part 1B header card -- no
          investigation ID, score, or confidence is known yet, so this
          is an unlabeled block, never a fabricated "Investigation #0"
          or "0%" (task brief §12). */}
      <div className={`${pulseClass} investigation-workspace__skeleton-header`} />
      <div className={`${pulseClass} investigation-workspace__skeleton-tabs`} />
      <div className={`${pulseClass} investigation-workspace__skeleton-content`} />
    </div>
  );
}

function BackToInvestigationsButton(): ReactElement {
  const navigate = useNavigate();
  return (
    <button
      type="button"
      className="investigation-workspace__secondary-button"
      onClick={() => navigate(INVESTIGATIONS_PATH)}
    >
      Back to Investigations
    </button>
  );
}

interface WorkspaceTabsProps {
  readonly warnings: readonly string[];
  readonly data: InvestigationWorkspaceData;
  readonly activeTab: WorkspaceTabId;
  readonly onSelectTab: (tabId: WorkspaceTabId) => void;
}

/**
 * Tab shell (task brief §10, Part 1A), rendering the real Overview
 * content (Part 1C/1D) for the "overview" tab, the real IOC workspace
 * (`InvestigationIocWorkspace`, Part 2A) for the "iocs" tab, the real
 * Threat Intel foundation content (`InvestigationThreatIntel`, Part
 * 3A) for the "threat-intel" tab, and (Part 4A) the Correlations
 * foundation content (`InvestigationCorrelations`) for the
 * "correlations" tab. All four tabs are real, selectable local
 * workspace state -- no tab ever navigates to an unrelated top-level
 * page (`/ioc-explorer`, `/threat-intel` are explicitly out of scope
 * here -- selection is local workspace state only, task brief §5/§21),
 * and switching between tabs never triggers a new fetch
 * (`useInvestigation()` above this component owns fetching; tab
 * selection is purely a local render choice, task brief §12/§23).
 *
 * Frontend MAX-1 (Accessibility Foundation) turns this into a proper
 * WAI-ARIA tab interface on top of the same `activeTab` state that
 * already drove the pre-existing click behavior -- no second
 * navigation system or state source was introduced. Each tab button
 * gets a stable, deterministic `id`/`aria-controls` pair
 * (`investigation-workspace-tab-<tabId>` /
 * `investigation-workspace-panel-<tabId>`, derived directly from
 * `WORKSPACE_TABS`'s own ids), roving `tabIndex` (0 on the active
 * tab, -1 on the rest), and `ArrowRight`/`ArrowLeft`/`Home`/`End`
 * keyboard handling that both selects the target tab and moves real
 * DOM focus to it -- matching the existing automatic-activation click
 * behavior (selecting a tab is always cheap/local, task brief
 * §12/§23, so there is no reason for a slower "focus first, activate
 * on Enter/Space" pattern here). Only the active panel is ever
 * mounted (unchanged from the pre-MAX-1 behavior), so it is rendered
 * as a single `role="tabpanel"` whose `id`/`aria-labelledby` track
 * whichever tab is currently active.
 */
function WorkspaceTabs({ warnings, data, activeTab, onSelectTab }: WorkspaceTabsProps): ReactElement {
  // Roving-tabindex focus targets -- populated via each tab button's
  // ref callback below. Kept as a plain ref (not state) since focus
  // is an imperative DOM concern, not something that should trigger a
  // re-render on its own.
  const tabRefs = useRef<Partial<Record<WorkspaceTabId, HTMLButtonElement>>>({});

  const selectAndFocusTab = (tabId: WorkspaceTabId): void => {
    onSelectTab(tabId);
    tabRefs.current[tabId]?.focus();
  };

  const handleTabKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number): void => {
    const lastIndex = WORKSPACE_TABS.length - 1;
    let nextIndex: number;

    switch (event.key) {
      case "ArrowRight":
        nextIndex = index === lastIndex ? 0 : index + 1;
        break;
      case "ArrowLeft":
        nextIndex = index === 0 ? lastIndex : index - 1;
        break;
      case "Home":
        nextIndex = 0;
        break;
      case "End":
        nextIndex = lastIndex;
        break;
      default:
        // Any other key (including Tab, Enter, Space) keeps the
        // browser's default behavior -- this handler only owns the
        // four WAI-ARIA tab-navigation keys.
        return;
    }

    // Prevent the page from scrolling on Home/End/arrow keys once
    // we're handling them ourselves.
    event.preventDefault();
    const nextTab = WORKSPACE_TABS[nextIndex];
    if (nextTab) {
      selectAndFocusTab(nextTab.id);
    }
  };

  const activePanelClassName =
    activeTab === "overview"
      ? "investigation-workspace__content investigation-workspace__overview"
      : "investigation-workspace__content";

  return (
    <div className="investigation-workspace__shell">
      <div className="investigation-workspace__tabs" role="tablist" aria-label="Investigation workspace sections">
        {WORKSPACE_TABS.map((tab, index) => {
          const active = tab.id === activeTab;
          return (
            <button
              key={tab.id}
              ref={(el) => {
                if (el) {
                  tabRefs.current[tab.id] = el;
                } else {
                  delete tabRefs.current[tab.id];
                }
              }}
              type="button"
              role="tab"
              id={`investigation-workspace-tab-${tab.id}`}
              aria-selected={active}
              aria-controls={`investigation-workspace-panel-${tab.id}`}
              tabIndex={active ? 0 : -1}
              className={
                active
                  ? "investigation-workspace__tab investigation-workspace__tab--active"
                  : "investigation-workspace__tab"
              }
              onClick={() => onSelectTab(tab.id)}
              onKeyDown={(event) => handleTabKeyDown(event, index)}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      {warnings.length > 0 ? (
        <div className="investigation-workspace__warnings">
          {warnings.map((warning) => (
            <StatusBadge key={warning} label={warning} tone="warning" />
          ))}
        </div>
      ) : null}

      <div
        key={activeTab}
        role="tabpanel"
        id={`investigation-workspace-panel-${activeTab}`}
        aria-labelledby={`investigation-workspace-tab-${activeTab}`}
        tabIndex={0}
        className={`${activePanelClassName} investigation-workspace__content--enter`}
      >
        {activeTab === "iocs" ? (
          <InvestigationIocWorkspace data={data} />
        ) : activeTab === "threat-intel" ? (
          <InvestigationThreatIntel data={data} />
        ) : activeTab === "correlations" ? (
          <InvestigationCorrelations data={data} />
        ) : (
          <>
            <InvestigationOverviewRisk data={data} />
            <InvestigationOverviewSummary data={data} />
            <InvestigationOverviewIOC data={data} />
            <InvestigationOverviewThreatIntel data={data} />
            <InvestigationOverviewTimeline data={data} />
          </>
        )}
      </div>
    </div>
  );
}


export function InvestigationWorkspacePage({
  investigationId,
}: InvestigationWorkspacePageProps): ReactElement {
  const { state, data, investigationError, iocsError, threatIntelligenceError, timelineError, riskExplanationError, retry } =
    useInvestigation(investigationId);
  const reducedMotion = useReducedMotion();
  // MAX7-F-02: which tab is selected is read from (and written back
  // to) the URL's `?tab=` query parameter, not local component state
  // -- so a reload, a shared link, or the browser back/forward button
  // returns to the same tab an analyst was actually looking at,
  // instead of silently resetting to Overview. This still has no
  // bearing on `useInvestigation()`'s own generation/stale-response
  // protection: investigation switching still always renders the
  // current investigation's real data on whichever tab the URL
  // resolves to (a link built without a `?tab=` value, e.g. every
  // existing Dashboard/Investigations/Reports row link, simply
  // resolves to "overview" -- see `isWorkspaceTabId()`).
  const [searchParams, setSearchParams] = useSearchParams();
  const rawActiveTab = searchParams.get(TAB_QUERY_PARAM);
  const activeTab: WorkspaceTabId = isWorkspaceTabId(rawActiveTab) ? rawActiveTab : "overview";

  // `replace: true` -- switching tabs updates the current history
  // entry's query string rather than pushing a new one, so the
  // existing MAX-1 keyboard tab navigation (ArrowRight/Left/Home/End,
  // §"WorkspaceTabs" below) doesn't turn every keypress into its own
  // back-button stop; the browser back button still lands an analyst
  // back on this investigation with whichever tab was active when
  // they navigated away, which is what MAX7-F-02 asks for.
  const setActiveTab = useCallback(
    (tabId: WorkspaceTabId): void => {
      setSearchParams(
        (previous) => {
          const next = new URLSearchParams(previous);
          if (tabId === "overview") {
            next.delete(TAB_QUERY_PARAM);
          } else {
            next.set(TAB_QUERY_PARAM, tabId);
          }
          return next;
        },
        { replace: true },
      );
    },
    [setSearchParams],
  );

  // Only computed once an investigation has actually loaded -- never
  // called for "loading"/"notFound"/"error" (normalizeInvestigationWorkspace
  // requires a real GetInvestigationResult, see its own doc comment).
  const normalized = useMemo(() => {
    if (data.investigation === null) {
      return null;
    }
    return normalizeInvestigationWorkspace(
      data.investigation,
      data.iocs,
      data.threatIntelligence,
      data.timeline ?? null,
      data.riskExplanation ?? null,
      data.iocSignificance ?? null,
    );
  }, [
    data.investigation,
    data.iocs,
    data.threatIntelligence,
    data.timeline,
    data.riskExplanation,
    data.iocSignificance,
  ]);

  if (state === "notFound") {
    return (
      <PageLayout label="Investigation Workspace page">
        <PageHeader
          title="Investigation Workspace"
          description="Investigation not found."
        />
        <section className="page-layout__section">
          <Card>
            <p className="investigation-workspace__message">Investigation not found</p>
            <p className="investigation-workspace__message investigation-workspace__message--muted">
              Investigation ID: {investigationId}
            </p>
            <BackToInvestigationsButton />
          </Card>
        </section>
      </PageLayout>
    );
  }

  if (state === "error") {
    return (
      <PageLayout label="Investigation Workspace page">
        <PageHeader
          title="Investigation Workspace"
          description="Something went wrong loading this investigation."
        />
        <section className="page-layout__section">
          <Card>
            <p className="investigation-workspace__message" role="alert">
              {describeInvestigationError(investigationError)}
            </p>
            <div className="investigation-workspace__actions">
              <Button onClick={retry}>Retry</Button>
              <BackToInvestigationsButton />
            </div>
          </Card>
        </section>
      </PageLayout>
    );
  }

  if (state === "success" || state === "partial") {
    // Guarded by the state check above -- `useInvestigation()` never
    // reports "success"/"partial" without a loaded investigation, so
    // this can only be null if that contract is violated; treat it as
    // still-loading rather than crash or fabricate data.
    if (normalized === null) {
      return (
        <PageLayout label="Investigation Workspace page">
          <PageHeader title="Investigation Workspace" description="Loading investigation…" />
          <section className="page-layout__section">
            <WorkspaceSkeleton reducedMotion={reducedMotion} />
          </section>
        </PageLayout>
      );
    }

    const warnings: string[] = [];
    if (iocsError !== null) {
      warnings.push("IOC data unavailable");
    }
    if (threatIntelligenceError !== null) {
      warnings.push("Threat Intelligence data unavailable");
    }
    // `timelineError` is optional on `UseInvestigationResult` (see that
    // type's own doc comment) purely so pre-Part-5A test doubles keep
    // compiling -- the real hook always sets it to `null` or a real
    // error, never leaves it `undefined`, but this page still treats
    // `undefined` the same as `null` ("no failure") rather than
    // fabricating a warning for a section a caller simply didn't
    // report on.
    if (timelineError !== null && timelineError !== undefined) {
      warnings.push("Timeline data unavailable");
    }
    // `riskExplanationError` is optional on `UseInvestigationResult` for
    // the same reason `timelineError` is (see that field's own doc
    // comment) -- treats `undefined` the same as `null` ("no failure").
    if (riskExplanationError !== null && riskExplanationError !== undefined) {
      warnings.push("Risk explanation unavailable");
    }

    return (
      <PageLayout label="Investigation Workspace page">
        <PageHeader
          title="Investigation Workspace"
          description="Identity, risk, and analysis status for this investigation."
        />
        <section className="page-layout__section">
          <InvestigationHeaderCard data={normalized} />
        </section>
        <section className="page-layout__section">
          <WorkspaceTabs warnings={warnings} data={normalized} activeTab={activeTab} onSelectTab={setActiveTab} />
        </section>
      </PageLayout>
    );
  }

  // "idle" and "loading" -- idle only occurs defensively (an invalid
  // id somehow reaching this page despite the route layer's own
  // validation, see `useInvestigation.ts`'s doc comment); both render
  // the same honest loading shell rather than distinguishing a state
  // the route layer already prevents in practice.
  return (
    <PageLayout label="Investigation Workspace page">
      <PageHeader title="Investigation Workspace" description="Loading investigation…" />
      <section className="page-layout__section">
        <WorkspaceSkeleton reducedMotion={reducedMotion} />
      </section>
    </PageLayout>
  );
}
