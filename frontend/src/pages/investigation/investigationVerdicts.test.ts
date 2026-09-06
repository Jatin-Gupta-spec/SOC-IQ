/**
 * `countTypedVerdicts()` / `listIndicatorVerdicts()` tests --
 * Phase 4K-3 (rewritten from the original Phase 4K Part 1/2 legacy
 * raw-payload-based `countVerdicts()`/`matchIndicatorVerdicts()`
 * tests -- see `investigationVerdicts.ts`'s own doc comment for why).
 */

import { describe, expect, it } from "vitest";
import { countTypedVerdicts, listIndicatorVerdicts } from "./investigationVerdicts";
import type { InvestigationWorkspaceIndicator, InvestigationWorkspaceIocsByType } from "./investigationWorkspaceModel";
import type { TypedVerdict } from "../../shared/api/types";

function indicator(value: string, typedVerdict: TypedVerdict | null): InvestigationWorkspaceIndicator {
  return { value, tiState: "enriched", typedVerdict };
}

describe("countTypedVerdicts", () => {
  it("returns null when there is no per-indicator breakdown at all", () => {
    expect(countTypedVerdicts(null)).toBeNull();
  });

  it("returns an honest zero-total result for an empty real breakdown", () => {
    expect(countTypedVerdicts({})).toEqual({ groups: [], total: 0 });
  });

  it("counts real typedVerdict values across every IOC type", () => {
    const iocsByType: InvestigationWorkspaceIocsByType = {
      sha256: [indicator("a", "malicious"), indicator("b", "clean")],
      ipv4: [indicator("1.2.3.4", "not_found")],
      domains: [indicator("example.com", "suspicious")],
      urls: [indicator("https://example.com", "clean")],
    };

    const result = countTypedVerdicts(iocsByType);

    expect(result).not.toBeNull();
    expect(result?.total).toBe(5);
    expect(result?.groups).toEqual([
      { verdict: "malicious", count: 1 },
      { verdict: "suspicious", count: 1 },
      { verdict: "clean", count: 2 },
      { verdict: "not_found", count: 1 },
    ]);
  });

  it("keeps 'not_found' a distinct, never-merged-into-'clean' bucket", () => {
    const iocsByType: InvestigationWorkspaceIocsByType = {
      sha256: [indicator("a", "not_found"), indicator("b", "not_found"), indicator("c", "clean")],
    };

    const result = countTypedVerdicts(iocsByType);

    expect(result?.groups).toEqual([
      { verdict: "clean", count: 1 },
      { verdict: "not_found", count: 2 },
    ]);
  });

  it("skips an indicator with typedVerdict: null, never counting it as any real verdict", () => {
    const iocsByType: InvestigationWorkspaceIocsByType = {
      sha256: [indicator("a", null), indicator("b", null)],
    };

    const result = countTypedVerdicts(iocsByType);

    expect(result?.groups).toEqual([]);
    expect(result?.total).toBe(0);
  });

  it("ignores IOC types with no indicators without throwing", () => {
    const iocsByType: InvestigationWorkspaceIocsByType = { ipv4: [indicator("1.2.3.4", "clean")] };

    expect(() => countTypedVerdicts(iocsByType)).not.toThrow();
    const result = countTypedVerdicts(iocsByType);
    expect(result?.total).toBe(1);
    expect(result?.groups).toEqual([{ verdict: "clean", count: 1 }]);
  });
});

describe("listIndicatorVerdicts", () => {
  it("returns null when there is no per-indicator breakdown at all", () => {
    expect(listIndicatorVerdicts(null)).toBeNull();
  });

  it("returns an empty array, not null, when there is real data but nothing classified", () => {
    expect(listIndicatorVerdicts({})).toEqual([]);
  });

  it("lists a real typedVerdict for every indicator that carries one", () => {
    const iocsByType: InvestigationWorkspaceIocsByType = {
      sha256: [indicator("abc123", "malicious")],
      ipv4: [indicator("1.2.3.4", "clean")],
      domains: [indicator("evil.example", "not_found")],
      urls: [indicator("https://bad.example", "suspicious")],
    };

    const result = listIndicatorVerdicts(iocsByType);

    // Expected in PERSISTED_IOC_TYPES' canonical order (ipv4, domains,
    // urls, ..., sha256, ...), not the fixture's object-literal
    // insertion order -- `listIndicatorVerdicts()` intentionally
    // iterates PERSISTED_IOC_TYPES, the same canonical order
    // `countTypedVerdicts()` and every other per-type traversal in
    // this module already uses, so a caller's key-declaration order
    // never affects the result.
    expect(result).toEqual([
      { type: "ipv4", value: "1.2.3.4", verdict: "clean" },
      { type: "domains", value: "evil.example", verdict: "not_found" },
      { type: "urls", value: "https://bad.example", verdict: "suspicious" },
      { type: "sha256", value: "abc123", verdict: "malicious" },
    ]);
  });

  it("omits an indicator with typedVerdict: null, never inventing a verdict for it", () => {
    const iocsByType: InvestigationWorkspaceIocsByType = {
      sha256: [indicator("known", "clean"), indicator("unclassified", null)],
    };

    const result = listIndicatorVerdicts(iocsByType);

    expect(result).toEqual([{ type: "sha256", value: "known", verdict: "clean" }]);
  });

  it("includes any IOC type that carries a real typedVerdict, not just the four TI-enriched categories", () => {
    // Unlike the old raw-payload identity-matching approach, this is a
    // direct field read -- it has no reason to special-case which IOC
    // types the legacy TI pipeline happened to enrich.
    const iocsByType: InvestigationWorkspaceIocsByType = {
      emails: [indicator("a@b.com", null)],
      cves: [indicator("CVE-2024-0001", null)],
    };

    const result = listIndicatorVerdicts(iocsByType);

    expect(result).toEqual([]);
  });
});
