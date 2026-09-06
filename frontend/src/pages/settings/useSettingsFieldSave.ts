/**
 * Single-field edit/save lifecycle for the two real Settings controls
 * (Theme, Export Directory) -- SOC-IQ Part 2B-1.
 *
 * `SaveSettingsRequest` (`app/application/dto.py`) accepts exactly one
 * of `theme` / `export_directory` per call (`virustotal_api_key` is
 * rejected outright as of MAX19A-F-01 -- credential writes go through
 * `keystore_set_secret` instead), so each control owns its own
 * independent edit buffer, dirty flag, and save request -- there is no
 * combined "save all settings" action to build here, matching the
 * backend's own one-field-per-call contract.
 *
 * Mirrors `useReportExport.ts`'s state-machine shape (idle/in-flight/
 * success/error) and its cancellation discipline (a ref-backed flag
 * guarding against a resolved/rejected save reaching an unmounted
 * control), adapted to a persisted-value/dirty-tracking editor rather
 * than a fire-and-forget action.
 *
 * Stale-response guard (SOC-IQ MAX-21B-4A, verified forensic finding):
 * `save()` assigns each issued request a monotonic generation number,
 * the same pattern `useSettings.ts`'s load path already uses for
 * `get_settings`. If save A is issued and then save B is issued
 * before A resolves, B's generation becomes the current one; when A's
 * response arrives -- success or failure -- it is discarded rather
 * than applied, because it is no longer the most recently *issued*
 * request. This is deliberately keyed to issue order, not resolution
 * order: a slow-to-resolve older request must never be allowed to
 * overwrite a newer request's outcome just because it happens to
 * arrive later. The UI layer (`ThemeControl.tsx` /
 * `ExportDirectoryControl.tsx`) already disables the Save button
 * while `saveStatus.status === "saving"`, which prevents this from
 * being reachable through a single real Save button today -- this
 * guard exists as defense in depth so the hook itself stays correct
 * even under concurrent/programmatic saves, independent of whatever
 * UI happens to sit on top of it.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { runCommand } from "../../shared/api/client";

export type SettingsFieldName = "theme" | "export_directory";

export type SettingsFieldSaveStatus =
  | { readonly status: "idle" }
  | { readonly status: "saving" }
  | { readonly status: "success" }
  | { readonly status: "error"; readonly message: string };

export interface UseSettingsFieldSaveResult {
  /** The control's current (possibly unsaved) edit-buffer value. */
  readonly value: string;
  readonly setValue: (value: string) => void;
  /** `true` when `value` differs from the last known-persisted value. */
  readonly dirty: boolean;
  readonly saveStatus: SettingsFieldSaveStatus;
  /** No-ops while already `"saving"`. Safe to call again after
   * `"error"` to retry, or after `"success"` to re-save an edited
   * value. */
  readonly save: () => void;
}

function describeSaveError(error: unknown): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return "An unknown error occurred while saving.";
}

export function useSettingsFieldSave(
  field: SettingsFieldName,
  persistedValue: string,
): UseSettingsFieldSaveResult {
  const [value, setValueState] = useState(persistedValue);
  const [savedBaseline, setSavedBaseline] = useState(persistedValue);
  const [saveStatus, setSaveStatus] = useState<SettingsFieldSaveStatus>({ status: "idle" });
  const cancelledRef = useRef(false);
  // Monotonic per-issued-request counter -- see the stale-response
  // guard note in the file-level doc comment above.
  const generationRef = useRef(0);

  useEffect(
    () => () => {
      cancelledRef.current = true;
    },
    [],
  );

  const setValue = useCallback((next: string) => {
    setValueState(next);
    // A fresh edit supersedes any prior save outcome for this field --
    // an old "saved" / error banner must not linger next to a value
    // that no longer matches what it described.
    setSaveStatus((current) => (current.status === "idle" ? current : { status: "idle" }));
  }, []);

  const save = useCallback(() => {
    setSaveStatus((current) => {
      if (current.status === "saving") {
        return current;
      }
      return { status: "saving" };
    });

    const valueAtRequestTime = value;
    // Assigned at issue time, not resolution time -- see the
    // file-level doc comment. Whichever save() call runs last "wins"
    // this ref, regardless of how the two responses end up ordering.
    const generation = ++generationRef.current;

    void runCommand(
      "save_settings",
      field === "theme"
        ? { theme: valueAtRequestTime }
        : { export_directory: valueAtRequestTime },
    ).then(
      () => {
        if (cancelledRef.current || generation !== generationRef.current) {
          return;
        }
        setSavedBaseline(valueAtRequestTime);
        setSaveStatus({ status: "success" });
      },
      (error: unknown) => {
        if (cancelledRef.current || generation !== generationRef.current) {
          return;
        }
        setSaveStatus({ status: "error", message: describeSaveError(error) });
      },
    );
  }, [field, value]);

  return {
    value,
    setValue,
    dirty: value !== savedBaseline,
    saveStatus,
    save,
  };
}
