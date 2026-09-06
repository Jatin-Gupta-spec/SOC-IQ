import type { ReactElement } from "react";
import { Card } from "../components/Card";
import type { DashboardQuickAction } from "./dashboardViewModel";
import "./DashboardQuickActions.css";

export interface DashboardQuickActionsProps {
  readonly actions: readonly DashboardQuickAction[];
}

/**
 * Quick-actions/navigation region (Phase 4H Part 1, §7/§13).
 *
 * Plain in-app links (`href="#{path}"`) to existing destinations —
 * the app is mounted under `HashRouter` (`app/App.tsx`), so an
 * anchor with a `#`-prefixed href navigates through the existing
 * router exactly as a sidebar click does, with no second navigation
 * or command system (task brief §13) and no dependency on router
 * context at render time (keeps this component testable the same
 * way every other page is — see `pages/pages.test.tsx`'s
 * `renderToStaticMarkup`-only convention).
 */
export function DashboardQuickActions({ actions }: DashboardQuickActionsProps): ReactElement {
  return (
    <Card title="Quick Actions" className="dashboard-page__quick-actions">
      <nav aria-label="Dashboard quick actions">
        <ul className="dashboard-quick-actions__list">
          {actions.map((action) => {
            const Icon = action.icon;
            return (
              <li key={action.id}>
                <a className="dashboard-quick-actions__link" href={`#${action.path}`}>
                  <Icon className="dashboard-quick-actions__icon" aria-hidden="true" />
                  <span>{action.label}</span>
                </a>
              </li>
            );
          })}
        </ul>
      </nav>
    </Card>
  );
}
