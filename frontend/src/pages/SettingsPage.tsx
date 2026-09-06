import type { ReactElement } from "react";
import { PageLayout } from "./components/PageLayout";
import { PageHeader } from "./components/PageHeader";
import { Button } from "./components/Button";
import { Card } from "./components/Card";
import { InfoNote } from "./components/InfoNote";
import { SkeletonBlock } from "./components/SkeletonBlock";
import { mockSettingsSections } from "../mock/settings";
import { useSettings } from "./settings/useSettings";
import { useSettingsPageDirty } from "./settings/useSettingsPageDirty";
import { useSettingsNavigationGuardSync } from "./settings/useSettingsNavigationGuardSync";
import { useSettingsBeforeUnloadGuard } from "./settings/useSettingsBeforeUnloadGuard";
import { ThemeControl } from "./settings/ThemeControl";
import { ExportDirectoryControl } from "./settings/ExportDirectoryControl";
import { VirustotalControl } from "./settings/VirustotalControl";
import { useReducedMotion } from "../shared/hooks/useReducedMotion";
import "./SettingsPage.css";

function describeSettingsError(error: unknown): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return "An unknown error occurred while loading settings.";
}

/**
 * Structural loading skeleton (MAX-2, Part 4) -- one block per card
 * this page actually renders once loaded: the three real
 * backend-backed cards (Appearance, Report Export, Integrations)
 * followed by one block per read-only mock section already present in
 * the success view below. The mock-section count is read from
 * `mockSettingsSections.length` rather than hardcoded, so the
 * skeleton can't silently drift from what actually renders -- and per
 * the task brief's §"Do not make Settings appear more functional than
 * it currently is", no control labels, toggle states, or values are
 * represented, only the existing card structure.
 */
function SettingsSkeleton({ reducedMotion }: { readonly reducedMotion: boolean }): ReactElement {
  return (
    <div className="settings-page__skeleton" aria-hidden="true">
      <SkeletonBlock className="settings-page__skeleton-card" reducedMotion={reducedMotion} />
      <SkeletonBlock className="settings-page__skeleton-card" reducedMotion={reducedMotion} />
      <SkeletonBlock className="settings-page__skeleton-card" reducedMotion={reducedMotion} />
      {mockSettingsSections.map((section) => (
        <SkeletonBlock
          key={section.id}
          className="settings-page__skeleton-card settings-page__skeleton-card--mock"
          reducedMotion={reducedMotion}
        />
      ))}
    </div>
  );
}

/**
 * Settings page -- SOC-IQ Part 2B-1 (PD-07 Settings Partial Build).
 *
 * Theme and Export Directory are now real, backend-backed controls
 * loaded via the existing `get_settings` command (`useSettings()`)
 * and persisted through `save_settings` (`ThemeControl`/
 * `ExportDirectoryControl`, via `useSettingsFieldSave`). The
 * VirusTotal API key has a fully live, enabled credential write path
 * via `keystore_set_secret` (Rust-owned OS keystore write, MAX-19
 * Part 1B-3) -- it is not disabled; see `VirustotalControl`'s own doc
 * comment for the restart-required handoff semantics.
 *
 * Every other section below (Application, Notifications, Security,
 * and Appearance's Density control) is unchanged, non-functional mock
 * display -- out of scope for this checkpoint, per the task brief's
 * "no dead mock cleanup" boundary.
 *
 * # Settings dirty-state aggregation (MAX-18 Phase 2A-2, MAX18-F-01)
 *
 * Each of the three real controls' own `dirty` flag (already the
 * single source of truth its own Save button disables against) is
 * lifted here via `onDirtyChange` into `useSettingsPageDirty`, which
 * folds them into one `settingsDirty` boolean through the Phase
 * 2A-1 `computeSettingsDirty` combinator. Nothing about how a value
 * is edited, saved, or persisted changes -- this only adds a
 * page-level read of state each control already held.
 *
 * `settingsDirty` is exposed as `data-settings-dirty` on a
 * `display: contents` wrapper around the success view -- a
 * non-visual marker (no layout, styling, or behavior change) that
 * makes the aggregate observable for tests. Phase 2A-2 itself wired
 * up aggregation only: no navigation guard, dialog, `beforeunload`,
 * or autosave was wired to it there.
 *
 * # Navigation guard wiring (MAX-18 Phase 2A-3, MAX18-F-01)
 *
 * `useSettingsNavigationGuardSync(settingsDirty)` is the one line
 * this checkpoint adds: it forwards the same `settingsDirty` value
 * this component already computed into `settingsNavigationGuard`, the
 * singleton store `NavigationGroup`'s sidebar links and
 * `CommandPaletteContainer`'s command execution consult before
 * leaving Settings, and clears it again on unmount so the guard can
 * never act on stale state from a previous visit. `SettingsPage`
 * itself renders no dialog and contains no interception logic --
 * both live in `SettingsNavigationGuardDialog`
 * (`app/shell/SettingsNavigationGuardDialog.tsx`), mounted once in
 * `AppShell` alongside `CommandPaletteContainer`. See that store's
 * own doc comment (`pages/settings/settingsNavigationGuardStore.ts`)
 * for the full design.
 *
 * # Browser `beforeunload` protection (MAX-18 Phase 2A-5, MAX18-F-01)
 *
 * `useSettingsBeforeUnloadGuard(settingsDirty)` is this checkpoint's
 * one added line: a second, independent consumer of the same
 * `settingsDirty` aggregate, registering a native `beforeunload`
 * listener for exactly as long as it is `true`. This is additive to,
 * and entirely separate from, the in-app navigation guard above --
 * closing the tab/window or reloading is never mediated by
 * `settingsNavigationGuard`, so it needs the browser's own hook
 * instead. See that hook's own doc comment
 * (`pages/settings/useSettingsBeforeUnloadGuard.ts`) for the full
 * design and for why native-dialog appearance/text cannot be
 * exercised in this project's jsdom-based test environment.
 */
