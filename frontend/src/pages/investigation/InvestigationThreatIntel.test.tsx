// @vitest-environment jsdom
/**
 * `InvestigationThreatIntel` tests — Phase 4J-6 Part 3A.
 *
 * Mirrors the established `act` + `createRoot` rendering convention
 * (`InvestigationOverviewThreatIntel.test.tsx`) -- no
 * `@testing-library/react` is introduced.
 */

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { InvestigationThreatIntel } from "./InvestigationThreatIntel";
import type { InvestigationWorkspaceData, InvestigationWorkspaceIndicator } from "./investigationWorkspaceModel";
import { TI_STATES, type TiState, type TypedVerdict } from "../../shared/api/types";

const BASE_DATA: InvestigationWorkspaceData = {
  investigationId: 7,
  reportName: "malware_report.txt",
  analyzedAt: "2026-08-26T00:00:00",
  status: "completed",
  riskScore: 82,
  severity: "high",
  confidence: 0.9,
  iocsByType: {},
  rawThreatIntelligence: {},
  correlations: [],
};

function makeData(overrides: Partial<InvestigationWorkspaceData>): InvestigationWorkspaceData {
  return { ...BASE_DATA, ...overrides };
}

function indicator(
  value: string,
  tiState: TiState | null,
  typedVerdict: TypedVerdict | null = null,
): InvestigationWorkspaceIndicator {
  return { value, tiState, typedVerdict };
}

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

function render(data: InvestigationWorkspaceData): void {
  act(() => {
    root = createRoot(container);
    root.render(<InvestigationThreatIntel data={data} />);
  });
}

function rerender(data: InvestigationWorkspaceData): void {
  act(() => {
    root.render(<InvestigationThreatIntel data={data} />);
  });
}

function statusBadges(): HTMLElement[] {
  return Array.from(
    container.querySelector(".investigation-threat-intel__badges--status")?.querySelectorAll(".status-badge") ?? [],
  );
}

function verdictBadges(): HTMLElement[] {
  return Array.from(
    container.querySelector(".investigation-threat-intel__badges--verdicts")?.querySelectorAll(".status-badge") ?? [],
  );
}

function supportRow(label: string): Element | undefined {
  return Array.from(container.querySelectorAll(".investigation-threat-intel__support-row")).find((row) =>
    row.textContent?.includes(label),
  );
}

