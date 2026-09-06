// @vitest-environment jsdom
/**
 * `InvestigationOverviewTimeline` tests — Phase 4J-6 Part 1D, extended
 * in A4-P2-P3 Part 5C for the real timeline presentation.
 *
 * Mirrors the established `act` + `createRoot` rendering convention
 * (`InvestigationOverviewSummary.test.tsx`) -- no
 * `@testing-library/react` is introduced.
 */

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { InvestigationOverviewTimeline } from "./InvestigationOverviewTimeline";
import type {
  InvestigationWorkspaceData,
  InvestigationWorkspaceTimelineEvent,
} from "./investigationWorkspaceModel";

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
  timeline: null,
};

function makeData(overrides: Partial<InvestigationWorkspaceData>): InvestigationWorkspaceData {
  return { ...BASE_DATA, ...overrides };
}

const EVENT_1: InvestigationWorkspaceTimelineEvent = {
  eventId: "evt-1",
  investigationId: 7,
  eventType: "analysis_started",
  timestamp: "2026-08-26T00:00:00",
  source: "analyzer",
  summary: "Analysis started for malware_report.txt",
  metadata: {},
  semantics: "lifecycle",
};

const EVENT_2: InvestigationWorkspaceTimelineEvent = {
  eventId: "evt-2",
  investigationId: 7,
  eventType: "ioc_extracted",
  timestamp: "2026-08-26T00:02:15",
  source: "extractor",
  summary: "Extracted 4 IPv4 indicators & 1 domain",
  metadata: { count: 5 },
  semantics: "extraction",
};

const EVENT_3: InvestigationWorkspaceTimelineEvent = {
  eventId: "evt-3",
  investigationId: 7,
  eventType: "analysis_completed",
  timestamp: "2026-08-26T00:05:40",
  source: "analyzer",
  summary: "Analysis completed with risk score 82 (high, confidence 90%)",
  metadata: { duration_seconds: 340 },
  semantics: "lifecycle",
};

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
    root.render(<InvestigationOverviewTimeline data={data} />);
  });
}

function eventEls(): Element[] {
  return Array.from(container.querySelectorAll(".investigation-overview-timeline__event"));
}

