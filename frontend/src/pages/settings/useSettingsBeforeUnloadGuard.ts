/**
 * `useSettingsBeforeUnloadGuard` -- SOC-IQ MAX-18 Phase 2A-5
 * (MAX18-F-01, browser `beforeunload` protection).
 *
 * Phase 2A-3/2A-4 built a complete guard against leaving Settings via
 * *in-app* SPA navigation (sidebar links, the command palette) with
 * unsaved edits. None of that touches the case where the person tries
 * to leave the SPA/browser context entirely -- closing the tab,
 * closing the window, reloading, or navigating the browser chrome to
 * a different URL. `SettingsNavigationGuardStore`'s `requestNavigation`
 * is a decision a caller inside this application makes before
 * committing a route change it controls; a tab close or reload is not
 * mediated by any of this app's own code at all, so it needs its own,
 * separate protection: the browser-native `beforeunload` event. This
 * hook is that protection, and it is purely additive -- it does not
 * read from or write to `settingsNavigationGuard` and does not change
 * anything about the existing in-app guard.
 *
 * # Lifecycle (task brief's explicit requirements)
 *
 * Takes the same `settingsDirty` aggregate `SettingsPage` already
 * computes (Phase 2A-2) and passes to `useSettingsNavigationGuardSync`
 * (Phase 2A-3) -- no new dirty *logic*, only a second consumer of the
 * one existing boolean. A single `useEffect` keyed on `settingsDirty`:
 *
 *   - registers the listener only when `settingsDirty` is `true` on
 *     the render that runs the effect (an early return skips
 *     registration entirely while clean);
 *   - is torn down by React's own effect-cleanup rule every time
 *     `settingsDirty` changes value *and* on unmount, and is
 *     re-registered by the same rule's re-run whenever the new value
 *     is again `true` -- there is no separate "remove" case to write:
 *     going dirty->clean, or unmounting while dirty, both simply run
 *     the one cleanup function this effect returns, and it is a
 *     no-op to call `removeEventListener` for a listener that was
 *     never added (the clean-render case's early return means no
 *     cleanup closure capturing a real listener was ever created for
 *     it to remove);
 *   - never duplicates a listener across re-renders: because the
 *     effect is keyed on `settingsDirty` alone, a re-render with the
 *     *same* dirty value (e.g. an unrelated parent re-render, or a
 *     second field independently going dirty while the aggregate was
 *     already `true`) does not re-run the effect at all -- React's own
 *     dependency-array semantics, not anything this hook has to
 *     implement -- so there is exactly one listener for as long as
 *     `settingsDirty` stays `true`, regardless of how many times or
 *     for how many reasons a render happens in between.
 *
 * # "Multiple dirty controls still produce one effective browser
 * guard" (task brief's test 7)
 *
 * This hook never sees the three individual per-control flags --
 * only the one `settingsDirty` boolean `computeSettingsDirty`
 * (Phase 2A-1) already folded them into. Whether one control or all
 * three are dirty, `settingsDirty` is still a single `true`, so this
 * hook still registers exactly one listener either way; there is no
 * per-control registration path here to accidentally multiply.
 *
 * # Native confirmation text (task brief's explicit boundary)
 *
 * `event.preventDefault()` is the modern, spec-correct way to trigger
 * the browser's own native "leave site?" prompt; `event.returnValue`
 * is set only for the older engines that still key off it rather than
 * the return value of the handler. Neither this hook nor any caller
 * of it supplies, or attempts to supply, the prompt's wording --
 * every modern browser has ignored a custom string here for years and
 * always shows its own fixed text, which is exactly why no attempt is
 * made to control it. `event.returnValue` is set to an empty string,
 * never anything derived from a field's value, so there is no path by
 * which a Theme value, an export directory path, or (in particular)
 * the VirustotalControl edit buffer could ever reach this event.
 *
 * # Why this cannot be, and is not, asserted end-to-end in this
 * project's test environment
 *
 * jsdom (this project's `vitest` environment) implements the
 * `beforeunload` event as a dispatchable DOM event but -- like every
 * headless DOM implementation -- has no browser chrome to show a
 * native confirmation dialog, and does not implement the
 * unload-cancellation behavior a real browser performs when a
 * `beforeunload` listener calls `preventDefault()`/sets
 * `returnValue`. This is a documented, permanent limitation of
 * jsdom/Vitest, not a gap in this hook or its tests: what *is*
 * mechanically verifiable in jsdom, and what this checkpoint's test
 * file actually asserts, is the listener *lifecycle* (register only
 * while dirty, never duplicate, remove on clean/unmount, correct
 * behavior on remount) and that a manually dispatched `beforeunload`
 * event reaches this hook's handler with `preventDefault()` called
 * and `returnValue` set exactly when `settingsDirty` is `true`. Actual
 * native-dialog suppression/appearance can only be verified by manual
 * testing in a real browser, per the task brief's own instruction to
 * document this rather than attempt to simulate it.
 */
import { useEffect } from "react";

/**
 * Registers a `beforeunload` listener for exactly as long as
 * `settingsDirty` is `true`. Exported separately from the hook so the
 * test file can dispatch a synthetic `beforeunload` event and assert
 * on its `defaultPrevented`/`returnValue` without needing to reach
 * into the hook's closure.
 */
function handleBeforeUnload(event: BeforeUnloadEvent): void {
  event.preventDefault();
  // Legacy-engine compatibility only -- see this file's doc comment.
  // Never derived from any Settings field's value.
  event.returnValue = "";
}

export function useSettingsBeforeUnloadGuard(settingsDirty: boolean): void {
  useEffect(() => {
    if (!settingsDirty) {
      return;
    }

    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
    };
  }, [settingsDirty]);
}
