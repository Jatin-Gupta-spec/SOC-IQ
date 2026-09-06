/**
 * `useSettingsPageDirty` -- SOC-IQ MAX-18 Phase 2A-2 (MAX18-F-01,
 * Settings dirty-state aggregation).
 *
 * Phase 2A-1 (`settingsDirty.ts`) built `computeSettingsDirty`, a pure
 * combinator over three already-existing per-control dirty booleans,
 * but deliberately left it unwired: nothing lifted those three
 * controls' independent `dirty` flags into one place `SettingsPage`
 * could read. This hook is that place.
 *
 * It holds exactly the three flags `computeSettingsDirty` already
 * expects -- one per real Settings control (Theme, Export Directory,
 * VirusTotal API key) -- and re-derives `settingsDirty` from them on
 * every change via the same Phase 2A-1 combinator. No new dirty
 * *logic* is introduced here: each flag's value still comes entirely
 * from the control that owns it (`useSettingsFieldSave`'s `dirty` for
 * Theme/Export Directory, `useVirustotalKeySave`'s `dirty` for
 * VirusTotal); this hook only ever stores the three latest values it
 * is told and combines them.
 *
 * `SettingsPage` passes the three setter functions below straight
 * through to each control as an `onDirtyChange` callback -- `useState`
 * setters are referentially stable across renders, so no
 * `useCallback` wrapping is needed to keep a child's own
 * `onDirtyChange` effect from re-firing spuriously.
 *
 * Deliberately NOT a context/global store: this is local `useState`
 * scoped to one `SettingsPage` instance, matching the task brief's
 * "no global dirty-state infrastructure" boundary. A fresh mount of
 * `SettingsPage` (e.g. after navigating away and back) gets a fresh
 * hook instance with all three flags starting `false` -- there is no
 * way for a previous instance's dirty state to leak into a new one.
 */
import { useMemo, useState } from "react";
import { computeSettingsDirty } from "./settingsDirty";

export interface UseSettingsPageDirtyResult {
  /** `true` when any of the three tracked controls is currently dirty
   * -- `computeSettingsDirty` applied to this hook's own state. */
  readonly settingsDirty: boolean;
  /** Pass directly as `ThemeControl`'s `onDirtyChange`. */
  readonly handleThemeDirtyChange: (dirty: boolean) => void;
  /** Pass directly as `ExportDirectoryControl`'s `onDirtyChange`. */
  readonly handleExportDirectoryDirtyChange: (dirty: boolean) => void;
  /** Pass directly as `VirustotalControl`'s `onDirtyChange`. */
  readonly handleVirustotalKeyDirtyChange: (dirty: boolean) => void;
}

export function useSettingsPageDirty(): UseSettingsPageDirtyResult {
  const [themeDirty, setThemeDirty] = useState(false);
  const [exportDirectoryDirty, setExportDirectoryDirty] = useState(false);
  const [virustotalKeyDirty, setVirustotalKeyDirty] = useState(false);

  const settingsDirty = useMemo(
    () => computeSettingsDirty({ themeDirty, exportDirectoryDirty, virustotalKeyDirty }),
    [themeDirty, exportDirectoryDirty, virustotalKeyDirty],
  );

  return {
    settingsDirty,
    handleThemeDirtyChange: setThemeDirty,
    handleExportDirectoryDirtyChange: setExportDirectoryDirty,
    handleVirustotalKeyDirtyChange: setVirustotalKeyDirty,
  };
}
