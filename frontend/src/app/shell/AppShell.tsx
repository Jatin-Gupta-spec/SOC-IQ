import type { ReactElement, ReactNode } from "react";
import { ContentRegion } from "./ContentRegion";
import { NavigationRegion } from "./NavigationRegion";
import { RestartExhaustedNotification } from "../../shared/notifications/RestartExhaustedNotification";
import { CommandPaletteContainer } from "../commandPalette/CommandPaletteContainer";
import { SettingsNavigationGuardDialog } from "./SettingsNavigationGuardDialog";
import "./AppShell.css";

export interface AppShellProps {
  readonly children: ReactNode;
}

/**
 * Application shell foundation (Phase 4G-2 Part 1; notification
 * mount added Phase 4G-4 Part 2).
 *
 * Establishes the structural layout every later Phase 4G-2 checkpoint
 * builds on: a navigation region and a main content region, side by
 * side. `AppShell` owns layout only — no domain data, no sidecar
 * state, no feature business logic (see
 * `docs/architecture/FILE_STRUCTURE.md`: `app/` "owns bootstrap only,
 * no business logic"). `App.tsx` mounts this once and passes
 * `AppRoutes` as `children`; Part 2 (navigation UI) and Part 3 (mock
 * pages) plug into `NavigationRegion` and this outlet respectively
 * without either of them needing to touch `App.tsx` again.
 *
 * # Restart-exhausted notification placement (4G-4 Part 2, task brief
 * §5)
 *
 * `RestartExhaustedNotification` is mounted here, as a sibling above
 * the nav/content row, not inside `NavigationRegion` or
 * `ContentRegion`. `AppShell` is mounted exactly once by `App.tsx`
 * and is never remounted by routing (`AppRoutes` only replaces
 * `ContentRegion`'s children), so this placement survives navigation
 * without duplicating, and never overlaps or displaces the nav
 * sidebar or page content — it occupies its own row, pushing the
 * nav/content row down rather than overlaying it. The component
 * itself renders `null` when not visible (see its own doc), so this
 * adds zero layout footprint in the normal, non-exhausted case — no
 * second notification system, just one more stable row in the
 * existing shell.
 *
 * # Command palette mount (4G-5 Part 1)
 *
 * `CommandPaletteContainer` is mounted as one more sibling here, for
 * the same "mounted exactly once, survives navigation" reason as the
 * notification above. It is not part of the `.app-shell__regions`
 * row: the palette renders as a fixed-position overlay
 * (`CommandPalette.css`), so — like the notification when not
 * visible — it occupies no layout space in the shell's flex flow
 * either way; its position in this JSX only fixes its place in the
 * DOM, not on screen.
 *
 * # Settings navigation guard dialog mount (MAX-18 Phase 2A-3,
 * MAX18-F-01)
 *
 * `SettingsNavigationGuardDialog` is mounted as one more sibling
 * here, for the identical "mounted once, survives navigation, needs
 * router context" reason `CommandPaletteContainer` already is: it
 * calls `useNavigate()` to perform the "Leave" navigation itself, and
 * it must still be present (and able to receive the guard's pending
 * state) no matter which page `ContentRegion` currently renders,
 * since the navigation it is confirming is, by definition, a
 * transition *away from* whatever page triggered it. Renders `null`
 * until a confirmation is actually pending (see its own doc), so —
 * like the two mounts above — it adds no layout footprint the rest
 * of the time.
 */
export function AppShell({ children }: AppShellProps): ReactElement {
  return (
    <div className="app-shell">
      <RestartExhaustedNotification />
      <div className="app-shell__regions">
        <NavigationRegion />
        <ContentRegion>{children}</ContentRegion>
      </div>
      <CommandPaletteContainer />
      <SettingsNavigationGuardDialog />
    </div>
  );
}
