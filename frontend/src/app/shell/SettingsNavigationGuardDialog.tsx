/**
 * Settings navigation guard confirmation dialog — SOC-IQ MAX-18
 * Phase 2A-3 (MAX18-F-01).
 *
 * Renders `null` until `settingsNavigationGuard`
 * (`pages/settings/settingsNavigationGuardStore.ts`) has a pending
 * confirmation — the same "adds nothing to the page when inactive"
 * convention `RestartExhaustedNotification.tsx` and `CommandPalette.tsx`
 * already establish. This is the one place in the app that turns the
 * guard's `"blocked"` decision into something the person can actually
 * act on: Stay (`store.cancel()`, remain on Settings with edits
 * intact) or Leave (`store.confirmLeave()`, then navigate to the
 * destination it returns).
 *
 * Mounted once by `AppShell`, alongside `CommandPaletteContainer`, for
 * the identical reason that container is mounted there: it needs
 * `useNavigate()`'s router context, which only exists inside
 * `HashRouter`, and it must survive every route change rather than be
 * remounted by `AppRoutes` swapping pages in and out.
 *
 * # Scope (task brief's "confirmation UI polish" is explicitly OUT)
 *
 * This is the minimum accessible, functional confirmation this
 * finding requires — plain markup, the existing `.transition-fade`
 * utility (no new motion system), and only tokens already defined in
 * `styles/tokens.css`. No animation choreography, iconography, or
 * visual-design pass beyond what `CommandPalette.css` already
 * established for an equivalent overlay+dialog pair.
 *
 * # Accessibility
 *
 * `role="alertdialog"` (not the plain `role="dialog"` `CommandPalette`
 * uses) — this dialog exists specifically to demand a decision before
 * the person can do anything else, the textbook `alertdialog` case,
 * distinct from the palette's own non-modal-blocking search UI.
 * `aria-labelledby`/`aria-describedby` name and describe the surface
 * from its own visible heading/body text, so no separate `aria-label`
 * duplicates it. Focus moves onto the dialog itself the moment it
 * appears (task brief's "user receives the confirmation flow") and is
 * restored to whatever had it before, on Stay, mirroring
 * `CommandPalette.tsx`'s own MAX15-F-01 capture/restore pattern
 * exactly. On Leave there is nothing to restore to — the destination
 * page is about to mount, and `ContentRegion`'s MAX-17 route-change
 * focus management (unaffected by this checkpoint) takes over from
 * there.
 *
 * # Phase 2A-4 additions (confirmation UX + accessibility)
 *
 * Two gaps remained after 2A-3 that this checkpoint closes, both
 * confined to this file:
 *
 * - **Escape had no handler at all.** It is now given the same,
 *   intentional result as Stay — it never discards the pending edit
 *   and never runs `confirmLeave()`. Silently discarding data on an
 *   easily-mis-hit key would undercut the same "the person must be
 *   able to tell exactly what will happen" goal the two button
 *   labels exist to serve.
 * - **Nothing kept keyboard focus inside the dialog.** `aria-modal`
 *   is a promise to assistive tech that background content is
 *   unreachable while the dialog is open; without a trap, Tab from
 *   the Leave button (or Shift+Tab from Stay) could land on the
 *   sidebar or another background control sitting right behind the
 *   backdrop. `handleKeyDown` below adds a minimal, dependency-free
 *   wrap: Tab from the last focusable control cycles to the first,
 *   Shift+Tab from the first — or from the dialog container itself,
 *   before any Tab has been pressed — cycles to the last. No shared
 *   focus-trap primitive exists anywhere in this codebase (checked
 *   before writing this), so, consistent with this dialog's existing
 *   "local to this finding, not a generic framework" scope, the trap
 *   lives here rather than as a new shared utility.
 */

import {
  useEffect,
  useRef,
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactElement,
} from "react";
import { useNavigate } from "react-router-dom";
import { useSettingsNavigationGuardState } from "../../pages/settings/useSettingsNavigationGuardState";
import {
  settingsNavigationGuard,
  type SettingsNavigationGuardStore,
} from "../../pages/settings/settingsNavigationGuardStore";
import "./SettingsNavigationGuardDialog.css";