describe("InvestigationThreatIntel", () => {
  describe("availability", () => {
    it("shows an honest unavailable state, never a fabricated 'Not enriched', when TI data failed", () => {
      render(makeData({ rawThreatIntelligence: null, iocsByType: { ipv4: [indicator("1.2.3.4", "enriched")] } }));

      expect(container.textContent).toContain("Threat Intelligence data unavailable");
      expect(container.textContent).not.toContain("Not enriched");
      expect(container.querySelector(".investigation-threat-intel__badges")).toBeNull();
    });

    it("shows an honest note when TI succeeded but IOC data (needed for the breakdown) failed", () => {
      render(makeData({ rawThreatIntelligence: {}, iocsByType: null }));

      expect(container.textContent).toContain("Threat Intelligence data was received");
      expect(container.textContent).toContain("IOC data for this investigation failed to load");
    });

    it("shows an honest empty state, distinct from unavailable, when there are no indicators to enrich", () => {
      render(makeData({ rawThreatIntelligence: {}, iocsByType: {} }));

      expect(container.textContent).toContain("No indicators to enrich");
      expect(container.textContent).not.toContain("unavailable");
    });
  });

  describe("canonical state coverage", () => {
    it("distinguishes every one of the six canonical states, with real per-state counts", () => {
      render(
        makeData({
          rawThreatIntelligence: {},
          iocsByType: {
            ipv4: [
              indicator("1.1.1.1", "enriched"),
              indicator("2.2.2.2", "enriched"),
              indicator("3.3.3.3", "no_api_key"),
            ],
            domains: [indicator("evil.example", "provider_error")],
            urls: [indicator("http://bad.example", "incomplete_check")],
            cves: [indicator("CVE-2024-0001", "unsupported_type")],
            emails: [indicator("a@b.com", "not_enriched")],
          },
        }),
      );

      expect(supportRow("Enriched (2)")).toBeDefined();
      expect(supportRow("No API key (1)")).toBeDefined();
      expect(supportRow("Provider error (1)")).toBeDefined();
      expect(supportRow("Incomplete check (1)")).toBeDefined();
      expect(supportRow("Unsupported type (1)")).toBeDefined();
      expect(supportRow("Not enriched (1)")).toBeDefined();
    });

    it.each(TI_STATES)("renders a real, honest badge and description for the '%s' state", (state) => {
      render(makeData({ rawThreatIntelligence: {}, iocsByType: { ipv4: [indicator("1.1.1.1", state)] } }));

      const badges = statusBadges();
      expect(badges).toHaveLength(1);
      // A real describing sentence exists for the state -- never
      // blank, and never the literal snake_case state value leaking
      // into the UI unexplained.
      const row = container.querySelector(".investigation-threat-intel__support-row dd");
      expect(row?.textContent?.length ?? 0).toBeGreaterThan(0);
    });

    it("keeps a real provider error visible and distinguishable, never disguised as success", () => {
      render(
        makeData({
          rawThreatIntelligence: {},
          iocsByType: { ipv4: [indicator("1.1.1.1", "provider_error")] },
        }),
      );

      const badge = statusBadges().find((el) => el.textContent === "Provider error");
      expect(badge?.className).toContain("status-badge--error");
      // Provider error describes the indicators, not the investigation
      // itself.
      expect(container.textContent).not.toMatch(/investigation (has )?failed/i);
    });

    it("never treats 'not_enriched' as an error or a missing-API-key state", () => {
      render(
        makeData({
          rawThreatIntelligence: {},
          iocsByType: { ipv4: [indicator("1.1.1.1", "not_enriched")] },
        }),
      );

      const badge = statusBadges().find((el) => el.textContent === "Not enriched");
      expect(badge?.className).toContain("status-badge--neutral");
      expect(container.textContent).not.toContain("No API key");
      expect(container.textContent).not.toContain("Provider error");
    });

    it("never treats 'incomplete_check' as 'enriched' or 'provider_error'", () => {
      render(
        makeData({
          rawThreatIntelligence: {},
          iocsByType: { ipv4: [indicator("1.1.1.1", "incomplete_check")] },
        }),
      );

      expect(container.textContent).not.toContain("Enriched");
      expect(container.textContent).not.toContain("Provider error");
      expect(container.textContent).toContain("Incomplete check");
    });

    it("reports indicators with no TI classification separately from 'not_enriched'", () => {
      render(
        makeData({
          rawThreatIntelligence: {},
          iocsByType: { ipv4: [indicator("1.1.1.1", null)] },
        }),
      );

      expect(supportRow("Not yet classified (1)")).toBeDefined();
      expect(container.textContent).not.toContain("Not enriched");
    });
  });

  describe("no fabrication", () => {
    it("never renders a state that does not actually occur in the data", () => {
      render(
        makeData({
          rawThreatIntelligence: {},
          iocsByType: { ipv4: [indicator("1.1.1.1", "enriched")] },
        }),
      );

      expect(container.textContent).not.toContain("Provider error");
      expect(container.textContent).not.toContain("No API key");
      expect(container.textContent).not.toContain("Incomplete check");
      expect(container.textContent).not.toContain("Unsupported type");
      expect(container.textContent).not.toContain("Not yet classified");
    });

    it("does not render a raw JSON payload viewer, even though Part 3C shows real fields", () => {
      // Superseded by Part 3C (task brief §6): the Provider details
      // disclosure now deliberately surfaces the payload's own real,
      // non-sensitive fields as a labeled hierarchy -- but never as a
      // dumped JSON string/`<pre>` block, which is what this test
      // guards.
      render(
        makeData({
          rawThreatIntelligence: { some_field: "a real value", nested: { a: 1 } },
          iocsByType: { ipv4: [indicator("1.1.1.1", "enriched")] },
        }),
      );

      expect(container.querySelector("pre")).toBeNull();
      expect(container.textContent).not.toContain('{"some_field"');
      expect(container.textContent).not.toContain('"nested":{"a":1}');
    });
  });

  describe("accessibility", () => {
    it("uses a real heading for the card", () => {
      render(makeData({}));

      const heading = Array.from(container.querySelectorAll("h2")).find((el) => el.textContent === "Threat Intelligence");
      expect(heading).toBeDefined();
    });

    it("uses real sub-headings for Status and Supporting information, distinct from the card title", () => {
      render(makeData({ rawThreatIntelligence: {}, iocsByType: { ipv4: [indicator("1.1.1.1", "enriched")] } }));

      const headings = Array.from(container.querySelectorAll("h3")).map((el) => el.textContent);
      expect(headings).toContain("Status");
      expect(headings).toContain("Supporting information");
    });

    it("gives every state text, not color alone, as the carrier of meaning", () => {
      render(makeData({ rawThreatIntelligence: {}, iocsByType: { ipv4: [indicator("1.1.1.1", "provider_error")] } }));

      const badge = statusBadges().find((el) => el.className.includes("status-badge--error"));
      expect(badge?.textContent).toBe("Provider error");
    });
  });

  describe("Part 3B — result summary", () => {
  function metricValue(label: string): string | undefined {
    const card = Array.from(container.querySelectorAll(".metric-card")).find(
      (el) => el.querySelector(".metric-card__label")?.textContent === label,
    );
    return card?.querySelector(".metric-card__value")?.textContent ?? undefined;
  }

  it("shows a real total-indicators metric alongside real per-state metrics", () => {
    render(
      makeData({
        rawThreatIntelligence: {},
        iocsByType: {
          ipv4: [indicator("1.1.1.1", "enriched"), indicator("2.2.2.2", "enriched"), indicator("3.3.3.3", "no_api_key")],
          domains: [indicator("evil.example", null)],
        },
      }),
    );

    expect(metricValue("Total indicators")).toBe("4");
    expect(metricValue("Enriched")).toBe("2");
    expect(metricValue("No API key")).toBe("1");
    expect(metricValue("Not yet classified")).toBe("1");
  });

  it("never shows a metric for a state that does not actually occur", () => {
    render(makeData({ rawThreatIntelligence: {}, iocsByType: { ipv4: [indicator("1.1.1.1", "enriched")] } }));

    expect(metricValue("Provider error")).toBeUndefined();
    expect(metricValue("No API key")).toBeUndefined();
    expect(metricValue("Not yet classified")).toBeUndefined();
  });

  it("omits the unclassified metric entirely when every indicator has a real state", () => {
    render(makeData({ rawThreatIntelligence: {}, iocsByType: { ipv4: [indicator("1.1.1.1", "enriched")] } }));

    expect(metricValue("Not yet classified")).toBeUndefined();
  });

  it("never invents a percentage or count not present in the underlying data", () => {
    render(
      makeData({
        rawThreatIntelligence: {},
        iocsByType: { ipv4: [indicator("1.1.1.1", "enriched"), indicator("2.2.2.2", "no_api_key")] },
      }),
    );

    expect(container.textContent).not.toMatch(/%/);
  });

  it("does not render the result summary in the unavailable state", () => {
    render(makeData({ rawThreatIntelligence: null, iocsByType: null }));

    expect(container.querySelector(".investigation-threat-intel__metrics")).toBeNull();
  });

  it("does not render the result summary when there are no indicators to enrich", () => {
    render(makeData({ rawThreatIntelligence: {}, iocsByType: {} }));

    expect(container.querySelector(".investigation-threat-intel__metrics")).toBeNull();
  });

  it("uses a real heading for the summary section, distinct from Status", () => {
    render(makeData({ rawThreatIntelligence: {}, iocsByType: { ipv4: [indicator("1.1.1.1", "enriched")] } }));

    const headings = Array.from(container.querySelectorAll("h3")).map((el) => el.textContent);
    expect(headings).toContain("Result summary");
  });
});

describe("Part 3C — provider details", () => {
  it("renders provider details in the main branch alongside Status and Result summary", () => {
    render(
      makeData({
        rawThreatIntelligence: { status: "complete" },
        iocsByType: { ipv4: [indicator("1.1.1.1", "enriched")] },
      }),
    );

    expect(container.querySelector("details.provider-detail__disclosure")).not.toBeNull();
    expect(container.textContent).toContain("complete");
  });

  it("renders provider details when TI succeeded but the IOC breakdown is unavailable", () => {
    render(makeData({ rawThreatIntelligence: { status: "complete" }, iocsByType: null }));

    expect(container.querySelector("details.provider-detail__disclosure")).not.toBeNull();
  });

  it("renders provider details in the no-indicators empty state, when real fields exist", () => {
    render(makeData({ rawThreatIntelligence: { status: "no_indicators" }, iocsByType: {} }));

    expect(container.querySelector("details.provider-detail__disclosure")).not.toBeNull();
    expect(container.textContent).toContain("no_indicators");
  });

  it("never renders provider details at all when TI data is unavailable", () => {
    render(makeData({ rawThreatIntelligence: null, iocsByType: null }));

    expect(container.querySelector("details.provider-detail__disclosure")).toBeNull();
    expect(container.textContent).not.toContain("Provider details");
  });

  it("does not fabricate provider details for a no_api_key state -- shows only real fields", () => {
    render(
      makeData({
        rawThreatIntelligence: { status: "no_api_key" },
        iocsByType: { ipv4: [indicator("1.1.1.1", "no_api_key")] },
      }),
    );

    expect(container.textContent).not.toMatch(/enriched successfully|scan complete/i);
    expect(container.textContent).toContain("no_api_key");
  });

  it("keeps provider-error data honest -- no fabricated successful metrics", () => {
    render(
      makeData({
        rawThreatIntelligence: { status: "error", invalid_api_key: true },
        iocsByType: { ipv4: [indicator("1.1.1.1", "provider_error")] },
      }),
    );

    expect(container.textContent).toContain("Yes");
    expect(container.textContent).not.toContain("100%");
  });

  it("does not leak provider detail fields from one investigation into another", () => {
    render(
      makeData({
        rawThreatIntelligence: { status: "investigation-one-status" },
        iocsByType: { ipv4: [indicator("1.1.1.1", "enriched")] },
      }),
    );
    expect(container.textContent).toContain("investigation-one-status");

    rerender(
      makeData({
        rawThreatIntelligence: { status: "investigation-two-status" },
        iocsByType: { ipv4: [indicator("2.2.2.2", "enriched")] },
      }),
    );

    expect(container.textContent).not.toContain("investigation-one-status");
    expect(container.textContent).toContain("investigation-two-status");
  });
});

describe("investigation change safety", () => {
    it("replaces old TI state entirely when the investigation's data changes", () => {
      render(makeData({ rawThreatIntelligence: {}, iocsByType: { ipv4: [indicator("1.1.1.1", "provider_error")] } }));
      expect(container.textContent).toContain("Provider error");

      rerender(makeData({ rawThreatIntelligence: {}, iocsByType: { domains: [indicator("evil.example", "enriched")] } }));

      expect(container.textContent).not.toContain("Provider error");
      expect(container.textContent).toContain("Enriched");
    });
  });
});

