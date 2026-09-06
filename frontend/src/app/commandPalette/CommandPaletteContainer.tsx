/**
 * Command palette composition container — Phase 4G-5 Part 1.
 *
 * Owns exactly the two things `CommandPalette.tsx` and
 * `useCommandPaletteShortcut.ts` deliberately don't: the open/closed
 * state itself, and turning a selected command's `path` into a real
 * navigation via `react-router-dom`'s `useNavigate()` — which, unlike
 * `COMMANDS` (module-scope, router-free by design; see
 * `commandRegistry.ts`), only exists inside a component with `Router`
 * context. Mirrors `RestartExhaustedNotification`'s own composition
 * pattern: a dumb presentational component (`CommandPalette`) plus a
 * thin owner that wires it to the rest of the app, so the palette
 * itself stays testable without a router at all.
 *
 * `open`/`close`/`toggle` are all `useCallback`-stable across
 * renders — required for `useCommandPaletteShortcut`'s effect
 * dependency array to stay referentially stable too, so its
 * add/remove-listener effect does not re-run on every render (task
 * brief §9's "does not duplicate listeners" — technically safe
 * either way since the effect's own cleanup always removes what it
 * added, but stable callbacks avoid the needless churn).
 *
 * # Settings navigation guard (MAX-18 Phase 2A-3, MAX18-F-01)
 *
 * `handleNavigate` is the palette's one call site that turns a
 * selected command into a real route change, which makes it exactly
 * the place `settingsNavigationGuard.requestNavigation()` must be
 * consulted before `navigate()` runs — the destination is never
 * committed before that decision. A `"blocked"` result closes the
 * palette (so its overlay doesn't sit on top of the confirmation
 * dialog `AppShell` also mounts) and returns without navigating; an
 * `"allowed"` result runs the exact same `navigate(path); close();`
 * this container always performed, unchanged.
 */

import { useCallback, useState, type ReactElement } from "react";
import { useNavigate } from "react-router-dom";
import { CommandPalette } from "./CommandPalette";
import { useCommandPaletteShortcut } from "./useCommandPaletteShortcut";
import { COMMANDS } from "../../shared/commands/commandRegistry";
import { settingsNavigationGuard } from "../../pages/settings/settingsNavigationGuardStore";

export function CommandPaletteContainer(): ReactElement {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();

  const close = useCallback(() => setOpen(false), []);
  const toggle = useCallback(() => setOpen((current) => !current), []);

  useCommandPaletteShortcut(toggle);

  const handleNavigate = useCallback(
    (path: string) => {
      if (settingsNavigationGuard.requestNavigation(path) === "blocked") {
        close();
        return;
      }
      navigate(path);
      close();
    },
    [navigate, close],
  );

  return (
    <CommandPalette
      open={open}
      commands={COMMANDS}
      onClose={close}
      onNavigate={handleNavigate}
    />
  );
}
