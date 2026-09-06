import { describe, expect, it } from "vitest";

import {
  normalizeInvestigationWorkspace,
  type InvestigationWorkspaceThreatIntelligenceInput,
} from "./investigationWorkspaceModel";
import {
  PERSISTED_IOC_TYPES,
  TI_STATES,
  type GetInvestigationResult,
  type GetInvestigationRiskExplanationResult,
  type IocSignificanceByType,
  type IocsByType,
  type InvestigationIndicatorStates,
  type TimelineEvent,
} from "../../shared/api/types";

const BASE_INVESTIGATION: GetInvestigationResult = {
  investigation_id: 7,
  report_name: "report.txt",
  risk_score: 42,
  severity: "high",
  confidence: 0.9,
  status: "complete",
  analyzed_at: "2026-08-26T00:00:00",
  correlations: [],
};

describe("normalizeInvestigationWorkspace", () => {
  it("normalizes a complete investigation with IOCs and TI states", () => {
    const iocs: IocsByType = {
      ipv4: ["1.2.3.4"],
      domains: ["evil.example"],
    };
    const states: InvestigationIndicatorStates = {
      ipv4: { "1.2.3.4": "enriched" },
      domains: { "evil.example": "not_enriched" },
    };
    const threatIntelligence: InvestigationWorkspaceThreatIntelligenceInput = {
      raw: { "1.2.3.4": { vendor: "vt", malicious: 3 } },
      states,
    };

    const result = normalizeInvestigationWorkspace(BASE_INVESTIGATION, iocs, threatIntelligence);

    expect(result).toEqual({
      investigationId: 7,
      reportName: "report.txt",
      analyzedAt: "2026-08-26T00:00:00",
      status: "complete",
      riskScore: 42,
      severity: "high",
      confidence: 0.9,
      iocsByType: {
        ipv4: [{ value: "1.2.3.4", tiState: "enriched", typedVerdict: null }],
        domains: [{ value: "evil.example", tiState: "not_enriched", typedVerdict: null }],
      },
      iocSignificance: null,
      rawThreatIntelligence: { "1.2.3.4": { vendor: "vt", malicious: 3 } },
      correlations: [],
      timeline: null,
      riskExplanation: null,
    });
  });

  it("normalizes get_investigation's correlations field into camelCase, field-for-field (Phase 4J-6)", () => {
    const withCorrelations: GetInvestigationResult = {
      ...BASE_INVESTIGATION,
      correlations: [
        {
          relationship_type: "domain_url_host",
          source: "evil.com",
          target: "https://evil.com/payload.exe",
          context: "URL host matches extracted domain 'evil.com' exactly.",
        },
      ],
    };

    const result = normalizeInvestigationWorkspace(withCorrelations, null, null);

    expect(result.correlations).toEqual([
      {
        relationshipType: "domain_url_host",
        source: "evil.com",
        target: "https://evil.com/payload.exe",
        context: "URL host matches extracted domain 'evil.com' exactly.",
      },
    ]);
  });

  it("carries over the NOT_SCORED sentinel unchanged, never fabricating a real severity", () => {
    const notScored: GetInvestigationResult = {
      ...BASE_INVESTIGATION,
      risk_score: 0,
      severity: "NOT_SCORED",
      confidence: 0,
    };

    const result = normalizeInvestigationWorkspace(notScored, null, null);

    expect(result.severity).toBe("NOT_SCORED");
    expect(result.riskScore).toBe(0);
    expect(result.confidence).toBe(0);
  });

  it("normalizes all ten persisted IOC types when every one is present", () => {
    const iocs: IocsByType = Object.fromEntries(
      PERSISTED_IOC_TYPES.map((iocType, index) => [iocType, [`value-${index}`]]),
    ) as IocsByType;

    const result = normalizeInvestigationWorkspace(BASE_INVESTIGATION, iocs, null);

    expect(result.iocsByType).not.toBeNull();
    for (const iocType of PERSISTED_IOC_TYPES) {
      expect(result.iocsByType?.[iocType]).toEqual([
        { value: `value-${PERSISTED_IOC_TYPES.indexOf(iocType)}`, tiState: null, typedVerdict: null },
      ]);
    }
    expect(Object.keys(result.iocsByType ?? {}).sort()).toEqual([...PERSISTED_IOC_TYPES].sort());
  });

  it("keeps a present-but-empty IOC type as an empty array, not omitted", () => {
    const iocs: IocsByType = { ipv4: [] };

    const result = normalizeInvestigationWorkspace(BASE_INVESTIGATION, iocs, null);

    expect(result.iocsByType).toEqual({ ipv4: [] });
    expect(result.iocsByType).toHaveProperty("ipv4");
  });

  it("omits an IOC type entirely absent from the backend response, never synthesizing []", () => {
    const iocs: IocsByType = { ipv4: ["1.2.3.4"] };

    const result = normalizeInvestigationWorkspace(BASE_INVESTIGATION, iocs, null);

    expect(result.iocsByType).toEqual({ ipv4: [{ value: "1.2.3.4", tiState: null, typedVerdict: null }] });
    expect(result.iocsByType).not.toHaveProperty("domains");
    expect(Object.prototype.hasOwnProperty.call(result.iocsByType ?? {}, "domains")).toBe(false);
  });

  it("attaches every one of the six canonical TI states correctly", () => {
    const iocs: IocsByType = {
      ipv4: TI_STATES.map((_, i) => `1.2.3.${i}`),
    };
    const states: InvestigationIndicatorStates = {
      ipv4: Object.fromEntries(TI_STATES.map((state, i) => [`1.2.3.${i}`, state])),
    };
    const threatIntelligence: InvestigationWorkspaceThreatIntelligenceInput = {
      raw: {},
      states,
    };

    const result = normalizeInvestigationWorkspace(BASE_INVESTIGATION, iocs, threatIntelligence);

    for (const [i, state] of TI_STATES.entries()) {
      expect(result.iocsByType?.ipv4?.[i]).toEqual({ value: `1.2.3.${i}`, tiState: state, typedVerdict: null });
    }
  });

  it("marks an indicator with no matching states entry as null, not a fabricated state", () => {
    const iocs: IocsByType = { ipv4: ["9.9.9.9"] };
    const threatIntelligence: InvestigationWorkspaceThreatIntelligenceInput = {
      raw: {},
      states: { domains: { "other.example": "enriched" } },
    };

    const result = normalizeInvestigationWorkspace(BASE_INVESTIGATION, iocs, threatIntelligence);

    expect(result.iocsByType?.ipv4?.[0]).toEqual({ value: "9.9.9.9", tiState: null, typedVerdict: null });
  });

  it("treats an unsupported-type classification as data, reusing the backend's own value verbatim", () => {
    const iocs: IocsByType = { cves: ["CVE-2024-0001"] };
    const threatIntelligence: InvestigationWorkspaceThreatIntelligenceInput = {
      raw: {},
      states: { cves: { "CVE-2024-0001": "unsupported_type" } },
    };

    const result = normalizeInvestigationWorkspace(BASE_INVESTIGATION, iocs, threatIntelligence);

    expect(result.iocsByType?.cves).toEqual([{ value: "CVE-2024-0001", tiState: "unsupported_type", typedVerdict: null }]);
  });

  it("distinguishes missing IOC data (null) from a successful empty response ({})", () => {
    const missing = normalizeInvestigationWorkspace(BASE_INVESTIGATION, null, null);
    const empty = normalizeInvestigationWorkspace(BASE_INVESTIGATION, {}, null);

    expect(missing.iocsByType).toBeNull();
    expect(empty.iocsByType).toEqual({});
    expect(empty.iocsByType).not.toBeNull();
  });

  it("distinguishes missing threat-intelligence data (null) from a successful empty payload ({})", () => {
    const missing = normalizeInvestigationWorkspace(BASE_INVESTIGATION, null, null);
    const empty = normalizeInvestigationWorkspace(BASE_INVESTIGATION, null, { raw: {}, states: {} });

    expect(missing.rawThreatIntelligence).toBeNull();
    expect(empty.rawThreatIntelligence).toEqual({});
    expect(empty.rawThreatIntelligence).not.toBeNull();
  });

  it("preserves the raw threat_intelligence payload unchanged, including nested/opaque shapes", () => {
    const opaquePayload = {
      "1.2.3.4": { vendor: "vt", malicious: 3, opaque_nested: { a: [1, 2, { b: "c" }] } },
    };
    const threatIntelligence: InvestigationWorkspaceThreatIntelligenceInput = {
      raw: opaquePayload,
      states: {},
    };

    const result = normalizeInvestigationWorkspace(BASE_INVESTIGATION, null, threatIntelligence);

    expect(result.rawThreatIntelligence).toEqual(opaquePayload);
  });

  it("never fabricates a value: absent inputs normalize to null/absent, not invented defaults", () => {
    const result = normalizeInvestigationWorkspace(BASE_INVESTIGATION, null, null);

    expect(result.iocsByType).toBeNull();
    expect(result.rawThreatIntelligence).toBeNull();
  });

  it("is deterministic: normalizing the same input twice produces deeply-equal output", () => {
    const iocs: IocsByType = { ipv4: ["1.2.3.4"], sha256: ["a".repeat(64)] };
    const threatIntelligence: InvestigationWorkspaceThreatIntelligenceInput = {
      raw: { x: 1 },
      states: { ipv4: { "1.2.3.4": "enriched" } },
    };

    const first = normalizeInvestigationWorkspace(BASE_INVESTIGATION, iocs, threatIntelligence);
    const second = normalizeInvestigationWorkspace(BASE_INVESTIGATION, iocs, threatIntelligence);

    expect(first).toEqual(second);
  });

  it("handles a malformed/unexpected backend shape (states referencing an ioc type absent from iocs) without throwing", () => {
    const iocs: IocsByType = { ipv4: ["1.2.3.4"] };
    const threatIntelligence: InvestigationWorkspaceThreatIntelligenceInput = {
      raw: {},
      // `states` mentions a type/value pair with no corresponding entry
      // in `iocs` at all -- a shape the real backend should never
      // produce, but this module must not throw or silently invent an
      // IOC entry for it.
      states: { domains: { "ghost.example": "enriched" } },
    };

    expect(() =>
      normalizeInvestigationWorkspace(BASE_INVESTIGATION, iocs, threatIntelligence),
    ).not.toThrow();

    const result = normalizeInvestigationWorkspace(BASE_INVESTIGATION, iocs, threatIntelligence);
    expect(result.iocsByType).toEqual({
      ipv4: [{ value: "1.2.3.4", tiState: null, typedVerdict: null }],
    });
    expect(result.iocsByType).not.toHaveProperty("domains");
  });

  it("handles an investigation_id of null (mirrors InvestigationSummary's own nullability)", () => {
    const noId: GetInvestigationResult = { ...BASE_INVESTIGATION, investigation_id: null };

    const result = normalizeInvestigationWorkspace(noId, null, null);

    expect(result.investigationId).toBeNull();
  });
});