export interface SettingsNavigationGuardDialogProps {
  /** Test-injection point only, mirroring
   * `RestartExhaustedNotification`'s own `store` prop — production
   * callers never pass it. */
  readonly store?: SettingsNavigationGuardStore;
}

export function SettingsNavigationGuardDialog({
  store = settingsNavigationGuard,
}: SettingsNavigationGuardDialogProps): ReactElement | null {
  const state = useSettingsNavigationGuardState(store);
  const navigate = useNavigate();
  const dialogRef = useRef<HTMLDivElement>(null);

  // MAX15-F-01-style capture/restore: the element that had focus
  // immediately before the dialog opened, so Stay can put focus back
  // there instead of stranding it on `<body>`.
  const previouslyFocusedRef = useRef<HTMLElement | null>(null);
  const wasPendingRef = useRef(false);

  useEffect(() => {
    const becamePending = state.pending && !wasPendingRef.current;
    const becameIdle = !state.pending && wasPendingRef.current;

    if (becamePending) {
      previouslyFocusedRef.current =
        document.activeElement instanceof HTMLElement
          ? document.activeElement
          : null;
      dialogRef.current?.focus();
    }

    if (becameIdle) {
      const target = previouslyFocusedRef.current;
      previouslyFocusedRef.current = null;
      if (target && document.contains(target)) {
        target.focus();
      }
    }

    wasPendingRef.current = state.pending;
  }, [state.pending]);

  if (!state.pending) {
    return null;
  }

  const handleStay = (): void => {
    store.cancel();
  };

  const handleLeave = (): void => {
    const targetPath = store.confirmLeave();
    if (targetPath !== null) {
      navigate(targetPath);
    }
  };

  // Phase 2A-4: Escape gets the same, intentional, non-destructive
  // result as Stay (see the file-level doc above) rather than being
  // left unhandled or accidentally confirming the destructive path.
  //
  // Phase 2A-4: a minimal Tab/Shift+Tab focus trap. `dialogRef` (the
  // alertdialog container) is `tabIndex={-1}` so it is never itself
  // part of the browser's normal Tab sequence -- Tab/Shift+Tab are
  // computed relative to whatever currently has focus regardless of
  // that element's own tabindex, so the dialog container being the
  // *initial* focus target (see the effect above) must still be
  // handled explicitly, alongside the two buttons, or a Shift+Tab
  // immediately after opening would jump straight to whatever
  // precedes the dialog in the DOM.
  const handleKeyDown = (event: ReactKeyboardEvent<HTMLDivElement>): void => {
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      handleStay();
      return;
    }

    if (event.key !== "Tab") {
      return;
    }

    const dialogNode = dialogRef.current;
    if (!dialogNode) {
      return;
    }

    const focusable = Array.from(
      dialogNode.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
      ),
    );
    if (focusable.length === 0) {
      return;
    }

    const first = focusable[0] as HTMLElement;
    const last = focusable[focusable.length - 1] as HTMLElement;
    const active = document.activeElement;

    if (event.shiftKey) {
      if (active === first || active === dialogNode) {
        event.preventDefault();
        last.focus();
      }
    } else if (active === last) {
      event.preventDefault();
      first.focus();
    }
  };

  return (
    <div className="settings-nav-guard-backdrop transition-fade">
      <div
        ref={dialogRef}
        className="settings-nav-guard"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="settings-nav-guard-title"
        aria-describedby="settings-nav-guard-description"
        tabIndex={-1}
        onKeyDown={handleKeyDown}
      >
        <p id="settings-nav-guard-title" className="settings-nav-guard__title">
          Unsaved changes
        </p>
        <p
          id="settings-nav-guard-description"
          className="settings-nav-guard__description"
        >
          You have unsaved changes on the Settings page. Leaving now will
          discard them.
        </p>
        <div className="settings-nav-guard__actions">
          <button
            type="button"
            className="settings-nav-guard__button settings-nav-guard__button--stay"
            onClick={handleStay}
          >
            Stay
          </button>
          <button
            type="button"
            className="settings-nav-guard__button settings-nav-guard__button--leave"
            onClick={handleLeave}
          >
            Leave
          </button>
        </div>
      </div>
    </div>
  );
}