export function SettingsPage(): ReactElement {
  const { state, settings, error, retry } = useSettings();
  const reducedMotion = useReducedMotion();
  const {
    settingsDirty,
    handleThemeDirtyChange,
    handleExportDirectoryDirtyChange,
    handleVirustotalKeyDirtyChange,
  } = useSettingsPageDirty();

  useSettingsNavigationGuardSync(settingsDirty);
  useSettingsBeforeUnloadGuard(settingsDirty);

  return (
    <PageLayout label="Settings page">
      <PageHeader
        title="Settings"
        description="Application configuration."
      />

      {state === "loading" ? (
        <section className="page-layout__section" aria-label="Settings loading">
          <p className="skeleton-status" role="status" aria-live="polite">
            Loading settings…
          </p>
          <SettingsSkeleton reducedMotion={reducedMotion} />
        </section>
      ) : null}

      {state === "error" ? (
        <section className="page-layout__section">
          <Card title="Settings Unavailable">
            <p className="settings-page__message" role="alert">
              {describeSettingsError(error)}
            </p>
            <div className="settings-page__actions">
              <Button onClick={retry}>Retry</Button>
            </div>
          </Card>
        </section>
      ) : null}

      {state === "success" && settings !== null ? (
        <div data-settings-dirty={settingsDirty} style={{ display: "contents" }}>
          <section className="page-layout__section">
            <Card title="Appearance">
              <ThemeControl
                persistedTheme={settings.theme}
                onDirtyChange={handleThemeDirtyChange}
              />
            </Card>
          </section>

          <section className="page-layout__section">
            <Card title="Report Export">
              <ExportDirectoryControl
                persistedExportDirectory={settings.export_directory}
                onDirtyChange={handleExportDirectoryDirtyChange}
              />
            </Card>
          </section>

          <section className="page-layout__section">
            <Card title="Integrations">
              <VirustotalControl
                configured={settings.virustotal_api_key_configured}
                onDirtyChange={handleVirustotalKeyDirtyChange}
              />
            </Card>
          </section>

          <section className="page-layout__section">
            <InfoNote>
              The sections below are read-only mock values — no changes made here are saved.
            </InfoNote>
          </section>

          {mockSettingsSections.map((section) => (
            <section key={section.id} className="page-layout__section">
              <Card title={section.title}>
                <p className="settings-page__section-description">{section.description}</p>
                <ul className="settings-page__control-list">
                  {section.controls.map((control) => (
                    <li key={control.id} className="settings-page__control-row">
                      <span className="settings-page__control-label">{control.label}</span>
                      {control.kind === "toggle" ? (
                        <button
                          type="button"
                          className="settings-page__toggle"
                          disabled
                          aria-pressed={control.value === "On"}
                          aria-label={`${control.label}: ${control.value}`}
                        >
                          {control.value}
                        </button>
                      ) : (
                        <span className="settings-page__control-value">{control.value}</span>
                      )}
                    </li>
                  ))}
                </ul>
              </Card>
            </section>
          ))}
        </div>
      ) : null}
    </PageLayout>
  );
}
