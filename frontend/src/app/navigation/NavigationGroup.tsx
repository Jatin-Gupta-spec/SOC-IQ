import type { MouseEvent, ReactElement } from "react";
import { NavLink } from "react-router-dom";
import type { NavigationItem } from "./types";
import { settingsNavigationGuard } from "../../pages/settings/settingsNavigationGuardStore";

export interface NavigationGroupProps {
  readonly items: readonly NavigationItem[];
  /** Accessible group label (e.g. "Primary navigation", "Settings"). Not rendered visibly — the visual grouping is the divider in `NavigationRegion`. */
  readonly ariaLabel: string;
}

/**
 * Renders one navigation group as a list of links.
 *
 * Active state (§10) comes entirely from `react-router-dom`'s `NavLink`,
 * which derives `isActive` from the current route — there is no local
 * `useState` tracking "which item is selected" that could drift from
 * the router. `NavLink` also sets `aria-current="page"` on the active
 * link automatically, so active state is communicated to assistive
 * tech, not just visually.
 *
 * Per §16, active state must not be color-only: `nav-sidebar__link--active`
 * (see `navigation.css`) also changes font-weight and adds a left-edge
 * accent bar, so the distinction survives in grayscale/high-contrast
 * modes too.
 *
 * # Settings navigation guard (MAX-18 Phase 2A-3, MAX18-F-01)
 *
 * Every link's `onClick` first asks `settingsNavigationGuard`
 * (`pages/settings/settingsNavigationGuardStore.ts`) whether the
 * click may proceed. The guard itself decides -- based on whether
 * Settings is currently dirty and whether `item.path` actually leaves
 * it -- so this component carries no Settings-specific branching of
 * its own; it treats every item identically and simply respects
 * whatever the guard answers. A `"blocked"` answer calls
 * `event.preventDefault()`, which stops `NavLink`'s own default
 * navigation before the route changes -- the decision happens before
 * any destructive navigation, never as a revert after the fact. An
 * `"allowed"` answer (the overwhelming majority of clicks: any click
 * while Settings is clean, and every click that isn't leaving
 * Settings at all) leaves the event untouched, so `NavLink` navigates
 * exactly as it always has.
 */
export function NavigationGroup({
  items,
  ariaLabel,
}: NavigationGroupProps): ReactElement {
  return (
    <ul className="nav-sidebar__list" aria-label={ariaLabel}>
      {items.map((item) => {
        const Icon = item.icon;
        const handleClick = (event: MouseEvent<HTMLAnchorElement>): void => {
          if (settingsNavigationGuard.requestNavigation(item.path) === "blocked") {
            event.preventDefault();
          }
        };
        return (
          <li key={item.id} className="nav-sidebar__list-item">
            <NavLink
              to={item.path}
              onClick={handleClick}
              className={({ isActive }) =>
                isActive
                  ? "nav-sidebar__link nav-sidebar__link--active transition-color"
                  : "nav-sidebar__link transition-color"
              }
              aria-label={item.ariaLabel ?? item.label}
            >
              <Icon
                className="nav-sidebar__icon"
                aria-hidden="true"
                focusable="false"
              />
              <span className="nav-sidebar__label">{item.label}</span>
            </NavLink>
          </li>
        );
      })}
    </ul>
  );
}
