/**
 * API boundary.
 *
 * Per `docs/contracts/ipc-rules.md` rule 2, React never calls Python
 * directly — it calls the sidecar's HTTP origin, and Tauri hands it the
 * dynamically-assigned port at startup via a Tauri command.
 *
 * Phase 4D SSE Part 4B: that command now exists —
 * `src-tauri/src/lib.rs`'s `get_sidecar_origin`, backed by the real
 * `SidecarProcess` `src-tauri/src/sidecar.rs` already implemented
 * (Phase 2A Part 2B) and now actually drives at application startup
 * (confirmed by reading `src-tauri/src/lib.rs` directly, this Part —
 * nothing constructed or started a `SidecarProcess` before this
 * change). `getSidecarOrigin()` below is wired to the real
 * `invoke("get_sidecar_origin")` call.
 *
 * Phase 4E-P1 (`docs/phase4/PHASE4E_ARCHITECTURE.md` §10, slice
 * "4E-P1 — Typed frontend command client"): `runCommand<K>()` below is
 * now the one canonical, typed transport for
 * `POST /commands/{name}` — see its own doc comment for the contract.
 * `getSidecarOrigin()` (Phase 4D SSE Part 4B) is unchanged; runCommand
 * only ever consumes it, never re-implements origin resolution.
 *
 * Browser/dev preservation: `getSidecarOrigin()` is only ever backed by
 * a real Tauri origin when this code is actually running inside a Tauri
 * webview. Loading the same frontend bundle in a plain browser tab (no
 * Tauri runtime present — e.g. `vite dev` opened directly, or any
 * automated check that renders this app outside `cargo tauri dev`) has
 * no sidecar process behind it at all, so this file preserves exactly
 * the previous behavior for that case: reject with
 * `SidecarNotConnectedError`, the same error shape
 * `eventSourceManager.ts` (Part 4A) already knows how to treat as a
 * normal, retryable "not connected yet" state. `isTauri()` (from
 * `@tauri-apps/api/core`) is the check used to distinguish the two
 * environments, rather than trying/catching `invoke` and hoping the
 * failure mode is distinguishable — `isTauri()` is a synchronous,
 * side-effect-free capability check built for exactly this.
 */

import { invoke, isTauri } from "@tauri-apps/api/core";

import type { ApiFailure, ApiResponse, CommandName, CommandPayload, CommandResult } from "./types";
import { isSidecarStatus } from "../sidecar/validation";
import type { SidecarStatus } from "../sidecar/types";

export class SidecarNotConnectedError extends Error {
  constructor(reason: string) {
    super(
      "The sidecar origin is not available -- " +
        reason +
        ". See shared/api/client.ts and " +
        "docs/phase4/PHASE4D_SSE_PART4A_IMPLEMENTATION.md.",
    );
    this.name = "SidecarNotConnectedError";
  }
}

/**
 * Base type for every error `runCommand()` itself can reject with (as
 * opposed to `SidecarNotConnectedError`, which comes from
 * `getSidecarOrigin()` and simply propagates unchanged). Lets a caller
 * write one `catch (error) { if (error instanceof CommandClientError) ... }`
 * without needing to know which of the four concrete subclasses below
 * it got.
 */
export abstract class CommandClientError extends Error {}

/**
 * The `fetch()` call itself failed -- no response was ever received
 * (offline, connection refused, DNS failure, etc.). Distinct from
 * `CommandHttpError`, which means a response *was* received but with a
 * non-2xx status.
 */
export class CommandNetworkError extends CommandClientError {
  public readonly originalError: unknown;

  constructor(public readonly commandName: CommandName, originalError: unknown) {
    const reason =
      originalError instanceof Error ? originalError.message : String(originalError);
    super(`Network failure calling command "${commandName}": ${reason}`);
    this.name = "CommandNetworkError";
    this.originalError = originalError;
  }
}

/**
 * A response was received but the HTTP status itself was not OK
 * (non-2xx). `POST /commands/{name}` (app/api/app.py) always returns
 * 200 with a `fail()` envelope for *application*-level errors -- this
 * class exists for transport-level failures the FastAPI route itself
 * cannot produce for a known command (proxy errors, an unexpected 5xx
 * from something in front of uvicorn, etc.), so it must still be
 * handled rather than assumed impossible.
 */
