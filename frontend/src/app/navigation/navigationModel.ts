import {
  AnalyzeIcon,
  DashboardIcon,
  InvestigationsIcon,
  ReportsIcon,
  SettingsIcon,
} from "./icons";
import type { NavigationItem } from "./types";

/**
 * Centralized navigation model (Phase 4G-2 Part 2, §6/§7).
 *
 * The single source of truth for the sidebar's five destinations. Per
 * PD-05 (Retire top-level IOC Explorer + Threat Intel), the two former
 * top-level "IOC Explorer" and "Threat Intel" mock destinations have
 * been retired from primary navigation — real, investigation-scoped
 * IOC and Threat Intel views remain available inside the Investigation
 * Workspace (`Investigations` → an investigation → its `IOCs`/`Threat
 * Intel` tabs), which is unaffected by this change. Per PD-06 (Part 3,
 * Retire top-level Risk), the former top-level "Risk" mock destination
 * has likewise been retired — real, investigation-scoped risk/severity/
 * confidence data remains available inside the Investigation
 * Workspace's Overview tab (`InvestigationOverviewRisk.tsx`), which is
 * unaffected by this change. `path` doubles as each destination's
 * route identifier — there is exactly one identifier per destination,
 * consumed by both the sidebar (`NavigationGroup`) and the router
 * (`app/router.tsx`), so the two cannot drift apart.
 *
 * Grouping follows that same architecture: Settings is the one
 * "secondary" destination, everything else is "primary".
 */
export const NAVIGATION_ITEMS: readonly NavigationItem[] = [
  {
    id: "dashboard",
    label: "Dashboard",
    path: "/dashboard",
    icon: DashboardIcon,
    group: "primary",
  },
  {
    id: "analyze",
    label: "Analyze",
    path: "/analyze",
    icon: AnalyzeIcon,
    group: "primary",
  },
  {
    id: "investigations",
    label: "Investigations",
    path: "/investigations",
    icon: InvestigationsIcon,
    group: "primary",
  },
  {
    id: "reports",
    label: "Reports",
    path: "/reports",
    icon: ReportsIcon,
    group: "primary",
  },
  {
    id: "settings",
    label: "Settings",
    path: "/settings",
    icon: SettingsIcon,
    group: "secondary",
  },
] as const;

/** The destination the app lands on at "/" and on an unknown path. */
export const DEFAULT_NAVIGATION_PATH = "/dashboard";