describe("normalizeInvestigationWorkspace — typed_verdicts (Phase 4K-2)", () => {
  it("passes typed_verdicts through, attached per-indicator alongside tiState", () => {
    const iocs: IocsByType = {
      ipv4: ["1.2.3.4"],
      domains: ["evil.example"],
    };
    const threatIntelligence: InvestigationWorkspaceThreatIntelligenceInput = {
      raw: {},
      states: {
        ipv4: { "1.2.3.4": "enriched" },
        domains: { "evil.example": "enriched" },
      },
      typedVerdicts: {
        ipv4: { "1.2.3.4": "malicious" },
        domains: { "evil.example": "clean" },
      },
    };

    const result = normalizeInvestigationWorkspace(BASE_INVESTIGATION, iocs, threatIntelligence);

    expect(result.iocsByType).toEqual({
      ipv4: [{ value: "1.2.3.4", tiState: "enriched", typedVerdict: "malicious" }],
      domains: [{ value: "evil.example", tiState: "enriched", typedVerdict: "clean" }],
    });
  });

  it("preserves CLEAN, never collapsing it into another value", () => {
    const iocs: IocsByType = { domains: ["safe.example"] };
    const threatIntelligence: InvestigationWorkspaceThreatIntelligenceInput = {
      raw: {},
      states: {},
      typedVerdicts: { domains: { "safe.example": "clean" } },
    };

    const result = normalizeInvestigationWorkspace(BASE_INVESTIGATION, iocs, threatIntelligence);

    expect(result.iocsByType?.domains?.[0]?.typedVerdict).toBe("clean");
  });

  it("preserves NOT_FOUND distinctly, never collapsing it into CLEAN", () => {
    const iocs: IocsByType = { ipv4: ["1.2.3.4"] };
    const threatIntelligence: InvestigationWorkspaceThreatIntelligenceInput = {
      raw: {},
      states: {},
      typedVerdicts: { ipv4: { "1.2.3.4": "not_found" } },
    };

    const result = normalizeInvestigationWorkspace(BASE_INVESTIGATION, iocs, threatIntelligence);

    expect(result.iocsByType?.ipv4?.[0]?.typedVerdict).toBe("not_found");
    expect(result.iocsByType?.ipv4?.[0]?.typedVerdict).not.toBe("clean");
  });

  it("preserves MALICIOUS", () => {
    const iocs: IocsByType = { urls: ["https://evil.example/payload"] };
    const threatIntelligence: InvestigationWorkspaceThreatIntelligenceInput = {
      raw: {},
      states: {},
      typedVerdicts: { urls: { "https://evil.example/payload": "malicious" } },
    };

    const result = normalizeInvestigationWorkspace(BASE_INVESTIGATION, iocs, threatIntelligence);

    expect(result.iocsByType?.urls?.[0]?.typedVerdict).toBe("malicious");
  });

  it("preserves SUSPICIOUS", () => {
    const iocs: IocsByType = { sha256: ["a".repeat(64)] };
    const threatIntelligence: InvestigationWorkspaceThreatIntelligenceInput = {
      raw: {},
      states: {},
      typedVerdicts: { sha256: { [`${"a".repeat(64)}`]: "suspicious" } },
    };

    const result = normalizeInvestigationWorkspace(BASE_INVESTIGATION, iocs, threatIntelligence);

    expect(result.iocsByType?.sha256?.[0]?.typedVerdict).toBe("suspicious");
  });

  it("preserves an explicit backend null as an unavailable verdict, not a fabricated value", () => {
    const iocs: IocsByType = { ipv4: ["1.2.3.4"] };
    const threatIntelligence: InvestigationWorkspaceThreatIntelligenceInput = {
      raw: {},
      states: {},
      typedVerdicts: { ipv4: { "1.2.3.4": null } },
    };

    const result = normalizeInvestigationWorkspace(BASE_INVESTIGATION, iocs, threatIntelligence);

    expect(result.iocsByType?.ipv4?.[0]?.typedVerdict).toBeNull();
  });

  it("does not crash when typed_verdicts is missing entirely from the threat-intelligence input", () => {
    const iocs: IocsByType = { ipv4: ["1.2.3.4"] };
    const threatIntelligence: InvestigationWorkspaceThreatIntelligenceInput = {
      raw: {},
      states: { ipv4: { "1.2.3.4": "enriched" } },
      // typedVerdicts intentionally omitted -- mirrors an older
      // backend response that predates the Phase 4K-1 field.
    };

    expect(() =>
      normalizeInvestigationWorkspace(BASE_INVESTIGATION, iocs, threatIntelligence),
    ).not.toThrow();

    const result = normalizeInvestigationWorkspace(BASE_INVESTIGATION, iocs, threatIntelligence);
    expect(result.iocsByType?.ipv4?.[0]).toEqual({
      value: "1.2.3.4",
      tiState: "enriched",
      typedVerdict: null,
    });
  });

  it("normalizes successfully when threatIntelligence itself is null (old-shape/no-fetch equivalent)", () => {
    const iocs: IocsByType = { ipv4: ["1.2.3.4"] };

    const result = normalizeInvestigationWorkspace(BASE_INVESTIGATION, iocs, null);

    expect(result.iocsByType?.ipv4?.[0]).toEqual({
      value: "1.2.3.4",
      tiState: null,
      typedVerdict: null,
    });
  });

  it("leaves TiState unchanged when typed_verdicts is present alongside it", () => {
    const iocs: IocsByType = { ipv4: ["1.2.3.4"] };
    const threatIntelligence: InvestigationWorkspaceThreatIntelligenceInput = {
      raw: {},
      states: { ipv4: { "1.2.3.4": "provider_error" } },
      typedVerdicts: { ipv4: { "1.2.3.4": "malicious" } },
    };

    const result = normalizeInvestigationWorkspace(BASE_INVESTIGATION, iocs, threatIntelligence);

    expect(result.iocsByType?.ipv4?.[0]?.tiState).toBe("provider_error");
    expect(result.iocsByType?.ipv4?.[0]?.typedVerdict).toBe("malicious");
  });

  it("leaves the raw threat_intelligence payload unchanged when typed_verdicts is present", () => {
    const rawPayload = { "1.2.3.4": { vendor: "vt", malicious: 3 } };
    const threatIntelligence: InvestigationWorkspaceThreatIntelligenceInput = {
      raw: rawPayload,
      states: {},
      typedVerdicts: { ipv4: { "1.2.3.4": "malicious" } },
    };

    const result = normalizeInvestigationWorkspace(BASE_INVESTIGATION, null, threatIntelligence);

    expect(result.rawThreatIntelligence).toEqual(rawPayload);
  });

  it("leaves existing IOC normalization (presence/absence/ordering) unchanged when typed_verdicts is present", () => {
    const iocs: IocsByType = { ipv4: ["1.2.3.4"], domains: [] };
    const threatIntelligence: InvestigationWorkspaceThreatIntelligenceInput = {
      raw: {},
      states: {},
      typedVerdicts: { ipv4: { "1.2.3.4": "clean" } },
    };

    const result = normalizeInvestigationWorkspace(BASE_INVESTIGATION, iocs, threatIntelligence);

    expect(result.iocsByType).toHaveProperty("domains");
    expect(result.iocsByType?.domains).toEqual([]);
    expect(result.iocsByType).not.toHaveProperty("urls");
  });

  it("supports independent verdicts across multiple IOC types simultaneously", () => {
    const iocs: IocsByType = {
      ipv4: ["1.2.3.4"],
      domains: ["example.com"],
      urls: ["https://example.com"],
    };
    const threatIntelligence: InvestigationWorkspaceThreatIntelligenceInput = {
      raw: {},
      states: {},
      typedVerdicts: {
        ipv4: { "1.2.3.4": "not_found" },
        domains: { "example.com": "clean" },
        urls: { "https://example.com": "malicious" },
      },
    };

    const result = normalizeInvestigationWorkspace(BASE_INVESTIGATION, iocs, threatIntelligence);

    expect(result.iocsByType?.ipv4?.[0]?.typedVerdict).toBe("not_found");
    expect(result.iocsByType?.domains?.[0]?.typedVerdict).toBe("clean");
    expect(result.iocsByType?.urls?.[0]?.typedVerdict).toBe("malicious");
  });

  it("never infers a typed verdict from tiState — different indicators can disagree", () => {
    const iocs: IocsByType = { ipv4: ["1.2.3.4"] };
    const threatIntelligence: InvestigationWorkspaceThreatIntelligenceInput = {
      raw: {},
      // TiState says "enriched" (the lookup succeeded), but no typed
      // verdict was supplied for it -- the normalizer must not infer
      // CLEAN, MALICIOUS, or anything else from a successful TiState.
      states: { ipv4: { "1.2.3.4": "enriched" } },
      typedVerdicts: {},
    };

    const result = normalizeInvestigationWorkspace(BASE_INVESTIGATION, iocs, threatIntelligence);

    expect(result.iocsByType?.ipv4?.[0]?.tiState).toBe("enriched");
    expect(result.iocsByType?.ipv4?.[0]?.typedVerdict).toBeNull();
  });

  it("never infers a typed verdict from a legacy raw display string", () => {
    const iocs: IocsByType = { ipv4: ["1.2.3.4"] };
    const threatIntelligence: InvestigationWorkspaceThreatIntelligenceInput = {
      // A legacy raw payload with a "Clean" display string, and no
      // typed_verdicts entry for this indicator at all -- the
      // normalizer must not parse `raw` to fabricate a verdict.
      raw: { "1.2.3.4": { verdict: "Clean" } },
      states: {},
      typedVerdicts: {},
    };

    const result = normalizeInvestigationWorkspace(BASE_INVESTIGATION, iocs, threatIntelligence);

    expect(result.iocsByType?.ipv4?.[0]?.typedVerdict).toBeNull();
  });

  it("old response shape (no typedVerdicts key at all) still normalizes successfully end-to-end", () => {
    const iocs: IocsByType = {
      ipv4: ["1.2.3.4"],
      domains: ["evil.example"],
    };
    const threatIntelligence = {
      raw: { "1.2.3.4": { vendor: "vt", malicious: 3 } },
      states: { ipv4: { "1.2.3.4": "enriched" } },
    } as InvestigationWorkspaceThreatIntelligenceInput;

    const result = normalizeInvestigationWorkspace(BASE_INVESTIGATION, iocs, threatIntelligence);

    expect(result.iocsByType).toEqual({
      ipv4: [{ value: "1.2.3.4", tiState: "enriched", typedVerdict: null }],
      domains: [{ value: "evil.example", tiState: null, typedVerdict: null }],
    });
    expect(result.rawThreatIntelligence).toEqual({ "1.2.3.4": { vendor: "vt", malicious: 3 } });
  });
});

