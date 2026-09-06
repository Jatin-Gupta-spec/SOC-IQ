/**
 * Deterministic command search — Phase 4G-5 Part 1, task brief §10.
 *
 * Plain substring matching over `label`/`description`/`keywords`,
 * case-insensitive. No fuzzy-matching dependency is added (none
 * already exists in this project's `package.json`, so §10's "no
 * fuzzy-search dependency unless already present" rules it out) and
 * no relevance scoring — task brief §10 explicitly says "do not
 * over-engineer ranking". Stability comes for free from
 * `Array.prototype.filter`, which never reorders the elements it
 * keeps, so results are always returned in `commands`' own input
 * order (for real callers, that's `COMMANDS`'s
 * `NAVIGATION_ITEMS`-derived order) — no separate sort step is
 * needed to satisfy "stable result ordering".
 */

import type { Command } from "./types";

/**
 * Returns the commands in `commands` whose label, description, or
 * any keyword contains `query` (case-insensitive, whitespace-
 * trimmed). An empty/whitespace-only query returns every command
 * unfiltered — the palette's initial, nothing-typed-yet state should
 * show the full command list, not an empty result.
 */
export function searchCommands(
  commands: readonly Command[],
  query: string,
): readonly Command[] {
  const normalized = query.trim().toLowerCase();
  if (normalized === "") {
    return commands;
  }

  return commands.filter((command) => {
    if (command.label.toLowerCase().includes(normalized)) {
      return true;
    }
    if (command.description?.toLowerCase().includes(normalized)) {
      return true;
    }
    return command.keywords.some((keyword) =>
      keyword.toLowerCase().includes(normalized),
    );
  });
}
