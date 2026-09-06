/**
 * `parseInvestigationId()` tests (Phase 4J-3, scope step 9).
 *
 * Covers every case step 6 of the phase scope enumerates, plus the
 * project's chosen contract for leading/trailing whitespace: rejected
 * outright, not trimmed-then-parsed (see `investigationRouteParams.ts`'s
 * own doc comment on why this parser is deliberately strict).
 */

import { describe, expect, it } from "vitest";
import { parseInvestigationId } from "./investigationRouteParams";

describe("parseInvestigationId", () => {
  it("accepts a valid positive integer", () => {
    expect(parseInvestigationId("123")).toEqual({
      valid: true,
      investigationId: 123,
    });
  });

  it("accepts a single-digit positive integer", () => {
    expect(parseInvestigationId("1")).toEqual({
      valid: true,
      investigationId: 1,
    });
  });

  it("rejects a missing parameter", () => {
    expect(parseInvestigationId(undefined)).toEqual({ valid: false });
  });

  it("rejects an empty string", () => {
    expect(parseInvestigationId("")).toEqual({ valid: false });
  });

  it("rejects a whitespace-only string", () => {
    expect(parseInvestigationId("   ")).toEqual({ valid: false });
  });

  it("rejects a value with leading whitespace around otherwise-valid digits", () => {
    expect(parseInvestigationId(" 123")).toEqual({ valid: false });
  });

  it("rejects a value with trailing whitespace around otherwise-valid digits", () => {
    expect(parseInvestigationId("123 ")).toEqual({ valid: false });
  });

  it("rejects non-numeric content", () => {
    expect(parseInvestigationId("abc")).toEqual({ valid: false });
  });

  it("rejects a malformed mixed string with a trailing non-digit", () => {
    expect(parseInvestigationId("12abc")).toEqual({ valid: false });
  });

  it("rejects a malformed mixed string with a leading non-digit", () => {
    expect(parseInvestigationId("abc12")).toEqual({ valid: false });
  });

  it("rejects a decimal value", () => {
    expect(parseInvestigationId("1.5")).toEqual({ valid: false });
  });

  it("rejects a negative value", () => {
    expect(parseInvestigationId("-1")).toEqual({ valid: false });
  });

  it("rejects zero", () => {
    expect(parseInvestigationId("0")).toEqual({ valid: false });
  });

  it("rejects a value outside the JavaScript safe integer range", () => {
    expect(parseInvestigationId("9007199254740992")).toEqual({
      valid: false,
    });
  });

  it("rejects an extremely large digit string", () => {
    expect(parseInvestigationId("99999999999999999999")).toEqual({
      valid: false,
    });
  });

  it("rejects a leading-plus-sign value", () => {
    expect(parseInvestigationId("+123")).toEqual({ valid: false });
  });
});