describe("normalizeInvestigationWorkspace — timeline (A4-P2-P3 Part 5B)", () => {
  const EVENT_1: TimelineEvent = {
    event_id: "evt-1",
    investigation_id: 7,
    event_type: "analysis_started",
    timestamp: "2026-08-26T00:00:00",
    source: "analyzer",
    summary: "Analysis started",
    metadata: {},
    semantics: "lifecycle",
  };
  const EVENT_2: TimelineEvent = {
    event_id: "evt-2",
    investigation_id: 7,
    event_type: "analysis_completed",
    timestamp: "2026-08-26T00:05:00",
    source: "analyzer",
    summary: "Analysis completed",
    metadata: { duration_seconds: 300 },
    semantics: "lifecycle",
  };

  it("defaults to null when no timeline argument is passed, preserving existing three-argument call sites", () => {
    const result = normalizeInvestigationWorkspace(BASE_INVESTIGATION, null, null);

    expect(result.timeline).toBeNull();
  });

  it("normalizes timeline = null as unavailable/missing, distinct from an empty timeline", () => {
    const result = normalizeInvestigationWorkspace(BASE_INVESTIGATION, null, null, null);

    expect(result.timeline).toBeNull();
  });

  it("normalizes timeline = [] as genuinely empty, not missing", () => {
    const result = normalizeInvestigationWorkspace(BASE_INVESTIGATION, null, null, []);

    expect(result.timeline).toEqual([]);
    expect(result.timeline).not.toBeNull();
  });

  it("normalizes a populated timeline, field-renaming to camelCase without fabricating or dropping data", () => {
    const result = normalizeInvestigationWorkspace(BASE_INVESTIGATION, null, null, [EVENT_1, EVENT_2]);

    expect(result.timeline).toEqual([
      {
        eventId: "evt-1",
        investigationId: 7,
        eventType: "analysis_started",
        timestamp: "2026-08-26T00:00:00",
        source: "analyzer",
        summary: "Analysis started",
        metadata: {},
        semantics: "lifecycle",
      },
      {
        eventId: "evt-2",
        investigationId: 7,
        eventType: "analysis_completed",
        timestamp: "2026-08-26T00:05:00",
        source: "analyzer",
        summary: "Analysis completed",
        metadata: { duration_seconds: 300 },
        semantics: "lifecycle",
      },
    ]);
  });

  it("preserves the backend's own event ordering exactly, never re-sorting", () => {
    // EVENT_2 is chronologically later than EVENT_1 -- pass it first to
    // prove this module doesn't sort by timestamp (or anything else).
    const result = normalizeInvestigationWorkspace(BASE_INVESTIGATION, null, null, [EVENT_2, EVENT_1]);

    expect(result.timeline?.map((event) => event.eventId)).toEqual(["evt-2", "evt-1"]);
  });

  it("never fabricates, drops, or reorders event fields", () => {
    const result = normalizeInvestigationWorkspace(BASE_INVESTIGATION, null, null, [EVENT_1]);

    expect(result.timeline?.[0]).toEqual({
      eventId: EVENT_1.event_id,
      investigationId: EVENT_1.investigation_id,
      eventType: EVENT_1.event_type,
      timestamp: EVENT_1.timestamp,
      source: EVENT_1.source,
      summary: EVENT_1.summary,
      metadata: EVENT_1.metadata,
      semantics: EVENT_1.semantics,
    });
  });

  it("leaves iocsByType/rawThreatIntelligence/correlations normalization unchanged when a timeline is present", () => {
    const iocs: IocsByType = { ipv4: ["1.2.3.4"] };
    const threatIntelligence: InvestigationWorkspaceThreatIntelligenceInput = {
      raw: { "1.2.3.4": { vendor: "vt" } },
      states: { ipv4: { "1.2.3.4": "enriched" } },
    };

    const result = normalizeInvestigationWorkspace(BASE_INVESTIGATION, iocs, threatIntelligence, [EVENT_1]);

    expect(result.iocsByType).toEqual({
      ipv4: [{ value: "1.2.3.4", tiState: "enriched", typedVerdict: null }],
    });
    expect(result.rawThreatIntelligence).toEqual({ "1.2.3.4": { vendor: "vt" } });
    expect(result.correlations).toEqual([]);
    expect(result.timeline).toHaveLength(1);
  });

  it("is deterministic: normalizing the same timeline input twice produces deeply-equal output", () => {
    const first = normalizeInvestigationWorkspace(BASE_INVESTIGATION, null, null, [EVENT_1, EVENT_2]);
    const second = normalizeInvestigationWorkspace(BASE_INVESTIGATION, null, null, [EVENT_1, EVENT_2]);

    expect(first.timeline).toEqual(second.timeline);
  });
});

