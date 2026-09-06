/**
 * Focused tests for the Phase 4E-P1 typed command client.
 *
 * Mocks `@tauri-apps/api/core` (origin resolution) and the global
 * `fetch` (HTTP transport) -- no live sidecar or Tauri runtime is
 * needed, per `PHASE4E_ARCHITECTURE.md` §10's "unit tests mocking
 * fetch/origin resolution; no new backend test needed" requirement.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const invokeMock = vi.fn();
const isTauriMock = vi.fn();

vi.mock("@tauri-apps/api/core", () => ({
  invoke: (...args: unknown[]) => invokeMock(...args),
  isTauri: () => isTauriMock(),
}));

import {
  CommandFailedError,
  CommandHttpError,
  CommandMalformedResponseError,
  CommandNetworkError,
  KeystoreWriteError,
  SidecarStatusUnavailableError,
  getSidecarStatus,
  runCommand,
  setVirustotalApiKey,
} from "./client";
import type { SidecarStatus } from "../sidecar/types";

const ORIGIN = "http://127.0.0.1:54213";

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  });
}

describe("runCommand", () => {
  beforeEach(() => {
    invokeMock.mockReset().mockResolvedValue(ORIGIN);
    isTauriMock.mockReset().mockReturnValue(true);
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("resolves the sidecar origin through getSidecarOrigin() (invoke), never a hardcoded port", async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse({ success: true, data: { status: "ok" }, error: null }),
    );

    await runCommand("list_investigations", {});

    expect(invokeMock).toHaveBeenCalledWith("get_sidecar_origin");
    expect(vi.mocked(fetch)).toHaveBeenCalledWith(
      `${ORIGIN}/commands/list_investigations`,
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("constructs the command request and serializes the payload as JSON", async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse({
        success: true,
        data: { investigation_id: 1, report_name: "r", risk_score: 1, severity: "low", confidence: 1, status: "done", analyzed_at: "now" },
        error: null,
      }),
    );

    await runCommand("get_investigation", { investigation_id: 1 });

    const [, init] = vi.mocked(fetch).mock.calls[0]!;
    expect(init).toMatchObject({
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({
      investigation_id: 1,
    });
  });

  it("returns the typed data directly on a success envelope", async () => {
    const summary = {
      investigation_id: 7,
      report_name: "report.txt",
      risk_score: 42,
      severity: "high",
      confidence: 0.9,
      status: "complete",
      analyzed_at: "2026-08-24T00:00:00",
    };
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse({ success: true, data: summary, error: null }),
    );

    const result = await runCommand("get_investigation", { investigation_id: 7 });

    expect(result).toEqual(summary);
  });

  it("throws a typed CommandFailedError preserving the backend error code/message", async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse({
        success: false,
        data: null,
        error: { code: "INVESTIGATION_NOT_FOUND", message: "No investigation with id 999." },
      }),
    );

    await expect(
      runCommand("get_investigation", { investigation_id: 999 }),
    ).rejects.toMatchObject(
      new CommandFailedError(
        "get_investigation",
        "INVESTIGATION_NOT_FOUND",
        "No investigation with id 999.",
      ),
    );
  });

  it("does not treat an HTTP failure as success", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response("Bad Gateway", { status: 502, statusText: "Bad Gateway" }),
    );

    await expect(runCommand("list_investigations", {})).rejects.toBeInstanceOf(
      CommandHttpError,
    );
  });

  it("represents a network failure as a typed CommandNetworkError", async () => {
    vi.mocked(fetch).mockRejectedValue(new TypeError("Failed to fetch"));

    await expect(runCommand("list_investigations", {})).rejects.toBeInstanceOf(
      CommandNetworkError,
    );
  });

  it("rejects a malformed response instead of treating it as successful", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse({ unexpected: "shape" }));

    await expect(runCommand("list_investigations", {})).rejects.toBeInstanceOf(
      CommandMalformedResponseError,
    );
  });

  it("rejects non-JSON response bodies as malformed, not success", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response("<html>not json</html>", {
        status: 200,
        headers: { "Content-Type": "text/html" },
      }),
    );

    await expect(runCommand("list_investigations", {})).rejects.toBeInstanceOf(
      CommandMalformedResponseError,
    );
  });

  it("propagates SidecarNotConnectedError from getSidecarOrigin() without calling fetch", async () => {
    isTauriMock.mockReturnValue(false);

    await expect(runCommand("list_investigations", {})).rejects.toThrow(
      /sidecar origin is not available/,
    );
    expect(vi.mocked(fetch)).not.toHaveBeenCalled();
  });

  it("never calls Tauri invoke directly for command transport (only for origin resolution)", async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse({ success: true, data: [], error: null }),
    );

    await runCommand("list_investigations", {});

    // Exactly one invoke call: get_sidecar_origin. No command-transport
    // invoke call exists -- everything after origin resolution is HTTP.
    expect(invokeMock).toHaveBeenCalledTimes(1);
    expect(invokeMock).toHaveBeenCalledWith("get_sidecar_origin");
  });
});

// ---------------------------------------------------------------------------
// getSidecarStatus() -- Phase 4E-P3 Part 2D-3C
// ---------------------------------------------------------------------------

function validSidecarStatus(overrides: Partial<SidecarStatus> = {}): SidecarStatus {
  return {
    state: "RUNNING",
    restart_pending: false,
    restart_pending_attempt: null,
    restart_attempts: 0,
    restart_exhausted: false,
    sequence: 1,
    ...overrides,
  };
}

describe("getSidecarStatus", () => {
  beforeEach(() => {
    invokeMock.mockReset();
    isTauriMock.mockReset().mockReturnValue(true);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("calls invoke('get_sidecar_status') directly, never through runCommand/fetch", async () => {
    invokeMock.mockResolvedValue(validSidecarStatus({ sequence: 42 }));
    vi.stubGlobal("fetch", vi.fn());

    const status = await getSidecarStatus();

    expect(invokeMock).toHaveBeenCalledWith("get_sidecar_status");
    expect(status.sequence).toBe(42);
    expect(vi.mocked(fetch)).not.toHaveBeenCalled();
    vi.unstubAllGlobals();
  });

  it("rejects with SidecarStatusUnavailableError when no Tauri runtime is present", async () => {
    isTauriMock.mockReturnValue(false);

    await expect(getSidecarStatus()).rejects.toBeInstanceOf(SidecarStatusUnavailableError);
    expect(invokeMock).not.toHaveBeenCalled();
  });

  it("rejects with SidecarStatusUnavailableError when invoke() itself fails", async () => {
    invokeMock.mockRejectedValue(new Error("IPC channel closed"));

    await expect(getSidecarStatus()).rejects.toThrow(/invoke\(\) failed/);
  });

  it("rejects with SidecarStatusUnavailableError for a structurally malformed response", async () => {
    invokeMock.mockResolvedValue({ state: "RUNNING" }); // missing required fields

    await expect(getSidecarStatus()).rejects.toBeInstanceOf(SidecarStatusUnavailableError);
  });

  it("rejects for a response with an invalid lifecycle state string", async () => {
    invokeMock.mockResolvedValue(validSidecarStatus({ state: "RESTARTING" as never }));

    await expect(getSidecarStatus()).rejects.toBeInstanceOf(SidecarStatusUnavailableError);
  });

  it("never fabricates a fallback status -- resolves only with the validated real value", async () => {
    const real = validSidecarStatus({ sequence: 7, restart_attempts: 2 });
    invokeMock.mockResolvedValue(real);

    const status = await getSidecarStatus();

    expect(status).toEqual(real);
  });
});

// ---------------------------------------------------------------------------
// setVirustotalApiKey() -- SOC-IQ Part 8 (ADR-008 Part 1B-3)
// ---------------------------------------------------------------------------

describe("setVirustotalApiKey", () => {
  beforeEach(() => {
    invokeMock.mockReset();
    isTauriMock.mockReset().mockReturnValue(true);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("calls invoke('keystore_set_secret') directly with the fixed secret name, never through runCommand/fetch", async () => {
    invokeMock.mockResolvedValue(undefined);
    vi.stubGlobal("fetch", vi.fn());

    await setVirustotalApiKey("fake-test-key-123");

    expect(invokeMock).toHaveBeenCalledWith("keystore_set_secret", {
      name: "virustotal_api_key",
      value: "fake-test-key-123",
    });
    expect(vi.mocked(fetch)).not.toHaveBeenCalled();
    vi.unstubAllGlobals();
  });

  it("rejects with KeystoreWriteError when no Tauri runtime is present", async () => {
    isTauriMock.mockReturnValue(false);

    await expect(setVirustotalApiKey("fake-test-key-123")).rejects.toBeInstanceOf(
      KeystoreWriteError,
    );
    expect(invokeMock).not.toHaveBeenCalled();
  });

  it("rejects with KeystoreWriteError, carrying the real message, when the Rust command itself fails", async () => {
    invokeMock.mockRejectedValue(new Error("the platform secret store is unavailable"));

    await expect(setVirustotalApiKey("fake-test-key-123")).rejects.toThrow(
      /the platform secret store is unavailable/,
    );
  });

  it("never includes the entered credential value in a thrown error's message", async () => {
    invokeMock.mockRejectedValue(new Error("write failed"));

    await expect(setVirustotalApiKey("do-not-leak-this-9F3K")).rejects.not.toThrow(
      /do-not-leak-this-9F3K/,
    );
  });
});
