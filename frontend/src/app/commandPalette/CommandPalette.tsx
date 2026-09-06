/**
 * Command palette UI skeleton — Phase 4G-5 Part 1, task brief §8/§11/
 * §12.
 *
 * Presentational + its own local query/selection state — this
 * component owns no navigation logic and no keyboard-invocation
 * logic of its own (that's `useCommandPaletteShortcut.ts`); it only
 * turns `commands`/`open`/`onClose`/`onNavigate` props into a dialog,
 * a search input, and a keyboard-navigable result list. It renders
 * `null` when `open` is `false`, the same "adds nothing to the page
 * when inactive" convention `RestartExhaustedNotification.tsx`
 * already established.
 *
 * # Accessibility (task brief §12)
 *
 * `role="dialog"` + `aria-modal="true"` + `aria-label` name the
 * surface itself. The search input carries its own `aria-label`
 * (there is no visible `<label>` in this compact a UI, matching
 * `SettingsPage`'s toggle buttons' own icon-only-control precedent of
 * an `aria-label` standing in for one). Results are a
 * `role="listbox"`/`role="option"` pair with `aria-selected`
 * reflecting keyboard/pointer selection — the closed
 * dialog/listbox/option pattern task brief §12 asks for, nothing
 * beyond it ("use ARIA only where necessary"). Escape and the
 * backdrop both call `onClose`; the backdrop is a real `<button>`
 * (not a bare `<div onClick>`) so it is itself keyboard-focusable and
 * needs no separate keydown handler of its own for that path.
 *
 * # Motion (task brief §13)
 *
 * Reuses `.transition-fade` exactly like `RestartExhaustedNotification`
 * does — no second motion/duration system, and reduced-motion is
 * inherited for free from that utility's existing global rule.
 */

import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactElement,
} from "react";
import { searchCommands } from "../../shared/commands/searchCommands";
import type { Command } from "../../shared/commands/types";
import "./CommandPalette.css";

export interface CommandPaletteProps {
  readonly open: boolean;
  readonly commands: readonly Command[];
  readonly onClose: () => void;
  readonly onNavigate: (path: string) => void;
}

export function CommandPalette({
  open,
  commands,
  onClose,
  onNavigate,
}: CommandPaletteProps): ReactElement | null {
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  // MAX15-F-01: the element that had focus immediately before the
  // palette opened, captured on the way in so it can be restored on
  // the way out. A plain ref (not state) — writing it must never
  // trigger a render, and its value only ever matters inside the two
  // effects below.
  const previouslyFocusedRef = useRef<HTMLElement | null>(null);

  const results = useMemo(
    () => searchCommands(commands, query),
    [commands, query],
  );

  // Reset to a clean, fully-focused state every time the palette
  // opens — task brief §11's "sane focus behavior": reopening should
  // never resurrect a stale query or an out-of-range selection from
  // the previous time it was open.
  //
  // The capture below must happen first, before anything in this
  // effect moves focus into the palette itself — otherwise
  // `document.activeElement` would already be the palette's own
  // input by the time it's read, and MAX15-F-01 would "restore"
  // focus right back into the palette it's supposed to be leaving.
  useEffect(() => {
    if (!open) {
      return;
    }
    previouslyFocusedRef.current = document.activeElement as HTMLElement | null;
    setQuery("");
    setSelectedIndex(0);
    inputRef.current?.focus();
  }, [open]);

  // MAX15-F-01: restore focus to whatever had it before the palette
  // opened, for every close path (Escape, backdrop dismiss, command
  // selection/navigation) — they all funnel through the same `open`
  // prop going false, so one effect covers all three. Guarded by
  // `document.contains` because navigation can unmount the very
  // element that used to hold focus (e.g. a control on the page the
  // palette navigated away from); in that case there is nothing safe
  // to focus, so fall back to leaving focus wherever it already
  // landed (typically the document body) rather than focusing a
  // detached node.
  useEffect(() => {
    if (open) {
      return;
    }
    const target = previouslyFocusedRef.current;
    previouslyFocusedRef.current = null;
    if (target && document.contains(target)) {
      target.focus();
    }
  }, [open]);

  // A query change can shrink `results` below the previously
  // selected index; clamp rather than let keyboard/Enter reference a
  // nonexistent row.
  useEffect(() => {
    if (selectedIndex >= results.length) {
      setSelectedIndex(results.length === 0 ? 0 : results.length - 1);
    }
  }, [results, selectedIndex]);

  if (!open) {
    return null;
  }

  const handleQueryChange = (event: ChangeEvent<HTMLInputElement>): void => {
    setQuery(event.target.value);
  };

  const runSelected = (): void => {
    const selected = results[selectedIndex];
    if (selected) {
      onNavigate(selected.path);
    }
  };

  const handleKeyDown = (event: ReactKeyboardEvent<HTMLDivElement>): void => {
    switch (event.key) {
      case "Escape":
        event.preventDefault();
        onClose();
        return;
      case "ArrowDown":
        event.preventDefault();
        setSelectedIndex((index) =>
          results.length === 0 ? 0 : (index + 1) % results.length,
        );
        return;
      case "ArrowUp":
        event.preventDefault();
        setSelectedIndex((index) =>
          results.length === 0
            ? 0
            : (index - 1 + results.length) % results.length,
        );
        return;
      case "Enter":
        event.preventDefault();
        runSelected();
        return;
      default:
        return;
    }
  };

  return (
    <div
      className="command-palette-backdrop transition-fade"
      onKeyDown={handleKeyDown}
    >
      <button
        type="button"
        className="command-palette-backdrop__dismiss"
        aria-label="Close command palette"
        onClick={onClose}
      />
      <div
        className="command-palette"
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
      >
        <input
          ref={inputRef}
          type="text"
          className="command-palette__input"
          placeholder="Type a command or search…"
          aria-label="Search commands"
          role="combobox"
          aria-expanded="true"
          aria-controls="command-palette-results"
          aria-autocomplete="list"
          value={query}
          onChange={handleQueryChange}
        />
        <ul
          id="command-palette-results"
          className="command-palette__results"
          role="listbox"
          aria-label="Command results"
        >
          {results.length === 0 ? (
            <li className="command-palette__empty" role="presentation">
              No matching commands
            </li>
          ) : (
            results.map((command, index) => (
              <li
                key={command.id}
                id={`command-palette-option-${command.id}`}
                className="command-palette__option"
                role="option"
                aria-selected={index === selectedIndex}
                data-selected={index === selectedIndex || undefined}
                onMouseEnter={() => setSelectedIndex(index)}
                onClick={() => {
                  setSelectedIndex(index);
                  onNavigate(command.path);
                }}
              >
                <span className="command-palette__option-label">
                  {command.label}
                </span>
                {command.description ? (
                  <span className="command-palette__option-description">
                    {command.description}
                  </span>
                ) : null}
              </li>
            ))
          )}
        </ul>
        <div className="command-palette__hint">
          <span>↑↓ to navigate</span>
          <span>Enter to select</span>
          <span>Esc to close</span>
        </div>
      </div>
    </div>
  );
}
