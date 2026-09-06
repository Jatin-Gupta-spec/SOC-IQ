import { useEffect, type ReactElement } from "react";
import { Button } from "../components/Button";
import { useSettingsFieldSave } from "./useSettingsFieldSave";

/**
 * The only two theme values the established legacy Qt implementation
 * supports (`app/gui/pages/settings_page.py`'s `_theme_combo.addItems`,
 * `app/settings/models.py`'s own default). No light theme, no new
 * theme architecture -- this control can only ever request one of
 * these two persisted values.
 */
const THEME_OPTIONS = ["Dark Mode (SOC-IQ Standard)", "High Contrast Dark"] as const;

export interface ThemeControlProps {
  /** The value currently persisted on the backend, as returned by
   * `get_settings` -- not necessarily one of `THEME_OPTIONS`. */
  readonly persistedTheme: string;
  /** Notified with this control's own `dirty` flag on mount and every
   * time it changes -- MAX-18 Phase 2A-2, so `SettingsPage` can fold
   * it into the page-level `settingsDirty` aggregate. Optional so
   * every existing standalone render of this control (its own unit/
   * live tests) is unaffected. */
  readonly onDirtyChange?: (dirty: boolean) => void;
}

/**
 * Real Theme control -- SOC-IQ Part 2B-1, live-apply disclosure added
 * MAX-12 Phase 2A (MAX12-F-01).
 *
 * Loads/saves through `save_settings` via `useSettingsFieldSave`.
 * Changing this setting does not dynamically re-skin the current
 * frontend -- no such architecture exists yet -- so this control only
 * ever claims to persist the chosen value, never to apply it live.
 *
 * MAX12-F-01: that limitation used to live only in this comment, never
 * in the rendered UI -- an analyst who picked "High Contrast Dark" and
 * saw "Theme saved." had no way to know the interface never actually
 * changed. The always-visible note below (`settings-page__field-note`,
 * `role="note"`, the exact convention `VirustotalControl`'s own
 * restart-required disclosure already established in this same
 * Settings page) says so honestly, every time this control renders --
 * not only after a save, since the same gap exists for whatever value
 * is already persisted on load, before the analyst touches anything.
 *
 * If the persisted value is not one of the two supported options
 * (e.g. a stale/legacy value from an older build), that is surfaced
 * honestly via a second, separate note rather than silently coerced to
 * a default and saved out from under the analyst -- nothing is written
 * until the analyst explicitly chooses one of the two supported
 * options below.
 */
export function ThemeControl({ persistedTheme, onDirtyChange }: ThemeControlProps): ReactElement {
  const isSupportedPersistedValue = (THEME_OPTIONS as readonly string[]).includes(persistedTheme);
  const { value, setValue, dirty, saveStatus, save } = useSettingsFieldSave(
    "theme",
    isSupportedPersistedValue ? persistedTheme : "",
  );

  useEffect(() => {
    onDirtyChange?.(dirty);
  }, [dirty, onDirtyChange]);

  return (
    <div className="settings-page__field-group">
      <div className="settings-page__field-row">
        <div className="settings-page__field">
          <label htmlFor="settings-theme-select" className="settings-page__field-label">
            Theme
          </label>
          <select
            id="settings-theme-select"
            className="settings-page__select"
            value={value}
            onChange={(event) => setValue(event.target.value)}
          >
            {value === "" ? (
              <option value="" disabled>
                Choose a theme…
              </option>
            ) : null}
            {THEME_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </div>
        <Button
          className="settings-page__save-button"
          onClick={save}
          disabled={!dirty || saveStatus.status === "saving"}
        >
          {saveStatus.status === "saving" ? "Saving…" : "Save"}
        </Button>
      </div>

      <p className="settings-page__field-note" role="note">
        This selection is saved but not yet applied to the interface -- SOC-IQ
        currently renders its one standard dark theme regardless of which option is
        chosen here.
      </p>

      {!isSupportedPersistedValue ? (
        <p className="settings-page__field-note" role="note">
          The persisted theme value “{persistedTheme || "(empty)"}” is not one of the
          supported options above. Nothing has been changed automatically -- choose a
          theme and save to update it.
        </p>
      ) : null}

      {saveStatus.status === "success" ? (
        <p
          className="settings-page__field-status settings-page__field-status--success"
          role="status"
          aria-live="polite"
        >
          Theme saved.
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