describe("Phase 4K-3 — result verdicts (typed verdicts)", () => {
  it("renders no verdict section when no indicator has a real typed verdict", () => {
    render(makeData({ rawThreatIntelligence: {}, iocsByType: { ipv4: [indicator("1.1.1.1", "enriched")] } }));

    const headings = Array.from(container.querySelectorAll("h3")).map((el) => el.textContent);
    expect(headings).not.toContain("Result verdicts");
  });

  it("renders real verdict counts, keeping 'Not Found' visibly distinct from 'Clean'", () => {
    render(
      makeData({
        rawThreatIntelligence: {},
        iocsByType: {
          sha256: [indicator("a", "enriched", "malicious"), indicator("b", "enriched", "clean")],
          ipv4: [indicator("1.2.3.4", "enriched", "not_found")],
        },
      }),
    );

    const headings = Array.from(container.querySelectorAll("h3")).map((el) => el.textContent);
    expect(headings).toContain("Result verdicts");

    const badges = verdictBadges();
    const clean = badges.find((el) => el.textContent === "Clean (1)");
    const notFound = badges.find((el) => el.textContent === "Not Found (1)");
    const malicious = badges.find((el) => el.textContent === "Malicious (1)");

    expect(malicious?.className).toContain("status-badge--critical");
    expect(clean?.className).toContain("status-badge--success");
    expect(notFound?.className).toContain("status-badge--neutral");
    // The two must never share a tone -- that would silently collapse
    // NOT_FOUND back into CLEAN, exactly what the backend's own
    // `Verdict` classification was built to prevent.
    expect(notFound?.className).not.toBe(clean?.className);
  });

  it("renders 'Suspicious' distinctly from every other verdict", () => {
    render(makeData({ rawThreatIntelligence: {}, iocsByType: { sha256: [indicator("a", "enriched", "suspicious")] } }));

    const badge = verdictBadges().find((el) => el.textContent === "Suspicious (1)");
    expect(badge?.className).toContain("status-badge--warning");
  });

  it("never treats typedVerdict: null as any real verdict -- an enriched indicator with no typed verdict is excluded", () => {
    render(
      makeData({
        rawThreatIntelligence: {},
        iocsByType: { ipv4: [indicator("1.1.1.1", "enriched", null)] },
      }),
    );

    const headings = Array.from(container.querySelectorAll("h3")).map((el) => el.textContent);
    expect(headings).not.toContain("Result verdicts");
  });

  it("never turns a provider_error, no_api_key, incomplete_check, or unsupported_type indicator into a Clean verdict", () => {
    render(
      makeData({
        rawThreatIntelligence: {},
        iocsByType: {
          ipv4: [indicator("1.1.1.1", "provider_error", null)],
          domains: [indicator("evil.example", "no_api_key", null)],
          urls: [indicator("http://bad.example", "incomplete_check", null)],
          cves: [indicator("CVE-2024-0001", "unsupported_type", null)],
        },
      }),
    );

    const headings = Array.from(container.querySelectorAll("h3")).map((el) => el.textContent);
    expect(headings).not.toContain("Result verdicts");
    expect(container.textContent).not.toContain("Clean (");
  });

  it("never fabricates a verdict section when rawThreatIntelligence is null", () => {
    render(makeData({ rawThreatIntelligence: null, iocsByType: { ipv4: [indicator("1.1.1.1", "enriched", "malicious")] } }));

    expect(container.textContent).not.toContain("Result verdicts");
  });

  it("never labels a provider -- typed_verdicts carries no provider identity", () => {
    render(
      makeData({
        rawThreatIntelligence: {},
        iocsByType: { sha256: [indicator("a", "enriched", "malicious")] },
      }),
    );

    expect(container.textContent).not.toContain("Provider: VirusTotal");
  });

  it("does not require the raw threat_intelligence payload to render a real typed verdict", () => {
    render(
      makeData({
        rawThreatIntelligence: {},
        iocsByType: { sha256: [indicator("a", "enriched", "malicious")] },
      }),
    );

    const badge = verdictBadges().find((el) => el.textContent === "Malicious (1)");
    expect(badge).toBeDefined();
  });
});

