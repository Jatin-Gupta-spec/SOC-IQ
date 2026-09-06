/**
 * Command registry — single source of truth for palette commands
 * (Phase 4G-5 Part 1, task brief §5/§6/§7).
 *
 * `COMMANDS` is derived from `NAVIGATION_ITEMS`
 * (`app/navigation/navigationModel.ts`), not a second hand-maintained
 * list — task brief §7 requires the registry take its navigation
 * information "from the existing navigation model where practical",
 * and all of it is practical here: every skeleton command *is* a
 * navigation command. This mirrors `app/router.tsx`'s own precedent
 * of mapping `NAVIGATION_ITEMS` into routes rather than restating the
 * eight destinations a third time — there remains exactly one
 * navigation source of truth (`NAVIGATION_ITEMS`), which the sidebar,
 * the router, and now the palette each project into their own shape.
 *
 * A plain module-scope `readonly` array, not a class/store like
 * `RestartExhaustedNotificationStore` — this registry has no runtime
 * state of its own (no subscription, no mutation, no lifecycle to
 * initialize/dispose). `NAVIGATION_ITEMS` is itself already a static
 * `as const` list, so `COMMANDS` is exactly as deterministic — same
 * array, same order, every call — without inventing state-management
 * machinery a static derivation doesn't need.
 */

import { NAVIGATION_ITEMS } from "../../app/navigation/navigationModel";
import type { Command } from "./types";

/**
 * One navigation command per sidebar destination, in
 * `NAVIGATION_ITEMS`'s own order (task brief §14 item 6's
 * "deterministic ordering" starts here, before any search filtering
 * is even applied).
 *
 * `id` is namespaced `navigate:<navigation item id>` rather than
 * reusing the bare navigation id directly — commands and navigation
 * items are different vocabularies (task brief §4: "commands must
 * have stable unique IDs" is this registry's own contract, not
 * borrowed wholesale from a neighboring one), and the prefix keeps
 * this registry's ID space collision-free from a future non-
 * navigation command that might otherwise coincidentally share a
 * navigation item's id.
 */
export const COMMANDS: readonly Command[] = NAVIGATION_ITEMS.map(
  (item): Command => ({
    id: `navigate:${item.id}`,
    label: item.label,
    description: `Go to ${item.label}`,
    category: "navigation",
    keywords: [item.id, item.label.toLowerCase()],
    path: item.path,
  }),
);
