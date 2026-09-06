// @vitest-environment jsdom
/**
 * `ProviderDetail` tests — Phase 4J-6 Part 3C.
 *
 * Mirrors the established `act` + `createRoot` rendering convention
 * (`InvestigationThreatIntel.test.tsx`) -- no
 * `@testing-library/react` is introduced.
 */

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { ProviderDetail } from "./ProviderDetail";

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  container = document.createElement("div");
  document.body.appendChild(container);
});

afterEach(() => {
  act(() => {
    root.unmount();
  });
  container.remove();
});

function render(raw: Record<string, unknown>): void {
  act(() => {
    root = createRoot(container);
    root.render(<ProviderDetail raw={raw} />);
  });
}

function disclosure(): HTMLDetailsElement | null {
  return container.querySelector("details.provider-detail__disclosure");
}

describe("ProviderDetail", () => {
  describe("real fields only", () => {
    it("renders a real top-level field with its actual key (humanized) and value", () => {
      render({ status: "partial" });

      expect(container.textContent).toContain("Status");
      expect(container.textContent).toContain("partial");
    });

    it("renders real nested object fields as a labeled hierarchy, not a JSON string", () => {
      render({ coverage: { requested: 5, succeeded: 3 } });

      expect(container.textContent).toContain("Coverage");
      expect(container.textContent).toContain("Requested");
      expect(container.textContent).toContain("5");
      expect(container.textContent).toContain("Succeeded");
      expect(container.textContent).toContain("3");
      expect(container.textContent).not.toContain("{");
      expect(container.querySelector("pre")).toBeNull();
    });

    it("renders real array fields as a list of their real items", () => {
      render({ hashes: [{ sha256: "abc123", malicious: 0 }] });

      expect(container.textContent).toContain("Hashes");
      expect(container.textContent).toContain("Sha256");
      expect(container.textContent).toContain("abc123");
    });

    it("never renders a field label that is not one of the payload's own real keys", () => {
      render({ status: "complete" });

      expect(container.textContent).not.toContain("Reputation");
      expect(container.textContent).not.toContain("Detection Information");
      expect(container.textContent).not.toContain("Verdict");
    });

    it("formats boolean values honestly without inventing a numeric interpretation", () => {
      render({ invalid_api_key: false });

      expect(container.textContent).toContain("No");
      expect(container.textContent).not.toContain("0 malicious");
    });
  });

  describe("safety", () => {
    it.each(["api_key", "apiKey", "auth_token", "secret", "password", "credential", "authorization"])(
      "withholds a field whose key name is '%s'",
      (sensitiveKey) => {
        render({ [sensitiveKey]: "should-never-render", status: "complete" });

        expect(container.textContent).not.toContain("should-never-render");
        expect(container.textContent).toContain("complete");
      },
    );

    it("shows a real non-secret status flag whose name merely mentions 'api_key'", () => {
      render({ invalid_api_key: true, status: "error" });

      expect(container.textContent).toContain("Invalid Api Key");
      expect(container.textContent).toContain("Yes");
    });

    it("withholds a sensitive-named key at any nesting depth, not just the top level", () => {
      render({ coverage: { requested: 5, api_key: "should-never-render" } });

      expect(container.textContent).not.toContain("should-never-render");
      expect(container.textContent).toContain("Requested");
    });

    it("shows an honest empty note when every field was withheld as sensitive", () => {
      render({ api_key: "hidden-value" });

      expect(container.textContent).not.toContain("hidden-value");
      expect(container.textContent).toContain("No provider detail fields are available");
      expect(disclosure()).toBeNull();
    });
  });

  describe("empty/null data", () => {
    it("shows an honest note, not an empty disclosure, for a genuinely empty payload", () => {
      render({});

      expect(container.textContent).toContain("No provider detail fields are available");
      expect(disclosure()).toBeNull();
    });

    it("renders a real null field value honestly rather than as fabricated zero results", () => {
      render({ last_error: null });

      expect(container.textContent).toContain("Not provided");
      expect(container.textContent).not.toContain("0 results");
    });
  });

  describe("long values", () => {
    it("renders a long real value in full without clipping it", () => {
      const longHash = "a".repeat(300);
      render({ sha256: longHash });

      expect(container.textContent).toContain(longHash);
    });
  });

  describe("disclosure", () => {
    it("is closed by default", () => {
      render({ status: "complete" });

      expect(disclosure()?.open).toBe(false);
    });

    it("opens when the summary is activated", () => {
      render({ status: "complete" });

      act(() => {
        disclosure()!.open = true;
        disclosure()!.dispatchEvent(new Event("toggle"));
      });

      expect(disclosure()?.open).toBe(true);
    });

    it("uses a real, keyboard-focusable native <summary> element", () => {
      render({ status: "complete" });

      const summary = container.querySelector("summary.provider-detail__summary");
      expect(summary).not.toBeNull();
      expect(summary?.tagName).toBe("SUMMARY");
    });
  });

  describe("provider neutrality", () => {
    it("renders whatever real provider-shaped field the payload actually supplies", () => {
      render({ provider: "SomeOtherProvider" });

      expect(container.textContent).toContain("SomeOtherProvider");
    });

    it("does not assume or hardcode a specific provider name", () => {
      render({ status: "complete" });

      expect(container.textContent).not.toContain("VirusTotal");
    });
  });
});
