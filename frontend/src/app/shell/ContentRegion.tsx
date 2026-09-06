import { useEffect, useRef, type ReactElement, type ReactNode } from "react";
import { useLocation } from "react-router-dom";

export interface ContentRegionProps {
  readonly children: ReactNode;
}

/**
 * Finds the current route's page landmark inside `container` and, if
 * it is present and actually connected to the document, focuses it.
 * Returns whether it succeeded.
 *
 * Deliberately re-queries the DOM on every call rather than caching a
 * ref to a specific page's `<main>` — `InvestigationWorkspacePage`
 * alone swaps between several different `<PageLayout>`-owned `<main>`
 * elements across its own loading/error/success states, so a cached
 * reference would go stale the moment any of those states change. A
 * fresh, region-scoped query is what keeps this safe against both a
 * detached old-page node and a not-yet-rendered new one (task brief
 * §8).
 */
function focusCurrentPageMain(container: HTMLElement): boolean {
  const main = container.querySelector<HTMLElement>("main.page-layout");
  if (main === null || !document.contains(main)) {
    return false;
  }
  main.focus();
  return true;
}

/**
 * True once focus has ended up somewhere this shell should leave
 * alone — i.e. actually landed inside a real, connected element and
 * not merely fallen back to `document.body` (the browser's default
 * when a focused node is removed from the DOM, e.g. an unmounting
 * `<PageLayout>`) or onto a now-detached node. Used by the
 * navigation-recovery observer below to decide whether focus needs
 * rescuing at all — if something more specific (a page's own tab
 * switcher, a dialog, an in-page control) already holds it, the
 * route-level mechanism must not fight that (task brief §6).
 */
function isFocusStranded(): boolean {
  const active = document.activeElement;
  return active === null || active === document.body || !document.contains(active);
}

/**
 * Main content region — the page outlet (Phase 4G-2 Part 1).
 *
 * A thin structural wrapper: it owns only sizing/scroll containment
 * for whatever is mounted inside it, never the semantics of that
 * content. `AppRoutes` (`app/router.tsx`) already supplies the page's
 * `<main>` landmark, so this wrapper intentionally adds no competing
 * ARIA role — Part 2/Part 3 can mount real pages here without a
 * landmark collision.
 *
 * # Route-change focus management (MAX17-F-01)
 *
 * Colocated here rather than in `AppShell` because this is the one
 * shell element that actually wraps the routed content on every
 * navigation path (sidebar `NavLink`, whole-row `location.hash`
 * activation, and command-palette `navigate()` all end up rendering a
 * new page as this component's `children`) — the smallest existing
 * boundary that already sees every case in MAX17-F-01's finding,
 * exactly as the audit's own "recommended direction" described, with
 * no new provider/context/store.
 *
 * Keyed off `useLocation().pathname` specifically, not the full
 * location or its `key` — `InvestigationWorkspacePage`'s own tab
 * switcher (MAX7-F-02) persists the active tab via
 * `setSearchParams(..., { replace: true })`, which changes the
 * location (and its `key`) without changing the path, and which
 * already moves real DOM focus to the newly-selected tab itself
 * (`WorkspaceTabs.selectAndFocusTab`). Keying on `pathname` alone
 * means that local, already-correct focus management is never
 * second-guessed by this shell-level effect — the effect only ever
 * fires for an actual page-to-page navigation.
 *
 * # Timing (task brief §3/§8)
 *
 * The destination page can still be loading the first time this
 * effect runs after a location change — every page is code-split
 * (MAX8-F-01) and initially renders `RouteLoadingFallback` (itself a
 * `<PageLayout>`) until its chunk resolves, and
 * `InvestigationWorkspacePage` separately renders its own
 * loading-state `<PageLayout>` before its real success/error content.
 * Each of those is a real, distinct `<main>` that unmounts and is
 * replaced once the next one is ready, which — being a plain DOM
 * removal — sends focus to `document.body` in between. Rather than
 * an arbitrary delay, a `MutationObserver` scoped to this region
 * focuses the current page's `<main>` immediately, then keeps
 * watching for exactly that "focus fell back to body/a detached node"
 * signal for as long as this navigation is current, and re-anchors
 * focus to whatever `<main>` exists at that moment. It never
 * re-focuses main while focus is already usefully somewhere else in
 * the page (`isFocusStranded`), so it cannot fight a page's own local
 * focus management (e.g. tab switching, a dialog's own focus trap).
 */
export function ContentRegion({ children }: ContentRegionProps): ReactElement {
  const containerRef = useRef<HTMLDivElement>(null);
  const isInitialRenderRef = useRef(true);
  const location = useLocation();

  useEffect(() => {
    // Skip the very first render (initial page load): moving focus
    // away from wherever the browser/user already put it before any
    // navigation has actually happened is not this finding's
    // scope — MAX17-F-01 is about focus surviving a *route change*,
    // not about claiming focus on first paint.
    if (isInitialRenderRef.current) {
      isInitialRenderRef.current = false;
      return;
    }

    const container = containerRef.current;
    if (container === null) {
      return;
    }

    // Unconditional: this is what actually moves focus off a still-
    // connected, still-focused control from the *previous* page (a
    // clicked sidebar `NavLink`, an activated investigation row) —
    // the specific gap MAX17-F-01 documents. Whatever currently has
    // focus is, by definition, stale the moment the path has changed.
    focusCurrentPageMain(container);

    const observer = new MutationObserver(() => {
      if (!isFocusStranded()) {
        return;
      }
      focusCurrentPageMain(container);
    });
    observer.observe(container, { childList: true, subtree: true });

    return () => {
      observer.disconnect();
    };
  }, [location.pathname]);

  return (
    <div className="app-shell__content-region" ref={containerRef}>
      {children}
    </div>
  );
}
