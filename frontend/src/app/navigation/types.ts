import type { ComponentType, SVGProps } from "react";

export type NavigationGroupId = "primary" | "secondary";

/**
 * A single sidebar destination.
 *
 * `path` is the one canonical identifier for the destination — the
 * same string is used as the route path (react-router) and as the
 * React `key`/lookup id is `id`, kept separate from `path` so a
 * future route-path rename doesn't also require renaming test
 * fixtures or other code that references items by id.
 */
export interface NavigationItem {
  readonly id: string;
  readonly label: string;
  readonly path: string;
  readonly icon: ComponentType<SVGProps<SVGSVGElement>>;
  readonly group: NavigationGroupId;
  readonly ariaLabel?: string;
}