describe("normalizeInvestigationWorkspace — risk explanation (PD-08-P2)", () => {
  const RISK_EXPLANATION: GetInvestigationRiskExplanationResult = {
    investigation_id: 7,
    report_name: "report.txt",
    score: 42,
    severity: "high",
    confidence: 0.9,
    ioc_score: 30,
    threat_intel_score: 10,
    cve_score: 2,
    ioc_categories: [
      {
        ioc_type: "ipv4",
        ioc_type_title: "IP Addresses",
        count: 1,
        weight: 30,
        significance: "high",
        points: 30,
      },
      {
        ioc_type: "domains",
        ioc_type_title: "Domains",
        count: 0,
        weight: 20,
        significance: "medium",
        points: 0,
      },
    ],
    ioc_breakdown_verified: true,
    threat_intel_state: "enriched",
    threat_intel_message: "Threat intelligence was checked for available indicators.",
    threat_intel_short_label: "Enriched",
    threat_intel_requested: 1,
    threat_intel_succeeded: 1,
    threat_intel_malicious_hash_count: 0,
    threat_intel_suspicious_hash_count: 0,
    correlation_evaluated: true,
    correlation_relationship_count: 0,
    correlation_summary: "No explicit correlations were found.",
    engine_reasons: ["IOC score contributed 30 points."],
    narrative: ["This investigation scored 42 (high) based on 1 IP address indicator."],
    warnings: [],
  };

  it("defaults to null when no riskExplanation argument is passed, preserving existing call sites", () => {
    const result = normalizeInvestigationWorkspace(BASE_INVESTIGATION, null, null);

    expect(result.riskExplanation).toBeNull();
  });

  it("normalizes riskExplanation = null as unavailable/missing", () => {
    const result = normalizeInvestigationWorkspace(BASE_INVESTIGATION, null, null, null, null);

    expect(result.riskExplanation).toBeNull();
  });

  it("normalizes a populated risk explanation field-for-field, without fabricating or dropping data", () => {
    const result = normalizeInvestigationWorkspace(BASE_INVESTIGATION, null, null, null, RISK_EXPLANATION);

    expect(result.riskExplanation).toEqual({
      investigationId: 7,
      reportName: "report.txt",
      score: 42,
      severity: "high",
      confidence: 0.9,
      iocScore: 30,
      threatIntelScore: 10,
      cveScore: 2,
      iocCategories: [
        {
          iocType: "ipv4",
          iocTypeTitle: "IP Addresses",
          count: 1,
          weight: 30,
          significance: "high",
          points: 30,
        },
        {
          iocType: "domains",
          iocTypeTitle: "Domains",
          count: 0,
          weight: 20,
          significance: "medium",
          points: 0,
        },
      ],
      iocBreakdownVerified: true,
      threatIntelState: "enriched",
      threatIntelMessage: "Threat intelligence was checked for available indicators.",
      threatIntelShortLabel: "Enriched",
      threatIntelRequested: 1,
      threatIntelSucceeded: 1,
      threatIntelMaliciousHashCount: 0,
      threatIntelSuspiciousHashCount: 0,
      correlationEvaluated: true,
      correlationRelationshipCount: 0,
      correlationSummary: "No explicit correlations were found.",
      engineReasons: ["IOC score contributed 30 points."],
      narrative: ["This investigation scored 42 (high) based on 1 IP address indicator."],
      warnings: [],
    });
  });

  it("preserves the backend's own ioc_categories ordering exactly, never re-sorting or recomputing", () => {
    const result = normalizeInvestigationWorkspace(BASE_INVESTIGATION, null, null, null, RISK_EXPLANATION);

    expect(result.riskExplanation?.iocCategories.map((category) => category.iocType)).toEqual([
      "ipv4",
      "domains",
    ]);
  });

  it("carries an unverified breakdown flag through unchanged, never upgrading it to verified", () => {
    const unverified: GetInvestigationRiskExplanationResult = {
      ...RISK_EXPLANATION,
      ioc_breakdown_verified: false,
    };
    const result = normalizeInvestigationWorkspace(BASE_INVESTIGATION, null, null, null, unverified);

    expect(result.riskExplanation?.iocBreakdownVerified).toBe(false);
  });

  it("carries narrative and warnings through verbatim, in order, without reinterpretation", () => {
    const withWarnings: GetInvestigationRiskExplanationResult = {
      ...RISK_EXPLANATION,
      narrative: ["Line one.", "Line two."],
      warnings: ["Threat intelligence coverage was incomplete."],
    };
    const result = normalizeInvestigationWorkspace(BASE_INVESTIGATION, null, null, null, withWarnings);

    expect(result.riskExplanation?.narrative).toEqual(["Line one.", "Line two."]);
    expect(result.riskExplanation?.warnings).toEqual([
      "Threat intelligence coverage was incomplete.",
    ]);
  });

  it("leaves iocsByType/rawThreatIntelligence/correlations/timeline normalization unchanged when a risk explanation is present", () => {
    const iocs: IocsByType = { ipv4: ["1.2.3.4"] };
    const threatIntelligence: InvestigationWorkspaceThreatIntelligenceInput = {
      raw: { "1.2.3.4": { vendor: "vt" } },
      states: { ipv4: { "1.2.3.4": "enriched" } },
    };

    const result = normalizeInvestigationWorkspace(
      BASE_INVESTIGATION,
      iocs,
      threatIntelligence,
      null,
      RISK_EXPLANATION,
    );

    expect(result.iocsByType).toEqual({
      ipv4: [{ value: "1.2.3.4", tiState: "enriched", typedVerdict: null }],
    });
    expect(result.rawThreatIntelligence).toEqual({ "1.2.3.4": { vendor: "vt" } });
    expect(result.correlations).toEqual([]);
    expect(result.timeline).toBeNull();
    expect(result.riskExplanation).not.toBeNull();
  });

  it("is deterministic: normalizing the same risk explanation input twice produces deeply-equal output", () => {
    const first = normalizeInvestigationWorkspace(BASE_INVESTIGATION, null, null, null, RISK_EXPLANATION);
    const second = normalizeInvestigationWorkspace(BASE_INVESTIGATION, null, null, null, RISK_EXPLANATION);

    expect(first.riskExplanation).toEqual(second.riskExplanation);
  });
});

