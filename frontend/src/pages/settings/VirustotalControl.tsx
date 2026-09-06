import { useEffect, type ReactElement } from "react";
import { Button } from "../components/Button";
import { StatusBadge } from "../components/StatusBadge";
import { useVirustotalKeySave } from "./useVirustotalKeySave";

export interface VirustotalControlProps {
  /** `get_settings`'s `virustotal_api_key_configured` -- a boolean
   * derived server-side from whether a non-empty key came back from
   * the secret store. The raw key itself never reaches this
   * component, or any frontend state. */
  readonly configured: boolean;
  /** Notified with this control's own `dirty` flag (see
   * `useVirustotalKeySave`'s doc comment for what "dirty" means for
   * this credential-only control) on mount and every time it changes
   * -- MAX-18 Phase 2A-2, so `SettingsPage` can fold it into the
   * page-level `settingsDirty` aggregate. Never receives the edit
   * buffer itself, only the boolean derived from its length -- see
   * `useVirustotalKeySave`. Optional so every existing standalone
   * render of this control (its own unit/live tests) is unaffected. */
  readonly onDirtyChange?: (dirty: boolean) => void;
}

/**
 * VirusTotal API key control -- SOC-IQ Part 8 (ADR-008 Part 1B-3,
 * "approved credential write implementation").
 *
 * Writes go through the existing, already-registered
 * `keystore_set_secret` Tauri command only (`useVirustotalKeySave` ->
 * `setVirustotalApiKey()`, `shared/api/client.ts`) -- the approved
 * security boundary per Part 7's Option A (application restart)
 * decision. This component never reads a credential back: `configured`
 * is the only signal it ever receives about what is currently stored,
 * and the entered replacement value is never displayed, retained past
 * a successful save, or round-tripped through any other frontend
 * state.
 *
 * Deliberately does NOT attempt to make the new credential active in
 * the current session -- the running Python sidecar keeps its old
 * environment until the next launch's `apply_secret_handoff()`
 * (`src-tauri/src/sidecar.rs`), so a successful save is reported
 * exactly as "saved, restart required," never as "active now."
 */
export function VirustotalControl({ configured, onDirtyChange }: VirustotalControlProps): ReactElement {
  const { value, setValue, dirty, saveStatus, save } = useVirustotalKeySave();

  useEffect(() => {
    onDirtyChange?.(dirty);
  }, [dirty, onDirtyChange]);

  const saving = saveStatus.status === "saving";

  return (
    <div className="settings-page__field-group">
      <div className="settings-page__field-row">
        <div className="settings-page__field settings-page__field--grow">
          <label htmlFor="settings-virustotal-api-key" className="settings-page__field-label">
            VirusTotal API Key
          </label>
          <StatusBadge label={configured ? "Configured" : "Not configured"} tone={configured ? "success" : "neutral"} />
          <input
            id="settings-virustotal-api-key"
            type="password"
            className="settings-page__text-input"
            placeholder={configured ? "Enter a replacement API key" : "Enter your VirusTotal API key"}
            value={value}
            onChange={(event) => setValue(event.target.value)}
            autoComplete="off"
            spellCheck={false}
          />
        </div>
        <Button
          className="settings-page__save-button"
          onClick={save}
          disabled={!dirty || saving}
        >
          {saving ? "Saving…" : "Save"}
        </Button>
      </div>

      {saveStatus.status === "success" ? (
        <p
          className="settings-page__field-status settings-page__field-status--success"
          role="status"
          aria-live="polite"
        >
          Credential saved. Restart SOC-IQ for the new credential to take effect.
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

      <p className="settings-page__field-note" role="note">
        The VirusTotal API key is stored and retrieved through the OS-backed keystore
        architecture (ADR-008). Saving a new key updates the OS keystore immediately, but the
        currently running instance of SOC-IQ keeps using its existing credential until you
        restart the application.
      </p>
    </div>
  );
}
