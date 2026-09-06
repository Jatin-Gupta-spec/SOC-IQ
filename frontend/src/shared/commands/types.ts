/**
 * Command palette — typed command model (Phase 4G-5 Part 1).
 *
 * Deliberately the smallest shape that fits the skeleton's one
 * supported command kind: frontend navigation (task brief §4/§6).
 * `path` — not a generic `action`/`run` callback — is the command's
 * effect, for the same reason `NAVIGATION_ITEMS`
 * (`app/navigation/navigationModel.ts`) is plain data rather than a
 * list of closures: `commandRegistry.ts` builds this array at module
 * scope, outside any component, so it can be tested directly with no
 * React rendering machinery (task brief §5's "independent from UI
 * rendering"); a closure calling `useNavigate()`'s `navigate()` can't
 * be constructed there. The palette component (`CommandPalette.tsx`)
 * is the one place that turns a selected command's `path` into an
 * actual navigation, via the router context it already has.
 *
 * `category` is a closed union of one member today. It stays a union
 * (not a bare `string`) so a later phase adding a second command kind
 * (task brief's explicitly out-of-scope destructive/execution
 * commands) is a type-checked addition here, not a silent free-text
 * drift.
 */

export type CommandCategory = "navigation";

export interface Command {
  /** Stable, unique across the whole registry (task brief §4). */
  readonly id: string;
  readonly label: string;
  readonly description?: string;
  readonly category: CommandCategory;
  /**
   * Extra search terms beyond `label`/`description` — e.g. an
   * abbreviation or the underlying navigation id. Always present
   * (possibly empty) rather than optional, so `searchCommands.ts`
   * never needs an `?? []` at every call site.
   */
  readonly keywords: readonly string[];
  /** The route this command navigates to. Every command in this
   * skeleton is a navigation command, so this is required, not
   * optional — see module doc. */
  readonly path: string;
}