describe("normalizeInvestigationWorkspace — IOC significance (PD-08-P4.1)", () => {
  const IOC_SIGNIFICANCE: IocSignificanceByType = {
    ipv4: { weight: 8, significance: "High" },
    domains: { weight: 3, significance: "Medium" },
    emails: { weight: 0, significance: "Informational" },
  };

  it("defaults to null when no iocSignificance argument is passed, preserving existing call sites", () => {
    const result = normalizeInvestigationWorkspace(BASE_INVESTIGATION, null, null);

    expect(result.iocSignificance).toBeNull();
  });

  it("normalizes iocSignificance = null as unavailable/missing, distinct from a real empty object", () => {
    const result = normalizeInvestigationWorkspace(BASE_INVESTIGATION, null, null, null, null, null);

    expect(result.iocSignificance).toBeNull();
  });

  it("carries a real significance map through unchanged, field-for-field, without fabricating or dropping entries", () => {
    const result = normalizeInvestigationWorkspace(
      BASE_INVESTIGATION,
      null,
      null,
      null,
      null,
      IOC_SIGNIFICANCE,
    );

    expect(result.iocSignificance).toEqual({
      ipv4: { weight: 8, significance: "High" },
      domains: { weight: 3, significance: "Medium" },
      emails: { weight: 0, significance: "Informational" },
    });
  });

  it("keeps a genuinely empty significance object ({}) distinct from missing (null)", () => {
    const result = normalizeInvestigationWorkspace(BASE_INVESTIGATION, null, null, null, null, {});

    expect(result.iocSignificance).toEqual({});
    expect(result.iocSignificance).not.toBeNull();
  });

  it("keeps each category's weight/significance associated with its own real ioc_type, never mixed across types", () => {
    const result = normalizeInvestigationWorkspace(
      BASE_INVESTIGATION,
      null,
      null,
      null,
      null,
      IOC_SIGNIFICANCE,
    );

    expect(result.iocSignificance?.ipv4).toEqual({ weight: 8, significance: "High" });
    expect(result.iocSignificance?.domains).toEqual({ weight: 3, significance: "Medium" });
    expect(result.iocSignificance?.emails).toEqual({ weight: 0, significance: "Informational" });
    // A category absent from the backend's significance map stays
    // absent here too -- never synthesized as a fabricated
    // "Informational"/weight-0 default (that fallback is the backend's
    // own job, `ioc_type_significance()` -- see that function's
    // docstring, `app/services/ioc_significance.py`).
    expect(result.iocSignificance?.sha256).toBeUndefined();
  });

  it("leaves iocsByType/rawThreatIntelligence/correlations/timeline/riskExplanation normalization unchanged when iocSignificance is present", () => {
    const iocs: IocsByType = { ipv4: ["1.2.3.4"] };
    const threatIntelligence: InvestigationWorkspaceThreatIntelligenceInput = {
      raw: { "1.2.3.4": { vendor: "vt" } },
      states: { ipv4: { "1.2.3.4": "enriched" } },
    };

    const result = normalizeInvestigationWorkspace(
      BASE_INVESTIGATION,
      iocs,
      threatIntelligence,
      null,
      null,
      IOC_SIGNIFICANCE,
    );

    expect(result.iocsByType).toEqual({
      ipv4: [{ value: "1.2.3.4", tiState: "enriched", typedVerdict: null }],
    });
    expect(result.rawThreatIntelligence).toEqual({ "1.2.3.4": { vendor: "vt" } });
    expect(result.correlations).toEqual([]);
    expect(result.timeline).toBeNull();
    expect(result.riskExplanation).toBeNull();
    expect(result.iocSignificance).not.toBeNull();
  });

  it("is deterministic: normalizing the same significance input twice produces deeply-equal output", () => {
    const first = normalizeInvestigationWorkspace(
      BASE_INVESTIGATION,
      null,
      null,
      null,
      null,
      IOC_SIGNIFICANCE,
    );
    const second = normalizeInvestigationWorkspace(
      BASE_INVESTIGATION,
      null,
      null,
      null,
      null,
      IOC_SIGNIFICANCE,
    );

    expect(first.iocSignificance).toEqual(second.iocSignificance);
  });
});
