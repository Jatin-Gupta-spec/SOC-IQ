import type { ReactElement, ReactNode } from "react";
import "./PageLayout.css";

export interface PageLayoutProps {
  /** Accessible name for this page's `<main>` landmark, e.g. "Dashboard page". */
  readonly label: string;
  readonly children: ReactNode;
}

/**
 * Shared page-level layout (Phase 4G-2 Part 3, §6/§18).
 *
 * Supplies the single `<main>` landmark for the routed page — the
 * previous `RoutePlaceholder` (Part 2) owned this; each real page now
 * owns it instead, via this shared wrapper, so all eight pages get
 * identical landmark/scroll-container behavior without duplicating
 * it eight times. `ContentRegion` (the shell) already owns outer
 * sizing/scroll containment for whatever mounts inside it, so this
 * wrapper only adds the page-local content constraints (max width,
 * internal padding, internal scrolling) — see `globals.css`'s note
 * that the page shell itself does not scroll, individual screens do.
 *
 * # Programmatic focusability (MAX17-F-01)
 *
 * `tabIndex={-1}` lets `ContentRegion`'s route-change focus effect
 * move keyboard focus onto this landmark after a navigation, without
 * adding it to the page's normal sequential (Tab) order — `-1` is
 * focusable only via `.focus()`, never via Tab, which is exactly the
 * "landmark that can receive focus but isn't itself a tab stop"
 * behavior this finding calls for. No other prop, label, or landmark
 * semantics change.
 */
export function PageLayout({ label, children }: PageLayoutProps): ReactElement {
  return (
    <main className="page-layout" aria-label={label} tabIndex={-1}>
      {children}
    </main>
  );
}
