import type { ReactElement } from "react";
import { PageLayout } from "./components/PageLayout";
import { PageHeader } from "./components/PageHeader";
import { Button } from "./components/Button";
import { Card } from "./components/Card";
import { DashboardMetrics } from "./dashboard/DashboardMetrics";
import { DashboardInvestigationOverview } from "./dashboard/DashboardInvestigationOverview";
import { DashboardRecentInvestigations } from "./dashboard/DashboardRecentInvestigations";
import { DashboardRiskOverview } from "./dashboard/DashboardRiskOverview";
import { DashboardIocOverview } from "./dashboard/DashboardIocOverview";
import { DashboardOperationalStatus } from "./dashboard/DashboardOperationalStatus";
import { DashboardQuickActions } from "./dashboard/DashboardQuickActions";
import { DashboardInvestigationActivity } from "./dashboard/DashboardInvestigationActivity";
import { useDashboard } from "./dashboard/useDashboard";
import { useInvestigationActivity } from "./dashboard/useInvestigationActivity";
import {
  buildDashboardQuickActions,
  toDashboardViewModel,
  toInvestigationActivityTrend,
} from "./dashboard/dashboardViewModel";
import { NAVIGATION_ITEMS } from "../app/navigation/navigationModel";
import { useReducedMotion } from "../shared/hooks/useReducedMotion";
import "./DashboardPage.css";

const quickActions = buildDashboardQuickActions(NAVIGATION_ITEMS);

function describeDashboardError(error: unknown): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return "An unknown error occurred while loading the dashboard.";
}

/**
 * Structural loading skeleton — mirrors `dashboard-page__grid`'s real
 * grid-template-areas so the loading state resembles the actual widget
 * geometry. No fake values, labels, percentages, names, or chart data
 * are rendered here; every block is an unlabeled placeholder. Reuses
 * the same 750ms opacity-pulse idiom already established by the
 * Investigation Workspace skeleton (`investigation-workspace-pulse`),
 * rather than inventing a new animation language.
 */
function DashboardSkeleton({ reducedMotion }: { readonly reducedMotion: boolean }): ReactElement {
  const pulseClass = reducedMotion
    ? "dashboard-page__skeleton-block"
    : "dashboard-page__skeleton-block dashboard-page__skeleton-block--pulse";

  return (
    <div className="dashboard-page__skeleton-grid" aria-hidden="true">
      <div className={`${pulseClass} dashboard-page__skeleton-metrics`} />
      <div className={`${pulseClass} dashboard-page__skeleton-operational`} />
      <div className={`${pulseClass} dashboard-page__skeleton-investigations`} />
      <div className={`${pulseClass} dashboard-page__skeleton-activity`} />
      <div className={`${pulseClass} dashboard-page__skeleton-recent`} />
      <div className={`${pulseClass} dashboard-page__skeleton-risk`} />
      <div className={`${pulseClass} dashboard-page__skeleton-ioc`} />
      <div className={`${pulseClass} dashboard-page__skeleton-quick`} />
    </div>
  );
}

/**
 * Dashboard page — Phase 4H Part 3 presentation/layout integration.
 *
 * The aggregate Dashboard data comes from exactly one command through
 * `useDashboard()`. The view-model maps that response into the existing
 * Dashboard widgets. Operational status and quick actions remain on their
 * existing real boundaries and are not duplicated here.
 *
 * Data ownership remains in the Phase 4H-P2 hook/view-model boundary. This
 * phase only composes those existing data regions into the Dashboard's
 * responsive 12-column presentation grid. Timeline and refresh policy remain
 * explicitly outside scope.
 */
export function DashboardPage(): ReactElement {
  const { state, dashboard, error, retry } = useDashboard();
  const {
    state: activityState,
    activity,
    error: activityError,
    retry: retryActivity,
  } = useInvestigationActivity();
  const reducedMotion = useReducedMotion();

  return (
    <PageLayout label="Dashboard page">
      <div className="dashboard-page">
        <PageHeader
        title="Dashboard"
        description="Security operations overview — active investigations, risk posture, and recent activity across SOC-IQ."
      />

        {state === "loading" ? (
        <section className="page-layout__section" aria-label="Dashboard loading">
          <p className="dashboard-page__visually-hidden" role="status" aria-live="polite">
            Loading dashboard data…
          </p>
          <DashboardSkeleton reducedMotion={reducedMotion} />
        </section>
      ) : null}

        {state === "error" ? (
        <section className="page-layout__section" aria-label="Dashboard error">
          <Card title="Dashboard Unavailable">
            <p className="dashboard-page__message" role="alert">
              {describeDashboardError(error)}
            </p>
            <div className="dashboard-page__actions">
              <Button className="dashboard-page__retry-button" onClick={retry}>
                Retry
              </Button>
            </div>
          </Card>
        </section>
      ) : null}

        {state === "success" && dashboard !== null ? (() => {
        const viewModel = toDashboardViewModel(dashboard);
        return (
          <div className="dashboard-page__grid">
            <section className="dashboard-page__metrics" aria-label="Key metrics">
              <DashboardMetrics metrics={viewModel.metrics} />
            </section>

            <section className="dashboard-page__operational" aria-label="Operational status">
              <DashboardOperationalStatus />
            </section>

            <section className="dashboard-page__investigations" aria-label="Investigation overview">
              <DashboardInvestigationOverview workload={viewModel.investigationWorkload} />
            </section>

            <section className="dashboard-page__recent" aria-label="Recent investigations">
              <DashboardRecentInvestigations investigations={viewModel.recentInvestigations} />
            </section>

            <section className="dashboard-page__risk" aria-label="Risk distribution">
              <DashboardRiskOverview distribution={viewModel.riskDistribution} />
            </section>

            <section className="dashboard-page__ioc" aria-label="IOC distribution">
              <DashboardIocOverview distribution={viewModel.iocDistribution} />
            </section>

            <section className="dashboard-page__quick-actions" aria-label="Quick actions">
              <DashboardQuickActions actions={quickActions} />
            </section>

            <section className="dashboard-page__activity" aria-label="Investigation activity">
              {activityState === "loading" ? (
                <Card title="Investigation Activity">
                  <p className="dashboard-page__visually-hidden" role="status" aria-live="polite">
                    Loading investigation activity…
                  </p>
                  <div
                    className={
                      reducedMotion
                        ? "dashboard-page__skeleton-block"
                        : "dashboard-page__skeleton-block dashboard-page__skeleton-block--pulse"
                    }
                    aria-hidden="true"
                    style={{ height: "120px" }}
                  />
                </Card>
              ) : null}

              {activityState === "error" ? (
                <Card title="Investigation Activity">
                  <p className="dashboard-page__message" role="alert">
                    {describeDashboardError(activityError)}
                  </p>
                  <div className="dashboard-page__actions">
                    <Button className="dashboard-page__retry-button" onClick={retryActivity}>
                      Retry
                    </Button>
                  </div>
                </Card>
              ) : null}

              {activityState === "success" && activity !== null ? (
                <DashboardInvestigationActivity
                  trend={toInvestigationActivityTrend(activity.investigations_by_date)}
                />
              ) : null}
            </section>
          </div>
        );
      })() : null}
      </div>
    </PageLayout>
  );
}
