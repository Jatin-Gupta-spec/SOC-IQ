import type { ReactElement, ReactNode } from "react";
import "./PageHeader.css";

export interface PageHeaderProps {
  /** The page's own title. Rendered as the page's single top-level heading. */
  readonly title: string;
  /** One or two sentences of context for what the page will eventually do. */
  readonly description: string;
  /** Optional region for future per-page actions (e.g. a "New" button). Static-only in this checkpoint — see `docs/phase4/...Part 3`, §6. */
  readonly actions?: ReactNode;
}

/**
 * Shared page header (Phase 4G-2 Part 3, §6).
 *
 * Every mock page composes this instead of hand-rolling its own
 * title/description markup, so the eight pages share one consistent
 * heading structure. `title` renders as an `<h1>` — each page is its
 * own document section (reached via the sidebar, not nested under
 * another page), so there is exactly one `<h1>` per page and this is
 * it.
 */
export function PageHeader({
  title,
  description,
  actions,
}: PageHeaderProps): ReactElement {
  return (
    <header className="page-header">
      <div className="page-header__text">
        <h1 className="page-header__title">{title}</h1>
        <p className="page-header__description">{description}</p>
      </div>
      {actions ? <div className="page-header__actions">{actions}</div> : null}
    </header>
  );
}
