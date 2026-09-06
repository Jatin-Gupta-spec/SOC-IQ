/**
 * `settingsDirty` aggregate -- SOC-IQ MAX-18 Phase 2A-1 (MAX18-F-01,
 * dirty-state foundation).
 *
 * The three Settings controls each already carry their own
 * independent dirty signal:
 *
 *   - Theme / Export Directory: `useSettingsFieldSave`'s `dirty`
 *     (differs from the last known-persisted value).
 *   - VirusTotal API key: `useVirustotalKeySave`'s `dirty` (non-empty
 *     edit buffer -- see that hook's own doc comment for why it can't
 *     mean "differs from storage").
 *
 * `computeSettingsDirty` is the single, pure "is anything on this
 * page unsaved" combinator those three signals feed into. It exists
 * now so the later navigation-interception work (MAX-18 Phase 2A-2)
 * has one well-tested place to ask that question, instead of each
 * future consumer re-deriving its own OR of the three flags.
 *
 * Deliberately NOT wired into `SettingsPage` yet: nothing in this
 * checkpoint (Phase 2A-1) consumes an aggregate dirty flag -- that
 * starts with 2A-2's navigation interception -- and wiring it in
 * earlier would mean carrying page-level state with no reader, per
 * this checkpoint's explicit scope boundary. See
 * `docs/audits/SOC-IQ-FRONTEND-MAX-18-2A-1.md`.
 *
 * Takes booleans only, never the underlying field values -- the
 * VirusTotal edit buffer in particular must never reach this (or any)
 * aggregation point, only whether it is non-empty.
 */

export interface SettingsDirtyFlags {
  readonly themeDirty: boolean;
  readonly exportDirectoryDirty: boolean;
  readonly virustotalKeyDirty: boolean;
}

/** `true` if any individual Settings control is currently dirty. */
export function computeSettingsDirty(flags: SettingsDirtyFlags): boolean {
  return flags.themeDirty || flags.exportDirectoryDirty || flags.virustotalKeyDirty;
}
