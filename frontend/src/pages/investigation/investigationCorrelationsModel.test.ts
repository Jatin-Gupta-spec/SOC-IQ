/**
 * `deriveInvestigationCorrelations` tests — Phase 4J-6 Part 4A.
 */

import { describe, expect, it } from "vitest";

import { deriveInvestigationCorrelations, type InvestigationCorrelation } from "./investigationCorrelationsModel";
import type { InvestigationWorkspaceData } from "./investigationWorkspaceModel";

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

describe("deriveInvestigationCorrelations", () => {
  describe("unavailable", () => {
    it("reports unavailable when both IOC and TI data failed to load", () => {
      const result = deriveInvestigationCorrelations(makeData({ iocsByType: null, rawThreatIntelligence: null }));

      expect(result.status).toBe("unavailable");
    });

    it("does not report unavailable when only IOC data failed but TI data is present", () => {
      const result = deriveInvestigationCorrelations(makeData({ iocsByType: null, rawThreatIntelligence: {} }));

      expect(result.status).not.toBe("unavailable");
    });

    it("does not report unavailable when only TI data failed but IOC data is present", () => {
      const result = deriveInvestigationCorrelations(
        makeData({ iocsByType: { ipv4: [{ value: "1.2.3.4", tiState: null, typedVerdict: null }] }, rawThreatIntelligence: null }),
      );

      expect(result.status).not.toBe("unavailable");
    });
  });

  describe("empty", () => {
    it("reports empty when real data is present but carries no explicit relationship", () => {
      const result = deriveInvestigationCorrelations(
        makeData({
          iocsByType: {
            ipv4: [{ value: "1.2.3.4", tiState: "enriched", typedVerdict: null }],
            domains: [{ value: "evil.example", tiState: "enriched", typedVerdict: null }],
          },
          rawThreatIntelligence: { "1.2.3.4": { vendor: "vt", malicious: 3 } },
        }),
      );

      expect(result.status).toBe("empty");
    });

    it("reports empty rather than unavailable when IOC data is a real, empty object", () => {
      const result = deriveInvestigationCorrelations(makeData({ iocsByType: {}, rawThreatIntelligence: {} }));

      expect(result.status).toBe("empty");
    });

    it("never fabricates a relationship from two IOCs sharing the same type", () => {
      const result = deriveInvestigationCorrelations(
        makeData({
          iocsByType: {
            ipv4: [
              { value: "1.1.1.1", tiState: "enriched", typedVerdict: null },
              { value: "2.2.2.2", tiState: "enriched", typedVerdict: null },
            ],
          },
        }),
      );

      expect(result.status).toBe("empty");
      if (result.status === "available") {
        throw new Error("unreachable");
      }
    });
  });

  describe("available", () => {
    it("reports available with the real relationships when data.correlations is populated (Phase 4J-6)", () => {
      const correlation: InvestigationCorrelation = {
        relationshipType: "domain_url_host",
        source: "evil.com",
        target: "https://evil.com/payload.exe",
        context: "URL host matches extracted domain 'evil.com' exactly.",
      };

      const result = deriveInvestigationCorrelations(
        makeData({
          iocsByType: { domains: [{ value: "evil.com", tiState: null, typedVerdict: null }] },
          correlations: [correlation],
        }),
      );

      expect(result.status).toBe("available");
      if (result.status === "available") {
        expect(result.correlations).toEqual([correlation]);
      }
    });

    it("still reports empty, not available, when correlations is a real but empty array", () => {
      const result = deriveInvestigationCorrelations(makeData({ correlations: [] }));

      expect(result.status).toBe("empty");
    });
  });

  describe("no fabrication", () => {
    it("never infers a relationship from rawThreatIntelligence contents, even when data.correlations is empty", () => {
      const result = deriveInvestigationCorrelations(
        makeData({
          iocsByType: {
            ipv4: [{ value: "1.2.3.4", tiState: "enriched", typedVerdict: null }],
            sha256: [{ value: "aa".repeat(32), tiState: "enriched", typedVerdict: null }],
          },
          rawThreatIntelligence: { "1.2.3.4": { relatedHash: "aa".repeat(32) } },
        }),
      );

      // Even though the raw payload above happens to contain a value
      // that *looks* related, `rawThreatIntelligence` is deliberately
      // opaque (see `ProviderDetail.tsx`) and this module never reads
      // provider-specific fields out of it -- so the result must stay
      // "empty", not "available" with a guessed relationship.
      expect(result.status).toBe("empty");
    });
  });
});