describe("Phase 4K-3 — indicator verdicts (typed verdicts)", () => {
  it("renders no indicator-verdicts section when no indicator has a real typed verdict", () => {
    render(makeData({ rawThreatIntelligence: {}, iocsByType: { ipv4: [indicator("1.1.1.1", "enriched")] } }));

    const headings = Array.from(container.querySelectorAll("h3")).map((el) => el.textContent);
    expect(headings).not.toContain("Indicator verdicts");
  });

  it("renders a real per-indicator verdict row for every indicator with a real typed verdict", () => {
    render(
      makeData({
        rawThreatIntelligence: {},
        iocsByType: {
          sha256: [indicator("abc123", "enriched", "malicious")],
          ipv4: [indicator("1.2.3.4", "enriched", "not_found")],
        },
      }),
    );

    const headings = Array.from(container.querySelectorAll("h3")).map((el) => el.textContent);
    expect(headings).toContain("Indicator verdicts");
    expect(container.textContent).toContain("abc123");
    expect(container.textContent).toContain("1.2.3.4");

    const badges = Array.from(container.querySelectorAll("table .status-badge"));
    const malicious = badges.find((el) => el.textContent === "Malicious");
    const notFound = badges.find((el) => el.textContent === "Not Found");
    expect(malicious?.className).toContain("status-badge--critical");
    expect(notFound?.className).toContain("status-badge--neutral");
  });

  it("never shows an indicator with typedVerdict: null in this table", () => {
    render(
      makeData({
        rawThreatIntelligence: {},
        iocsByType: {
          sha256: [indicator("known", "enriched", "clean"), indicator("unclassified", "enriched", null)],
        },
      }),
    );

    expect(container.textContent).toContain("known");
    expect(container.textContent).not.toContain("unclassified");
  });

  it("never fabricates an indicator-verdicts section when rawThreatIntelligence is null", () => {
    render(
      makeData({
        rawThreatIntelligence: null,
        iocsByType: { ipv4: [indicator("1.1.1.1", "enriched", "malicious")] },
      }),
    );

    expect(container.textContent).not.toContain("Indicator verdicts");
  });

  it("keeps existing TiState status rendering intact alongside the new typed-verdict sections", () => {
    render(
      makeData({
        rawThreatIntelligence: {},
        iocsByType: { ipv4: [indicator("1.1.1.1", "provider_error", "malicious")] },
      }),
    );

    // Same indicator can honestly carry both a real tiState ("the
    // lookup failed with a provider error") and a real typedVerdict
    // ("but a verdict was still persisted") -- neither is dropped or
    // overridden by the other.
    const statusBadge = statusBadges().find((el) => el.textContent === "Provider error");
    expect(statusBadge?.className).toContain("status-badge--error");

    const verdictBadge = verdictBadges().find((el) => el.textContent === "Malicious (1)");
    expect(verdictBadge).toBeDefined();
  });
});
