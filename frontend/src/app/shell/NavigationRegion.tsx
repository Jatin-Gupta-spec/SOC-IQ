import type { ReactElement } from "react";
import { NAVIGATION_ITEMS } from "../navigation/navigationModel";
import { NavigationGroup } from "../navigation/NavigationGroup";
import { SidecarStatusIndicator } from "../../shared/components/SidecarStatusIndicator";
import "../navigation/navigation.css";

/**
 * Navigation region — real sidebar UI (Phase 4G-2 Part 2; sidecar
 * status footer added Phase 4G-3 Part 2).
 *
 * Was a bare structural placeholder in Part 1; Phase 4G-2 Part 2
 * filled it in with the actual primary/secondary navigation, built
 * entirely from the centralized `NAVIGATION_ITEMS` model (§6) so
 * there is one source of truth for labels/paths/icons, not scattered
 * per-component strings. Layout sizing (width/border/background)
 * still lives in `AppShell.css`'s `.app-shell__navigation-region` —
 * this component keeps that class and adds `.nav-sidebar` for the
 * sidebar's own internal layout (`navigation.css`), rather than
 * duplicating the region's box model here.
 *
 * Phase 4G-3 Part 2 adds one more fixed element at the bottom of that
 * same sidebar: `SidecarStatusIndicator`, in its own footer band
 * (`.nav-sidebar__footer`, `navigation.css`) below the secondary nav
 * group — a stable, always-visible location per task brief §4,
 * chosen over the content region so it stays visible regardless of
 * which page is routed. `NavigationRegion` only mounts it here; all
 * status-reading/projection logic remains entirely inside
 * `SidecarStatusIndicator` and the Part 1 consumer it reads from —
 * this file gains no sidecar-specific logic of its own.
 */
export function NavigationRegion(): ReactElement {
  const primaryItems = NAVIGATION_ITEMS.filter(
    (item) => item.group === "primary",
  );
  const secondaryItems = NAVIGATION_ITEMS.filter(
    (item) => item.group === "secondary",
  );

  return (
    <nav
      className="app-shell__navigation-region nav-sidebar"
      aria-label="Primary navigation"
    >
      <div className="nav-sidebar__brand">SOC-IQ</div>
      <NavigationGroup items={primaryItems} ariaLabel="Primary" />
      <div className="nav-sidebar__spacer" />
      <hr className="nav-sidebar__divider" />
      <NavigationGroup items={secondaryItems} ariaLabel="Settings" />
      <div className="nav-sidebar__footer">
        <SidecarStatusIndicator />
      </div>
    </nav>
  );
}