export class CommandHttpError extends CommandClientError {
  constructor(
    public readonly commandName: CommandName,
    public readonly status: number,
    public readonly statusText: string,
  ) {
    super(
      `HTTP ${status} ${statusText} calling command "${commandName}".`,
    );
    this.name = "CommandHttpError";
  }
}

/**
 * A 2xx response was received but its body was not valid JSON, or was
 * valid JSON that does not match the `ApiResponse<T>` envelope shape
 * (`app/application/responses.py`'s `Envelope.to_dict()`). Never
 * treated as a success -- see the "never a fake success" requirement
 * in `docs/phase4/PHASE4E_ARCHITECTURE.md` §10.
 */
export class CommandMalformedResponseError extends CommandClientError {
  constructor(
    public readonly commandName: CommandName,
    reason: string,
  ) {
    super(`Malformed response for command "${commandName}": ${reason}`);
    this.name = "CommandMalformedResponseError";
  }
}

/**
 * The backend returned a well-formed `fail()` envelope
 * (`success: false`). `code` and `message` are the exact values from
 * `app/application/errors.py`'s error-code catalog / `str(exception)`,
 * preserved verbatim -- never reworded, never dropped, never collapsed
 * into a single generic message (per the "preserve backend error
 * codes"/"do not add a giant generic catch block" requirements).
 */
