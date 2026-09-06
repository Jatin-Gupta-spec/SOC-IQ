import { useEffect, useState, type ReactElement } from "react";
import { Button } from "../components/Button";
import { useSettingsFieldSave } from "./useSettingsFieldSave";
import { isDirectoryBrowseSupported, pickExportDirectory } from "./exportDirectoryBrowse";

export interface ExportDirectoryControlProps {
  /** The value currently persisted on the backend, as returned by
   * `get_settings`. */
  readonly persistedExportDirectory: string;
  /** Notified with this control's own `dirty` flag on mount and every
   * time it changes -- MAX-18 Phase 2A-2, so `SettingsPage` can fold
   * it into the page-level `settingsDirty` aggregate. Optional so
   * every existing standalone render of this control (its own unit/
   * live tests) is unaffected. */
  readonly onDirtyChange?: (dirty: boolean) => void;
}

/**
 * Real Export Directory control -- SOC-IQ Part 2B-1, native browse
 * added MAX-11 Phase 2A.
 *
 * An editable text field, loading/saving through `save_settings` via
 * `useSettingsFieldSave`. Where supported (`isDirectoryBrowseSupported`
 * -- a real Tauri desktop runtime), a native "Browse…" button sits
 * alongside it, using `exportDirectoryBrowse.ts`'s OS-native folder
 * picker to fill the field -- mirroring the Analyze page's existing
 * "Browse for Analysis" pattern. Browsing only fills the field; it
 * does not save on the analyst's behalf, so the existing Save/dirty/
 * error/retry flow below is completely unchanged by this addition.
 * Outside a Tauri runtime (plain browser tab, tests) the field falls
 * back to hand-typed entry exactly as before.
 *
 * MAX19A-F-03: this value is saved but not yet applied anywhere --
 * `pages/reports/reportExportPath.ts::pickReportSavePath()` (the
 * native export-save dialog) only ever uses its own `defaultFileName`
 * argument and never reads the persisted `export_directory`. That gap
 * used to live only in source, undisclosed in the UI, unlike
 * `ThemeControl`'s equivalent limitation. The always-visible note
 * below uses that same `settings-page__field-note` / `role="note"`
 * convention so an analyst who sets this value learns honestly, every
 * time this control renders, that it doesn't yet change where the
 * export dialog defaults to -- wiring the export flow itself to read
 * this value is a separate, larger change outside this checkpoint.
 */
export function ExportDirectoryControl({
  persistedExportDirectory,
  onDirtyChange,
}: ExportDirectoryControlProps): ReactElement {
  const { value, setValue, dirty, saveStatus, save } = useSettingsFieldSave(
    "export_directory",
    persistedExportDirectory,
  );
  const [browseError, setBrowseError] = useState<string | null>(null);

  useEffect(() => {
    onDirtyChange?.(dirty);
  }, [dirty, onDirtyChange]);

  /**
   * Cancelling the dialog is a normal, silent outcome (matches native
   * OS picker convention, same as `AnalyzePage`'s `handleNativeBrowse`).
   * A genuine dialog failure surfaces through its own message slot
   * rather than being folded into `saveStatus`, since browsing and
   * saving are independent actions with independent outcomes.
   */
  async function handleBrowse(): Promise<void> {
    setBrowseError(null);
    const result = await pickExportDirectory();
    if (result.ok) {
      setValue(result.path);
      return;
    }
    if (result.reason === "cancelled" || result.reason === "unsupported") {
      return;
    }
    setBrowseError("Couldn't open the folder picker. You can still type the path directly.");
  }

  return (
    <div className="settings-page__field-group">
      <div className="settings-page__field-row">
        <div className="settings-page__field settings-page__field--grow">
          <label htmlFor="settings-export-directory" className="settings-page__field-label">
            Export Directory
          </label>
          <input
            id="settings-export-directory"
            type="text"
            className="settings-page__text-input"
            value={value}
            onChange={(event) => setValue(event.target.value)}
            spellCheck={false}
          />
        </div>
        {isDirectoryBrowseSupported() ? (
          <Button
            variant="secondary"
            className="settings-page__browse-button"
            onClick={() => {
              void handleBrowse();
            }}
            disabled={saveStatus.status === "saving"}
          >
            Browse…
          </Button>
        ) : null}
        <Button
          className="settings-page__save-button"
          onClick={save}
          disabled={!dirty || saveStatus.status === "saving"}
        >
          {saveStatus.status === "saving" ? "Saving…" : "Save"}
        </Button>
      </div>

      <p className="settings-page__field-note" role="note">
        This directory is saved but not yet used -- report exports currently open
        the native save dialog with only a suggested file name, regardless of what
        is set here.
      </p>

      {browseError !== null ? (
        <p className="settings-page__field-status settings-page__field-status--error" role="alert">
          {browseError}
        </p>
      ) : null}

      {saveStatus.status === "success" ? (
        <p
          className="settings-page__field-status settings-page__field-status--success"
          role="status"
          aria-live="polite"
        >
          Export directory saved.
        </p>
      ) : null}

      {saveStatus.status === "error" ? (
        <div className="settings-page__field-status-row">
          <p className="settings-page__field-status settings-page__field-status--error" role="alert">
            {saveStatus.message}
          </p>
          <Button className="settings-page__retry-button" onClick={save}>
            Retry
          </Button>
        </div>
      ) : null}
    </div>
  );
}
