import type { ButtonHTMLAttributes, ReactElement } from "react";
import "./Button.css";

/**
 * Shared Button primitive (MAX-6, F-01/F-04).
 *
 * Before this component, "retry" alone had three independently
 * implemented visual treatments across five pages (Dashboard,
 * Analyze, Investigations, Reports, Settings) -- and Dashboard's
 * version declared no color/background/border at all, rendering as
 * an unstyled native browser button. A second, separately-drifted
 * filled-button spec existed for the Investigations/Reports export
 * actions. This component consolidates both families into one
 * primitive so equivalent actions can no longer drift apart.
 *
 * `variant="primary"` (default) is the filled brand-purple button
 * used for the app's default committed action (retry, save, etc.).
 * `variant="secondary"` is the transparent/outlined button used by
 * Analyze's browse/start/retry controls.
 *
 * `size="compact"` is the smaller, page-header-scoped treatment used
 * by the Investigations/Reports export actions -- a legitimately
 * different context (inline page-header action vs. a Card's
 * full-width error-state action), not a bug, so it stays a supported
 * size rather than being forced to match the default size.
 *
 * No local `:focus-visible` override is defined here on purpose: the
 * global `:focus-visible` rule in `globals.css` (`--color-border-focus`)
 * already applies to every button by default, which is the whole
 * point -- one focus-indicator color for the app (MAX-1), not a
 * per-component reimplementation of it.
 */
export type ButtonVariant = "primary" | "secondary";
export type ButtonSize = "default" | "compact";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  readonly variant?: ButtonVariant;
  readonly size?: ButtonSize;
}

export function Button({
  variant = "primary",
  size = "default",
  className,
  type = "button",
  ...rest
}: ButtonProps): ReactElement {
  const classes = [
    "button",
    `button--${variant}`,
    size === "compact" ? "button--compact" : "",
    className ?? "",
  ]
    .filter(Boolean)
    .join(" ");

  return <button type={type} className={classes} {...rest} />;
}