export class CommandFailedError extends CommandClientError {
  constructor(
    public readonly commandName: CommandName,
    public readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "CommandFailedError";
  }
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/**
 * Structural validation of a parsed JSON body against the
 * `ApiResponse<T>` envelope shape (`success`/`data`/`error`, per
 * `app/application/responses.py::Envelope.to_dict()`). Does not (and
 * cannot) validate `data`'s inner shape against `T` -- that is the
 * backend contract each command DTO/handler already enforces; this
 * function only guards against a body that isn't the envelope at all
 * (e.g. an empty body, a proxy error page, a future transport bug).
 */
function isApiResponseShape(value: unknown): value is ApiResponse<unknown> {
  if (!isPlainObject(value) || typeof value.success !== "boolean") {
    return false;
  }

  if (value.success) {
    return "data" in value;
  }

  return (
    isPlainObject(value.error) &&
    typeof value.error.code === "string" &&
    typeof value.error.message === "string"
  );
}

/**
 * Typed frontend command client -- Phase 4E-P1
 * (`docs/phase4/PHASE4E_ARCHITECTURE.md` §4/§10).
 *
 * The one canonical transport for every application command: resolves
 * the sidecar origin via `getSidecarOrigin()` (never re-implemented or
 * bypassed here), POSTs to the existing `POST /commands/{name}` route
 * (`app/api/app.py::run_command`) with a JSON body, and parses the
 * response against the existing `ApiResponse<T>` envelope
 * (`app/application/responses.py`) -- no second, incompatible envelope
 * is introduced.
 *
 * `name`/`payload` are typed against `CommandContracts`
 * (`shared/api/types.ts`), so e.g.
 * `runCommand("get_investigation", { investigation_id: 1 })` has its
 * payload checked at compile time and its resolved value typed as
 * `InvestigationSummary` -- no caller needs an explicit `<T>` and no
 * caller can pass a payload shape the backend DTO would reject at the
 * type level.
 *
 * On success, resolves to the command's typed result data directly
 * (not the envelope wrapper) -- `T`, not `ApiResponse<T>`. On any
 * failure, rejects with one of the four `CommandClientError`
 * subclasses above; a caller that only cares "did it work" can treat
 * every rejection uniformly via `instanceof CommandClientError`, and a
 * caller that needs the backend's error code can narrow to
 * `CommandFailedError`. Never silently turns a failure into a fake
 * success, never swallows an error, never hardcodes the sidecar port
 * (origin comes from `getSidecarOrigin()` alone), and never touches
 * Tauri directly -- it only calls the existing `getSidecarOrigin()`
 * abstraction, exactly as `eventSourceManager.ts` already does for
 * SSE.
 */
export async function runCommand<K extends CommandName>(
  name: K,
  payload: CommandPayload<K>,
): Promise<CommandResult<K>> {
  // Propagates SidecarNotConnectedError unchanged -- origin resolution
  // is entirely getSidecarOrigin()'s concern, never duplicated here.
  const origin = await getSidecarOrigin();

  let response: Response;
  try {
    response = await fetch(`${origin}/commands/${encodeURIComponent(name)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch (error) {
    throw new CommandNetworkError(name, error);
  }

  if (!response.ok) {
    throw new CommandHttpError(name, response.status, response.statusText);
  }

  let body: unknown;
  try {
    body = await response.json();
  } catch (error) {
    const reason = error instanceof Error ? error.message : String(error);
    throw new CommandMalformedResponseError(
      name,
      `response body was not valid JSON (${reason}).`,
    );
  }

  if (!isApiResponseShape(body)) {
    throw new CommandMalformedResponseError(
      name,
      "response body did not match the ApiResponse envelope shape.",
    );
  }

  if (!body.success) {
    const failure = body as ApiFailure;
    throw new CommandFailedError(
      name,
      failure.error.code,
      failure.error.message,
    );
  }

  return body.data as CommandResult<K>;
}

/**
 * Resolve the sidecar's HTTP origin (e.g. `http://127.0.0.1:54213`),
 * per `docs/contracts/ipc-rules.md` rule 2 ("dynamic port, never
 * hard-coded"). Backed by a real `invoke("get_sidecar_origin")` call
 * when running inside Tauri; rejects with `SidecarNotConnectedError`
 * otherwise (no Tauri runtime present) or when the Rust command itself
 * reports the sidecar is not yet `Running` (still starting, failed to
 * start, or has exited) — see `src-tauri/src/lib.rs`'s
 * `get_sidecar_origin` doc comment for exactly which states reject.
 *
 * Callers (currently just `shared/events/eventSourceManager.ts`) must
 * continue to treat rejection as a normal, expected state, not an
 * exceptional one — that contract is unchanged from Part 4A, only the
 * source of the rejection is now real instead of unconditional.
 */
export async function getSidecarOrigin(): Promise<string> {
  if (!isTauri()) {
    throw new SidecarNotConnectedError(
      "no Tauri runtime is present (this code is not running inside the " +
        "Tauri desktop shell)",
    );
  }

  try {
    return await invoke<string>("get_sidecar_origin");
  } catch (error) {
    const reason = error instanceof Error ? error.message : String(error);
    throw new SidecarNotConnectedError(reason);
  }
}

/**
 * Rejection type for {@link getSidecarStatus} — mirrors
 * `SidecarNotConnectedError`'s own shape/naming for the same reason
 * (Phase 4E-P3 Part 2D-3C task brief §5: "reuse the existing
 * getSidecarOrigin() pattern for a direct invoke() Tauri command").
 * Covers both "no Tauri runtime" / "the invoke() call itself failed"
 * (transport) and "the response did not pass `isSidecarStatus()`"
 * (contract) — a caller that only needs "did this attempt produce a
 * usable status" can treat both uniformly; `reason` still distinguishes
 * them for logging/diagnostics.
 */
export class SidecarStatusUnavailableError extends Error {
  constructor(reason: string) {
    super(`The sidecar status snapshot is not available -- ${reason}.`);
    this.name = "SidecarStatusUnavailableError";
  }
}

/**
 * Direct `invoke("get_sidecar_status")` wrapper — Phase 4E-P3 Part
 * 2D-3C task brief §5. `get_sidecar_status` (`src-tauri/src/lib.rs`)
 * is a plain, synchronous, read-only `#[tauri::command]` reading
 * already-in-process Rust state; it is not one of the Python sidecar's
 * `POST /commands/{name}` HTTP commands, so it does not go through
 * `runCommand()` — exactly the same reasoning `getSidecarOrigin()`
 * above already established for `get_sidecar_origin`, the one other
 * command this file calls via a direct `invoke()`. This is that same
 * pattern's smallest extension, not a second command architecture.
 *
 * The Tauri IPC layer's generic type parameter is not validation
 * (task brief §16/§21's "treat the Tauri response as runtime data") —
 * the raw result is checked with the frozen Part 2D-1 validator
 * (`isSidecarStatus`, `validation.ts`) before this function will ever
 * resolve with it. Reuses that existing validator verbatim; no second,
 * duplicate predicate is introduced here (task brief §16: "do not
 * duplicate existing validation logic").
 *
 * Rejects with {@link SidecarStatusUnavailableError} — never a fake
 * fallback `SidecarStatus`, never a fabricated `sequence` (task brief
 * §17) — for: no Tauri runtime present, the `invoke()` call itself
 * failing, or a structurally malformed response. The caller (Part
 * 2D-3C's reconciliation coordinator) decides what "unavailable"
 * means for the current projected state; this function's only job is
 * "give me a real, valid `SidecarStatus`, or tell me plainly that I
 * don't have one."
 */
export async function getSidecarStatus(): Promise<SidecarStatus> {
  if (!isTauri()) {
    throw new SidecarStatusUnavailableError(
      "no Tauri runtime is present (this code is not running inside the " +
        "Tauri desktop shell)",
    );
  }

  let raw: unknown;
  try {
    raw = await invoke<unknown>("get_sidecar_status");
  } catch (error) {
    const reason = error instanceof Error ? error.message : String(error);
    throw new SidecarStatusUnavailableError(`invoke() failed -- ${reason}`);
  }

  if (!isSidecarStatus(raw)) {
    throw new SidecarStatusUnavailableError(
      "the response did not match the SidecarStatus contract",
    );
  }

  return raw;
}

/**
 * The fixed secret `name` `keystore_set_secret` stores the VirusTotal
 * API key under -- identical, by design, to `src-tauri/src/sidecar.rs`'s
 * `VIRUSTOTAL_SECRET_NAME` constant (`"virustotal_api_key"`) and to
 * `app/settings/repository.py`'s `_VT_API_KEY_SECRET_NAME`. All three
 * must agree for the Rust-owned write this function performs to end up
 * as the same credential `apply_secret_handoff()` reads back at the
 * next sidecar spawn (ADR-008).
 */
const VIRUSTOTAL_SECRET_NAME = "virustotal_api_key";

/**
 * Rejection type for {@link setVirustotalApiKey} -- mirrors
 * `SidecarStatusUnavailableError`'s shape/naming for the same reason
 * that class documents: a caller needs one type to catch regardless of
 * whether the failure was "no Tauri runtime", "the invoke() call
 * itself failed", or the Rust command's own `Result::Err` (already a
 * plain, secret-free `String` per `keystore.rs`'s `describe_error`).
 */
export class KeystoreWriteError extends Error {
  constructor(reason: string) {
    super(`The VirusTotal API key could not be saved -- ${reason}.`);
    this.name = "KeystoreWriteError";
  }
}

/**
 * Store the VirusTotal API key via the existing, already-registered
 * `keystore_set_secret` Tauri command (ADR-008 Part 1B-3) -- the
 * approved and only credential write path. This is a direct
 * `invoke()`, not a `runCommand()` call: exactly the same reasoning
 * `getSidecarOrigin()`/`getSidecarStatus()` above already establish --
 * `keystore_set_secret` is a native Rust capability reachable
 * synchronously in-process, not one of the Python sidecar's
 * `POST /commands/{name}` HTTP commands.
 *
 * `value` is never logged, retained, or echoed back by this function;
 * the caller (`useVirustotalKeySave`) is likewise expected to clear
 * its own copy once this promise settles either way. This function
 * does not attempt to read the credential back -- confirming a write
 * "worked" beyond `keystore_set_secret` resolving without error is not
 * this checkpoint's job (see `VirustotalControl`'s restart-required
 * messaging for why "worked" and "active" are different claims here).
 */
export async function setVirustotalApiKey(value: string): Promise<void> {
  if (!isTauri()) {
    throw new KeystoreWriteError(
      "no Tauri runtime is present (this code is not running inside the " +
        "Tauri desktop shell)",
    );
  }

  try {
    await invoke<void>("keystore_set_secret", { name: VIRUSTOTAL_SECRET_NAME, value });
  } catch (error) {
    const reason = error instanceof Error ? error.message : String(error);
    throw new KeystoreWriteError(reason);
  }
}
