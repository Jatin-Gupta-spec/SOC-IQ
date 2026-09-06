/**
 * `PageLayout` tests — MAX-17 Phase 2A (MAX17-F-01).
 *
 * Narrow, focused coverage for the one change this finding makes to
 * this file: `tabIndex={-1}` on the `<main>` landmark. Everything
 * else about `PageLayout` (the landmark itself, its `aria-label`,
 * its children) already has coverage via `pages.test.tsx`'s per-page
 * assertions — this file only proves the new, focus-specific
 * behavior: programmatically focusable, but not part of the page's
 * normal (Tab-key) sequential navigation order (task brief §10,
 * required Test 6).
 */

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { PageLayout } from "./PageLayout";

describe("PageLayout", () => {
  it("renders its <main> landmark with tabIndex={-1} so it can be focused programmatically", () => {
    const html = renderToStaticMarkup(
      <PageLayout label="Example page">
        <p>content</p>
      </PageLayout>,
    );

    expect(html).toContain('tabindex="-1"');
  });

  it("does not add a positive tabIndex, which would join the normal Tab order", () => {
    const html = renderToStaticMarkup(
      <PageLayout label="Example page">
        <p>content</p>
      </PageLayout>,
    );

    expect(html).not.toMatch(/tabindex="(?!-1)\d+"/);
  });

  it("keeps the existing landmark role and accessible name unchanged", () => {
    const html = renderToStaticMarkup(
      <PageLayout label="Example page">
        <p>content</p>
      </PageLayout>,
    );

    expect(html).toContain("<main");
    expect(html).toContain('aria-label="Example page"');
    expect(html).toContain('class="page-layout"');
  });
});
