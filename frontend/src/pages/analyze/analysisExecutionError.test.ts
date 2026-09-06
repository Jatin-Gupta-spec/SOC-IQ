import { describe, expect, it } from "vitest";

import {
  CommandFailedError,
  CommandHttpError,
  CommandMalformedResponseError,
  CommandNetworkError,
  SidecarNotConnectedError,
} from "../../shared/api/client";
import { describeExecutionError, mapExecutionError } from "./analysisExecutionError";

describe("mapExecutionError", () => {
  it("maps REPORT_NOT_FOUND to invalid_input", () => {
    const error = new CommandFailedError("analyze_report", "REPORT_NOT_FOUND", "No report at /tmp/x.txt.");
    const mapped = mapExecutionError(error);
    expect(mapped.kind).toBe("invalid_input");
    expect(mapped.code).toBe("REPORT_NOT_FOUND");
  });

  it("maps INVALID_COMMAND_PAYLOAD to invalid_input", () => {
    const error = new CommandFailedError("analyze_report", "INVALID_COMMAND_PAYLOAD", "report_path must be a non-empty string.");
    expect(mapExecutionError(error).kind).toBe("invalid_input");
  });

  it("maps any other backend error code to application_failure", () => {
    const error = new CommandFailedError("analyze_report", "DATABASE_ERROR", "connection refused");
    const mapped = mapExecutionError(error);
    expect(mapped.kind).toBe("application_failure");
    expect(mapped.code).toBe("DATABASE_ERROR");
  });

  it("maps SidecarNotConnectedError to sidecar_unavailable", () => {
    const error = new SidecarNotConnectedError("not running in Tauri");
    expect(mapExecutionError(error).kind).toBe("sidecar_unavailable");
  });

  it("maps CommandNetworkError to network_failure", () => {
    const error = new CommandNetworkError("analyze_report", new TypeError("Failed to fetch"));
    expect(mapExecutionError(error).kind).toBe("network_failure");
  });

  it("maps CommandHttpError to network_failure", () => {
    const error = new CommandHttpError("analyze_report", 502, "Bad Gateway");
    expect(mapExecutionError(error).kind).toBe("network_failure");
  });

  it("maps CommandMalformedResponseError to unexpected", () => {
    const error = new CommandMalformedResponseError("analyze_report", "not JSON");
    expect(mapExecutionError(error).kind).toBe("unexpected");
  });

  it("maps a non-Error thrown value to unexpected, without throwing itself", () => {
    const mapped = mapExecutionError("some unexpected string");
    expect(mapped.kind).toBe("unexpected");
    expect(mapped.cause).toBe("some unexpected string");
  });

  it("never exposes the raw backend message in the user-facing message", () => {
    const error = new CommandFailedError(
      "analyze_report",
      "DATABASE_ERROR",
      "Traceback (most recent call last): sqlite3.OperationalError: database is locked at /home/user/.soc-iq/db.sqlite",
    );
    const mapped = mapExecutionError(error);
    expect(mapped.message).not.toContain("Traceback");
    expect(mapped.message).not.toContain("sqlite3");
    expect(mapped.message).not.toContain(".sqlite");
  });

  it("preserves the original error only on cause, for diagnostics", () => {
    const error = new CommandFailedError("analyze_report", "REPORT_NOT_FOUND", "gone");
    const mapped = mapExecutionError(error);
    expect(mapped.cause).toBe(error);
  });
});

describe("describeExecutionError", () => {
  it("returns a distinct, non-empty message for every error kind", () => {
    const kinds = ["invalid_input", "sidecar_unavailable", "application_failure", "network_failure", "unexpected"] as const;
    const messages = kinds.map((kind) => describeExecutionError({ kind }));
    expect(new Set(messages).size).toBe(kinds.length);
    messages.forEach((message) => expect(message.length).toBeGreaterThan(0));
  });
});
