import type { ReactElement } from "react";
import { Card } from "../components/Card";
import { StatusBadge } from "../components/StatusBadge";
import { useSidecarStatus } from "../../shared/sidecar/useSidecarStatus";
import { sidecarProjection, type SidecarProjectionStore } from "../../shared/sidecar/projectionStore";
import { projectSidecarStatusView } from "../../shared/sidecar/sidecarStatusView";
import { toOperationalStatusViewModel } from "./dashboardViewModel";
import "./DashboardOperationalStatus.css";

export interface DashboardOperationalStatusProps {
  /**
   * Test-injection point only, mirroring `useSidecarStatus`'s own
   * `store` parameter (see that hook's doc comment) — production call
   * sites never pass this and always get the one application-wide
   * `sidecarProjection` singleton.
   */
  readonly store?: SidecarProjectionStore;
}

/**
 * Operational-status region (Phase 4H Part 1, §7/§12).
 *
 * The Dashboard's one piece of genuinely live data in this
 * checkpoint. Reads the existing, frozen sidecar projection via
 * `useSidecarStatus()` (4G-3) and the existing normalized vocabulary
 * via `projectSidecarStatusView()` — both consumed exactly as every
 * other reader of that projection does. This component does not
 * subscribe to Tauri events, does not poll, and does not own any
 * sidecar state of its own (task brief §12's three prohibitions).
 */
export function DashboardOperationalStatus({
  store = sidecarProjection,
}: DashboardOperationalStatusProps): ReactElement {
  const sidecarState = useSidecarStatus(store);
  const statusView = projectSidecarStatusView(sidecarState);
  const { label, tone } = toOperationalStatusViewModel(statusView);

  return (
    <Card title="Operational Status" className="dashboard-page__operational">
      <div className="dashboard-operational-status__row">
        <span className="dashboard-operational-status__label">Analysis engine</span>
        <StatusBadge label={label} tone={tone} />
      </div>
    </Card>
  );
}
