import type { ReactElement, ReactNode } from "react";
import "./Card.css";

export interface CardProps {
  readonly title?: string;
  readonly children: ReactNode;
  /** Extra class name for page-specific card variants (e.g. grid placement). */
  readonly className?: string;
}

/**
 * Generic surface panel (Phase 4G-2 Part 3, §17).
 *
 * The one shared "card" primitive every mock page's panels compose,
 * built from existing surface/border/radius tokens only — no new
 * visual system per §17. Deliberately minimal (title + body): pages
 * needing a more specific shape (metrics, tables) compose this with
 * their own inner content rather than this component growing
 * page-specific props.
 */
export function Card({ title, children, className }: CardProps): ReactElement {
  const classes = className ? `card ${className}` : "card";
  return (
    <section className={classes}>
      {title ? <h2 className="card__title">{title}</h2> : null}
      <div className="card__body">{children}</div>
    </section>
  );
}
