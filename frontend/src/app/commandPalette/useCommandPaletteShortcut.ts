/**
 * Ctrl+K (Cmd+K on macOS) keyboard invocation foundation for the
 * command palette — Phase 4G-5 Part 1, task brief §9.
 *
 * A frontend-only `window` keydown listener — no native Tauri global
 * shortcut (task brief §3/§19 explicitly excludes that from this
 * skeleton). One `useEffect` with a single add/remove pair, mirroring
 * every other window/document-level listener already in this project
 * (see `shared/events/eventSourceManager.ts`'s own precedent): the
 * cleanup function always removes exactly the listener this same
 * effect run added, so repeated mount/unmount — including React
 * Strict Mode's deliberate double-invoke in development — never
 * accumulates a second listener (task brief §14 items 14-15).
 *
 * `onToggle` is taken as a parameter rather than owning open/closed
 * state itself — that state belongs to whichever component actually
 * renders the palette (`CommandPaletteContainer.tsx`); this hook's
 * only job is translating one specific key combination into one call
 * to whatever the caller passed in the same shape
 * `useRestartExhaustedNotification`'s `store` parameter and
 * `startSidecarLifecycle`'s `reconciler` parameter already use for
 * this project's "own no state of your own" convention.
 */

import { useEffect } from "react";

const EDITABLE_TAGS = new Set(["INPUT", "TEXTAREA", "SELECT"]);

/**
 * True when `target` is a form control or `contenteditable` element
 * the person is actively typing into — the shortcut must not fire in
 * that case (task brief §9's "does not trigger while typing in
 * unrelated text fields"), since Ctrl+K/Cmd+K has native meaning in
 * several browsers' own address-bar/text-field editing (e.g. "delete
 * to end of line") that this global handler must not shadow.
 */
function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) {
    return false;
  }
  return EDITABLE_TAGS.has(target.tagName) || target.isContentEditable;
}

/**
 * True for the conventional palette-toggle chord: Ctrl+K on
 * Windows/Linux, Cmd+K on macOS (task brief §9's "platform-
 * appropriate equivalent") — either modifier alone, not both at once
 * (a real Ctrl+Cmd+K chord is a different, unrelated combination),
 * and never alongside Alt/Shift, which would make it a different
 * shortcut entirely in most browsers/OSes.
 */
function isToggleChord(event: KeyboardEvent): boolean {
  if (event.key.toLowerCase() !== "k") {
    return false;
  }
  const hasPrimaryModifier = event.ctrlKey !== event.metaKey;
  return hasPrimaryModifier && !event.altKey && !event.shiftKey;
}

/**
 * Registers the Ctrl+K/Cmd+K toggle for as long as the calling
 * component is mounted. `onToggle` is called with no arguments each
 * time the chord fires outside an editable field; the caller decides
 * what "toggle" means (open if closed, close if open).
 */
export function useCommandPaletteShortcut(onToggle: () => void): void {
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent): void {
      if (!isToggleChord(event)) {
        return;
      }
      if (isEditableTarget(event.target)) {
        return;
      }
      event.preventDefault();
      onToggle();
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [onToggle]);
}
