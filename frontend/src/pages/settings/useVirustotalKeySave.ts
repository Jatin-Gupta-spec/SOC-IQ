/**
 * VirusTotal credential edit/save lifecycle -- SOC-IQ Part 8 (ADR-008
 * Part 1B-3, "approved credential write implementation").
 *
 * Deliberately NOT `useSettingsFieldSave`: that hook tracks a
 * `persistedValue` it received from `get_settings` and diffs edits
 * against it -- appropriate for Theme/Export Directory, whose current
 * value the frontend is allowed to hold. The VirusTotal API key must
 * never be read back into this process (`VirustotalControl`'s own doc
 * comment; Part 7's approved architecture), so this hook has no
 * persisted baseline to diff against at all: it only ever knows
 * whether the edit buffer is non-empty, not whether it differs from
 * whatever is currently stored.
 *
 * Success here means exactly "`keystore_set_secret` returned Ok" --
 * per Part 7's approved architecture (Option A, application restart),
 * it does NOT mean the running Python sidecar is using the new
 * credential yet. This hook does not attempt to represent "active";
 * `VirustotalControl` is responsible for wording the restart-required
 * message honestly.
 *
 * `dirty` (MAX-18 Phase 2A-1, MAX18-F-01) -- per the no-persisted-
 * baseline note above, this control's notion of "dirty" cannot mean
 * "differs from what's stored" the way `useSettingsFieldSave`'s does.
 * It means "there is unsaved input in the edit buffer": a non-empty
 * (after trimming) `value`. That is exactly the condition
 * `VirustotalControl` already disables its own Save button on, so
 * this is a rename/expose of existing logic, not a new comparison or
 * a new source of truth -- and it never touches the buffer's actual
 * contents, only its trimmed length.
 *
 * Stale-response guard (SOC-IQ MAX-21B-4A): `setValue()` resets any
 * non-idle `saveStatus` back to `"idle"` on every edit, including
 * `"saving"` -- so editing the buffer while a save is still in flight
 * re-enables `VirustotalControl`'s Save button and lets a second save
 * be issued before the first resolves. Demonstrated concretely during
 * the MAX-21B-4A implementation pass: if the older save then fails
 * after the newer one already succeeded, the stale failure overwrote
 * the newer save's success state. `save()` now assigns each issued
 * request a monotonic generation number (identical pattern to
 * `useSettingsFieldSave.ts` and `useSettings.ts`), and a resolve or
 * reject is only applied if it is still the most recently *issued*
 * request.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { KeystoreWriteError, setVirustotalApiKey } from "../../shared/api/client";

export type VirustotalKeySaveStatus =
  | { readonly status: "idle" }
  | { readonly status: "saving" }
  | { readonly status: "success" }
  | { readonly status: "error"; readonly message: string };

export interface UseVirustotalKeySaveResult {
  /** The in-progress, unsaved credential edit buffer. Never populated
   * from any backend read -- only ever set by the user typing. */
  readonly value: string;
  readonly setValue: (value: string) => void;
  /** `true` whenever the trimmed edit buffer is non-empty. See the
   * file-level doc comment: this hook has no persisted baseline to
   * diff against, so "dirty" here is "unsaved input present", not
   * "differs from storage". */
  readonly dirty: boolean;
  readonly saveStatus: VirustotalKeySaveStatus;
  /** No-ops on an empty (after trimming) `value`, or while already
   * `"saving"`. Safe to call again after `"error"` to retry. */
  readonly save: () => void;
}

function describeSaveError(error: unknown): string {
  if (error instanceof KeystoreWriteError && error.message) {
    return error.message;
  }
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return "An unknown error occurred while saving the VirusTotal API key.";
}

export function useVirustotalKeySave(): UseVirustotalKeySaveResult {
  const [value, setValueState] = useState("");
  const [saveStatus, setSaveStatus] = useState<VirustotalKeySaveStatus>({ status: "idle" });
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
    // A fresh edit supersedes any prior save outcome -- an old
    // success/error message must not linger next to a value that no
    // longer matches what it described.
    setSaveStatus((current) => (current.status === "idle" ? current : { status: "idle" }));
  }, []);

  const save = useCallback(() => {
    const trimmed = value.trim();
    if (trimmed.length === 0) {
      return;
    }

    setSaveStatus((current) => {
      if (current.status === "saving") {
        return current;
      }
      return { status: "saving" };
    });

    // Assigned at issue time, not resolution time -- see the
    // file-level doc comment. Whichever save() call runs last "wins"
    // this ref, regardless of how the two responses end up ordering.
    const generation = ++generationRef.current;

    void setVirustotalApiKey(trimmed).then(
      () => {
        if (cancelledRef.current || generation !== generationRef.current) {
          return;
        }
        // Clear the plaintext buffer immediately on success -- it is
        // never retained in persistent frontend state past this point
        // (Part 8 STEP 5).
        setValueState("");
        setSaveStatus({ status: "success" });
      },
      (error: unknown) => {
        if (cancelledRef.current || generation !== generationRef.current) {
          return;
        }
        // Preserve the previous configured state and allow retry --
        // the entered credential is not cleared here so the user does
        // not have to retype it, but it is never logged or persisted
        // anywhere by this hook.
        setSaveStatus({ status: "error", message: describeSaveError(error) });
      },
    );
  }, [value]);

  return { value, setValue, dirty: value.trim().length > 0, saveStatus, save };
}
