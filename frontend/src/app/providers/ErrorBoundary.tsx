import { Component, createRef, type ErrorInfo, type ReactNode, type RefObject } from "react";
import { Button } from "../../pages/components/Button";

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  error: Error | null;
}

/**
 * Application-level error boundary foundation.
 *
 * Catches render-time errors anywhere in the tree beneath it so a bug
 * in one feature module can't take down the whole shell. This is the
 * foundation only — a feature-specific fallback UI (e.g. "retry the
 * investigation fetch") is feature-module work, not shell work.
 *
 * MAX13-F-01: previously, once this boundary caught an error the
 * fallback below was permanent for the rest of the session — the only
 * way an analyst could get back into a working application was a full
 * restart, discarding whatever investigation/analysis/report state was
 * in progress elsewhere in the app. The "Try again" action below
 * clears the caught error from state, which causes React to attempt to
 * render `this.props.children` again. If whatever triggered the
 * original error is still present, the boundary will simply catch it
 * again — this is intentionally the full extent of the recovery
 * behavior; no retry counters, backoff, or other machinery is added
 * here, consistent with this being a foundation-level boundary rather
 * than feature-specific recovery logic.
 *
 * MAX14-F-01: catching an error here replaces the *entire* app (this
 * boundary wraps everything in `App.tsx`), but nothing previously
 * moved keyboard focus into the fallback when that happened. A
 * keyboard-only analyst whose focus was on some now-unmounted element
 * was left with focus silently reset to the document body, with no
 * indication of where to go next -- they had to tab from the top of
 * an otherwise-empty page to find "Try again." The fallback's
 * `role="alert"` container is now also a programmatic focus target
 * (`tabIndex={-1}`, matching the standard pattern for a
 * script-focused, non-tabbable element) and is focused the moment the
 * fallback appears -- on the initial catch and again if "Try again"
 * re-catches the same underlying error. This follows the same
 * explicit `.focus()`-on-transition convention already used by
 * `InvestigationWorkspacePage`'s tab switching and `CommandPalette`,
 * applied to this boundary for the first time.
 */
export class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  public override state: ErrorBoundaryState = { error: null };

  private readonly fallbackRef: RefObject<HTMLDivElement> = createRef();

  public static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  public override componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    // Foundation-only: log to the console. Wiring this to a real
    // diagnostics/observability sink is
    // docs/architecture/19-observability-architecture.md work, not
    // this phase's.
    // eslint-disable-next-line no-console
    console.error("SOC-IQ: unhandled error in component tree", error, errorInfo);

    // MAX14-F-01: componentDidCatch fires after the fallback has
    // already committed to the DOM (both for an error caught on the
    // very first render and for one caught later), so the ref is
    // guaranteed to be attached here -- unlike componentDidUpdate,
    // this also covers the case where the error is thrown before this
    // boundary has ever successfully rendered its children once.
    this.fallbackRef.current?.focus();
  }

  private readonly handleReset = (): void => {
    this.setState({ error: null });
  };

  public override render(): ReactNode {
    if (this.state.error) {
      return (
        <div
          ref={this.fallbackRef}
          role="alert"
          tabIndex={-1}
          className="app-error-boundary"
        >
          <h1>Something went wrong</h1>
          <p>SOC-IQ hit an unexpected error and this view could not render.</p>
          <Button variant="primary" onClick={this.handleReset}>
            Try again
          </Button>
        </div>
      );
    }

    return this.props.children;
  }
}
