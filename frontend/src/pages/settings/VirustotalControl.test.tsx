/**
 * `VirustotalControl` static-markup tests -- SOC-IQ Part 8 (ADR-008
 * Part 1B-3). `renderToStaticMarkup`, matching `pages.test.tsx`'s
 * no-jsdom-by-default convention -- these check the initial (idle,
 * empty-input) markup only. Interaction/save-lifecycle behavior is
 * covered by `VirustotalControl.live.test.tsx`.
 */

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { VirustotalControl } from "./VirustotalControl";

describe("VirustotalControl", () => {
  it("shows Configured when a key is configured", () => {
    const html = renderToStaticMarkup(<VirustotalControl configured={true} />);
    expect(html).toContain("Configured");
    expect(html).not.toContain("Not configured");
  });

  it("shows Not configured when no key is configured", () => {
    const html = renderToStaticMarkup(<VirustotalControl configured={false} />);
    expect(html).toContain("Not configured");
  });

  it("renders a password input, never prepopulated with a value", () => {
    const html = renderToStaticMarkup(<VirustotalControl configured={true} />);
    expect(html).toContain('type="password"');
    expect(html).not.toMatch(/value="[^"]+"/);
  });

  it("never renders a raw API key value in any form, configured or not", () => {
    const htmlConfigured = renderToStaticMarkup(<VirustotalControl configured={true} />);
    const htmlUnconfigured = renderToStaticMarkup(<VirustotalControl configured={false} />);
    expect(htmlConfigured).not.toMatch(/value="[^"]+"/);
    expect(htmlUnconfigured).not.toMatch(/value="[^"]+"/);
  });

  it("Save starts disabled since the input starts empty", () => {
    const html = renderToStaticMarkup(<VirustotalControl configured={false} />);
    expect(html).toContain("disabled=\"\"");
  });

  it("explains the OS-backed keystore architecture and restart requirement honestly", () => {
    const html = renderToStaticMarkup(<VirustotalControl configured={false} />);
    expect(html).toContain("OS-backed keystore");
    expect(html).toContain("restart");
  });

  it("never claims the credential is active immediately in its static copy", () => {
    const html = renderToStaticMarkup(<VirustotalControl configured={false} />);
    expect(html).not.toContain("Credential active");
    expect(html).not.toContain("now using the new key");
  });
});