describe("InvestigationOverviewTimeline", () => {
  describe("populated timeline (A4-P2-P3 Part 5C)", () => {
    it("renders every real event supplied, with its actual summary, semantics, and timestamp", () => {
      render(makeData({ timeline: [EVENT_1, EVENT_2, EVENT_3] }));

      const events = eventEls();
      expect(events).toHaveLength(3);

      expect(container.textContent).toContain("Analysis started for malware_report.txt");
      expect(container.textContent).toContain("Extracted 4 IPv4 indicators & 1 domain");
      expect(container.textContent).toContain("Analysis completed with risk score 82 (high, confidence 90%)");

      expect(container.textContent).toContain("2026-08-26T00:00:00");
      expect(container.textContent).toContain("2026-08-26T00:02:15");
      expect(container.textContent).toContain("2026-08-26T00:05:40");

      expect(container.textContent).toContain("lifecycle");
      expect(container.textContent).toContain("extraction");

      expect(container.textContent).toContain("analysis_started");
      expect(container.textContent).toContain("ioc_extracted");
      expect(container.textContent).toContain("analysis_completed");
    });

    it("renders events in the exact order supplied, never reordering by timestamp or any other field", () => {
      // EVENT_2/EVENT_3 are chronologically later than EVENT_1 -- pass
      // them in a deliberately non-chronological order to prove this
      // component doesn't sort.
      render(makeData({ timeline: [EVENT_3, EVENT_1, EVENT_2] }));

      const events = eventEls();
      expect(events).toHaveLength(3);
      expect(events[0]!.textContent).toContain("Analysis completed with risk score 82 (high, confidence 90%)");
      expect(events[1]!.textContent).toContain("Analysis started for malware_report.txt");
      expect(events[2]!.textContent).toContain("Extracted 4 IPv4 indicators & 1 domain");
    });

    it("renders a single real event correctly (not just the multi-event case)", () => {
      render(makeData({ timeline: [EVENT_2] }));

      const events = eventEls();
      expect(events).toHaveLength(1);
      expect(events[0]!.textContent).toContain("Extracted 4 IPv4 indicators & 1 domain");
      expect(events[0]!.textContent).toContain("2026-08-26T00:02:15");
    });

    it("renders real event values, not hard-coded placeholder text", () => {
      const customEvent: InvestigationWorkspaceTimelineEvent = {
        eventId: "evt-custom",
        investigationId: 7,
        eventType: "custom_event_type_xyz",
        timestamp: "2026-01-02T03:04:05",
        source: "custom-source",
        summary: "A wholly distinctive summary string: Zx19!",
        metadata: {},
        semantics: "custom-semantics-value",
      };
      render(makeData({ timeline: [customEvent] }));

      expect(container.textContent).toContain("A wholly distinctive summary string: Zx19!");
      expect(container.textContent).toContain("custom_event_type_xyz");
      expect(container.textContent).toContain("custom-semantics-value");
      expect(container.textContent).toContain("2026-01-02T03:04:05");
    });

    it("handles event text containing ordinary punctuation without corruption or crashing", () => {
      const punctuatedEvent: InvestigationWorkspaceTimelineEvent = {
        eventId: "evt-punct",
        investigationId: 7,
        eventType: "note_added",
        timestamp: "2026-08-26T00:10:00",
        source: "analyst",
        summary: "IOC 1.2.3.4 flagged; see ticket #482 -- \"high priority\" (re-check w/ vendor).",
        metadata: {},
        semantics: "annotation",
      };

      expect(() => render(makeData({ timeline: [punctuatedEvent] }))).not.toThrow();
      expect(container.textContent).toContain(
        "IOC 1.2.3.4 flagged; see ticket #482 -- \"high priority\" (re-check w/ vendor).",
      );
    });

    it("does not fabricate additional events beyond what was actually supplied", () => {
      render(makeData({ timeline: [EVENT_1] }));

      expect(eventEls()).toHaveLength(1);
      expect(container.textContent).not.toContain("Extracted 4 IPv4 indicators");
      expect(container.textContent).not.toContain("Analysis completed with risk score");
    });

    it("never shows the unavailable/empty note when real events are present", () => {
      render(makeData({ timeline: [EVENT_1] }));

      expect(container.textContent).not.toContain("Timeline data unavailable");
      expect(container.textContent).not.toContain("No timeline events have been recorded");
    });
  });

  describe("empty timeline (A4-P2-P3 Part 5C)", () => {
    it("renders an honest empty state, not a fabricated event", () => {
      render(makeData({ timeline: [] }));

      expect(eventEls()).toHaveLength(0);
      expect(container.textContent).toContain("No timeline events have been recorded");
    });

    it("does not present an empty timeline as unavailable data", () => {
      render(makeData({ timeline: [] }));

      expect(container.textContent).not.toContain("Timeline data unavailable");
    });

    it("does not fall back to the analyzedAt/status note for a genuinely empty timeline", () => {
      render(makeData({ timeline: [], analyzedAt: "2026-08-26T00:00:00", status: "completed" }));

      // A real, successful, empty timeline is not the same as "no
      // real timeline was ever fetched" -- the fallback must not
      // substitute its own event for it.
      expect(container.textContent).not.toContain("latest known status");
      expect(eventEls()).toHaveLength(0);
    });
  });

  describe("missing timeline (null) — Part 1D fallback", () => {
    it("shows an honest unavailable state when there is no real timestamp to anchor a timeline on", () => {
      render(makeData({ timeline: null, analyzedAt: "" }));

      expect(container.textContent).toContain("Timeline data unavailable");
      expect(eventEls()).toHaveLength(0);
    });

    it("treats a whitespace-only timestamp the same as a genuinely absent one", () => {
      render(makeData({ timeline: null, analyzedAt: "   " }));

      expect(container.textContent).toContain("Timeline data unavailable");
    });

    it("falls back to the one genuine timestamp/status pair when timeline is null but analyzedAt exists", () => {
      render(makeData({ timeline: null, analyzedAt: "2026-08-26T00:00:00", status: "completed" }));

      const events = eventEls();
      expect(events).toHaveLength(1);
      expect(container.textContent).toContain("2026-08-26T00:00:00");
      expect(container.textContent).toContain("completed");
    });

    it("labels the analyzedAt/status fallback explicitly as a fallback, not as real event history", () => {
      render(makeData({ timeline: null, analyzedAt: "2026-08-26T00:00:00", status: "completed" }));

      // The fallback must be clearly distinguishable from real
      // historical event data -- it says so explicitly.
      expect(container.textContent).toContain("latest known status");
    });

    it("never fabricates additional pipeline stages beyond the one real fallback event", () => {
      render(makeData({ timeline: null, analyzedAt: "2026-08-26T00:00:00", status: "completed" }));

      expect(container.textContent).not.toContain("Analysis started");
      expect(container.textContent).not.toContain("IOC extraction completed");
      expect(container.textContent).not.toContain("Threat intelligence completed");
    });

    it("treats an undefined timeline (pre-Part-5A test double shape) the same as an explicit null", () => {
      const { timeline: _omit, ...rest } = makeData({ analyzedAt: "2026-08-26T00:00:00", status: "completed" });
      render(rest as InvestigationWorkspaceData);

      const events = eventEls();
      expect(events).toHaveLength(1);
      expect(container.textContent).toContain("latest known status");
    });
  });

  describe("fallback precedence (A4-P2-P3 Part 5C)", () => {
    it("renders the real populated timeline instead of the analyzedAt/status fallback when both are present", () => {
      render(
        makeData({
          timeline: [EVENT_1, EVENT_2],
          analyzedAt: "2026-08-26T00:00:00",
          status: "completed",
        }),
      );

      // Real events render...
      expect(container.textContent).toContain("Analysis started for malware_report.txt");
      expect(container.textContent).toContain("Extracted 4 IPv4 indicators & 1 domain");
      // ...and the synthetic single-event fallback does not replace them.
      expect(container.textContent).not.toContain("latest known status");
      expect(eventEls()).toHaveLength(2);
    });

    it("never uses analyzedAt/status to invent a historical event when a real (even single-event) timeline exists", () => {
      render(makeData({ timeline: [EVENT_2], analyzedAt: "2026-08-26T00:00:00", status: "completed" }));

      const events = eventEls();
      expect(events).toHaveLength(1);
      expect(events[0]!.textContent).toContain("Extracted 4 IPv4 indicators & 1 domain");
      // The status badge value ("completed") from the fallback path
      // must not be conflated with a real event's own eventType/summary.
      expect(container.textContent).not.toContain("latest known status");
    });
  });

  describe("accessibility", () => {
    it("uses a real heading for the card", () => {
      render(makeData({}));

      const heading = Array.from(container.querySelectorAll("h2")).find(
        (el) => el.textContent === "Timeline",
      );
      expect(heading).toBeDefined();
    });

    it("keeps event type/status conveyed through readable text, not color alone", () => {
      render(makeData({ timeline: [EVENT_1] }));

      // The event type is real, visible text content -- not encoded
      // only via a CSS class/color.
      expect(container.textContent).toContain("analysis_started");
    });

    it("uses an ordered list to preserve the timeline's meaningful sequence for assistive tech", () => {
      render(makeData({ timeline: [EVENT_1, EVENT_2] }));

      expect(container.querySelector("ol.investigation-overview-timeline__events")).not.toBeNull();
    });
  });
});
