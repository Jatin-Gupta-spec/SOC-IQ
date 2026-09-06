/**
 * `Button` tests (MAX-6, F-01/F-04).
 *
 * `renderToStaticMarkup`, matching the project's existing
 * no-jsdom-by-default convention (see `pages.test.tsx`). Verifies the
 * primitive renders a real `<button>` (native keyboard/activation
 * semantics, per MAX-1 -- no clickable-`<div>` regression), applies
 * the expected variant/size classes, passes through disabled and
 * aria attributes untouched, and -- critically for F-02 -- does NOT
 * declare a local `:focus-visible` override, so it inherits the one
 * global focus rule in `globals.css` rather than reintroducing a
 * second focus-color system.
 */

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { Button } from "./Button";

describe("Button", () => {
  it("renders a real <button> element", () => {
    const html = renderToStaticMarkup(<Button>Retry</Button>);
    expect(html).toContain("<button");
    expect(html).toContain(">Retry<");
  });

  it("defaults to type=\"button\" so it never submits a form by accident", () => {
    const html = renderToStaticMarkup(<Button>Retry</Button>);
    expect(html).toContain('type="button"');
  });

  it("defaults to the primary variant", () => {
    const html = renderToStaticMarkup(<Button>Retry</Button>);
    expect(html).toContain("button--primary");
    expect(html).not.toContain("button--secondary");
    expect(html).not.toContain("button--compact");
  });

  it("applies the secondary variant class", () => {
    const html = renderToStaticMarkup(<Button variant="secondary">Browse</Button>);
    expect(html).toContain("button--secondary");
  });

  it("applies the compact size class", () => {
    const html = renderToStaticMarkup(
      <Button size="compact">Export CSV</Button>,
    );
    expect(html).toContain("button--compact");
  });

  it("passes through disabled, aria-busy, and aria-label", () => {
    const html = renderToStaticMarkup(
      <Button disabled aria-busy="true" aria-label="Exporting">
        Export CSV
      </Button>,
    );
    expect(html).toContain("disabled=\"\"");
    expect(html).toContain('aria-busy="true"');
    expect(html).toContain('aria-label="Exporting"');
  });

  it("preserves a caller-supplied className alongside the primitive's own classes", () => {
    const html = renderToStaticMarkup(
      <Button className="dashboard-page__retry-button">Retry</Button>,
    );
    expect(html).toContain("dashboard-page__retry-button");
    expect(html).toContain("button--primary");
  });

  it("does not declare a local :focus-visible override (F-02 — relies on the global MAX-1 focus rule)", async () => {
    // @ts-expect-error -- no @types/node in this project; see
    // shared/notifications/reducedMotion.test.ts for the established
    // precedent of reading a source file via Node's built-in fs from
    // within a dynamic import rather than adding @types/node.
    const fs = await import(/* @vite-ignore */ "node:fs");
    // @ts-expect-error -- see above.
    const url = await import(/* @vite-ignore */ "node:url");
    const cssPath = url.fileURLToPath(new URL("./Button.css", import.meta.url));
    const css = fs.readFileSync(cssPath, "utf-8") as string;
    expect(css).not.toContain(":focus-visible");
    expect(css).not.toContain("--color-status-info");
  });
});
