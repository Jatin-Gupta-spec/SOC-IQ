/**
 * Investigation Workspace — Threat Intel raw-payload detail renderer —
 * Phase 4J-6 Part 3C.
 *
 * Renders `InvestigationWorkspaceData.rawThreatIntelligence` (typed
 * `Record<string, unknown>`, `shared/api/types.ts`) as a labeled,
 * readable hierarchy — never `JSON.stringify(...)` in the page (task
 * brief §6), and never a fabricated field: every label rendered here
 * is the payload's own real key (humanized for display), and every
 * value rendered here is the payload's own real value. No provider
 * schema is assumed — the type stays opaque by design (the backend's
 * own `Investigation.threat_intelligence` is deliberately not DTO'd,
 * `shared/api/types.ts`'s own comment on that field), so this module
 * never asserts a shape onto the payload up front; it walks whatever
 * is actually there at runtime and renders exactly that (task brief
 * §3/§5/§7).
 *
 * # Why a generic walker rather than named fields
 *
 * Part 3A/3B established the precedent (`InvestigationThreatIntel`'s
 * own doc comment) that no component reads a specific key out of
 * `rawThreatIntelligence` — doing so would mean guessing an unstated,
 * possibly-provider-specific schema. Part 3C's brief asks for a real
 * "Provider Details" presentation of whatever the payload actually
 * contains, while still forbidding invented field semantics
 * ("Reputation", "Detection information", etc. "unless the underlying
 * data actually contains them", task brief §6) and forbidding
 * reconstructed IOC-to-result matching (task brief §14). A generic
 * key-driven renderer satisfies both constraints at once: it can
 * never display a label or a value the payload didn't actually
 * contain, because every label is a real object key (only humanized
 * for readability) and every value is read directly off that key —
 * there is no branch anywhere in this module that names a
 * provider-specific field.
 *
 * # Safety (task brief §13)
 *
 * Some key names are withheld from display outright regardless of
 * value — `SENSITIVE_KEY_PATTERN` below — so that a payload which
 * unexpectedly carries a credential-shaped field (an API key, a
 * bearer token, an authorization header) never reaches the DOM. This
 * check runs on every key at every depth, not just the top level.
 *
 * # Bounds
 *
 * Real provider payloads can be deeply nested or contain long lists
 * (e.g. one record per engine). `MAX_DEPTH` and `MAX_ARRAY_ITEMS`
 * keep this from becoming the "giant wall of data" the task brief
 * warns against (§10) — depth/length are display bounds only, never
 * a reason to alter a value's meaning (§11).
 */

import type { ReactElement } from "react";
import { InfoNote } from "../components/InfoNote";
import "./ProviderDetail.css";

const MAX_DEPTH = 6;
const MAX_ARRAY_ITEMS = 25;

/** Key-name tokens that mean "this field's value IS a secret" on
 * their own, in any key that contains them -- withheld unconditionally
 * (task brief §13). */
const SENSITIVE_ROOT_TOKENS = new Set([
  "secret",
  "password",
  "passwd",
  "credential",
  "credentials",
  "authorization",
  "bearer",
  "token",
]);

/** "key"/"apikey" are ambiguous on their own: the real backend
 * contract (`app/services/threat_intel_state.py`) has genuine,
 * non-secret boolean fields like `invalid_api_key` that describe
 * *whether* a key is valid, not the key's value. A key token is only
 * treated as holding a secret value when none of these status/
 * descriptor tokens are also present in the same field name -- so
 * `invalid_api_key`/`api_key_configured` stay visible, while a field
 * that is actually named just `api_key`/`apiKey` stays hidden. */
const KEY_STATUS_MODIFIER_TOKENS = new Set([
  "invalid",
  "valid",
  "has",
  "no",
  "missing",
  "configured",
  "present",
  "enabled",
  "disabled",
  "required",
  "expired",
  "rotated",
  "count",
  "name",
  "id",
  "type",
  "status",
]);

function tokenizeKey(key: string): string[] {
  return key
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .split(/[_\-\s]+/)
    .map((token) => token.toLowerCase())
    .filter((token) => token.length > 0);
}

/** Withheld from display at any depth, regardless of value, so a
 * credential-shaped field never reaches the DOM (task brief §13).
 * Matches on the key name only -- never on value content, since a
 * value's shape alone (e.g. a long hex string) is not a reliable
 * signal, and heuristically hiding real IOC data by its shape would
 * itself misrepresent the payload. */
function isSensitiveKey(key: string): boolean {
  const tokens = tokenizeKey(key);

  if (tokens.some((token) => SENSITIVE_ROOT_TOKENS.has(token))) {
    return true;
  }

  const hasKeyToken = tokens.includes("key") || tokens.includes("apikey");
  if (!hasKeyToken) {
    return false;
  }

  const hasStatusModifier = tokens.some((token) => KEY_STATUS_MODIFIER_TOKENS.has(token));
  return !hasStatusModifier;
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** Turns a real object key into a readable label -- e.g. `invalid_api_key`
 * (were it not withheld) or `rateLimited` both -> "Rate Limited"-style
 * casing. Formatting only: the underlying key is what decides whether
 * the field is shown at all (`isSensitiveKey`), this only affects how
 * its name is displayed. */
function humanizeKey(key: string): string {
  const tokens = tokenizeKey(key);
  if (tokens.length === 0) {
    return key;
  }
  return tokens.map((token) => token.charAt(0).toUpperCase() + token.slice(1)).join(" ");
}

function formatScalar(value: string | number | boolean): string {
  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
  }
  return String(value);
}

interface ProviderDetailValueProps {
  readonly value: unknown;
  readonly depth: number;
}

/** Renders one value at `depth`, recursing into objects/arrays.
 * Depth-capped (`MAX_DEPTH`) rather than assuming any real payload
 * is bounded -- an over-depth branch renders an honest "not shown"
 * note instead of either crashing or silently truncating without
 * saying so. */
function ProviderDetailValue({ value, depth }: ProviderDetailValueProps): ReactElement {
  if (value === null || value === undefined) {
    return <span className="provider-detail__scalar provider-detail__scalar--empty">Not provided</span>;
  }

  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return <span className="provider-detail__scalar">{formatScalar(value)}</span>;
  }

  if (depth >= MAX_DEPTH) {
    return <span className="provider-detail__scalar provider-detail__scalar--empty">Additional detail not shown</span>;
  }

  if (Array.isArray(value)) {
    if (value.length === 0) {
      return <span className="provider-detail__scalar provider-detail__scalar--empty">None</span>;
    }
    const shown = value.slice(0, MAX_ARRAY_ITEMS);
    const remaining = value.length - shown.length;
    return (
      <ol className="provider-detail__list">
        {shown.map((item, index) => (
          // eslint-disable-next-line react/no-array-index-key -- raw
          // provider array items carry no stable identifier of their own.
          <li key={index} className="provider-detail__list-item">
            <ProviderDetailValue value={item} depth={depth + 1} />
          </li>
        ))}
        {remaining > 0 ? (
          <li className="provider-detail__list-item provider-detail__list-item--truncated">
            {remaining} more item{remaining === 1 ? "" : "s"} not shown
          </li>
        ) : null}
      </ol>
    );
  }

  if (isPlainObject(value)) {
    const entries = Object.entries(value).filter(([key]) => !isSensitiveKey(key));
    if (entries.length === 0) {
      return <span className="provider-detail__scalar provider-detail__scalar--empty">No fields available</span>;
    }
    return (
      <dl className="provider-detail__fields">
        {entries.map(([key, entryValue]) => (
          <div key={key} className="provider-detail__field">
            <dt className="provider-detail__field-label">{humanizeKey(key)}</dt>
            <dd className="provider-detail__field-value">
              <ProviderDetailValue value={entryValue} depth={depth + 1} />
            </dd>
          </div>
        ))}
      </dl>
    );
  }

  // Any other real JS runtime value (function, symbol, etc.) should
  // never occur in JSON-shaped API data -- rendered honestly as
  // "unavailable" rather than silently coerced into a fabricated
  // string representation.
  return <span className="provider-detail__scalar provider-detail__scalar--empty">Not provided</span>;
}

export interface ProviderDetailProps {
  /** `InvestigationWorkspaceData.rawThreatIntelligence`. Callers only
   * render this once it is known to be non-null (missing data is a
   * distinct, separate presentation -- `InvestigationThreatIntel`). */
  readonly raw: Record<string, unknown>;
}

/**
 * The Part 3C "Provider details" disclosure: a collapsed-by-default,
 * keyboard-accessible `<details>`/`<summary>` (native semantics, task
 * brief §10/§18 -- no custom modal, no bespoke expand/collapse
 * handling) wrapping a real, labeled hierarchy of whatever
 * `rawThreatIntelligence` actually contains once sensitive-looking
 * keys are withheld.
 */
export function ProviderDetail({ raw }: ProviderDetailProps): ReactElement {
  const entries = Object.entries(raw).filter(([key]) => !isSensitiveKey(key));

  if (entries.length === 0) {
    return <InfoNote>No provider detail fields are available for this investigation.</InfoNote>;
  }

  return (
    <details className="provider-detail__disclosure">
      <summary className="provider-detail__summary">Show provider details</summary>
      <div className="provider-detail__content">
        <dl className="provider-detail__fields">
          {entries.map(([key, value]) => (
            <div key={key} className="provider-detail__field">
              <dt className="provider-detail__field-label">{humanizeKey(key)}</dt>
              <dd className="provider-detail__field-value">
                <ProviderDetailValue value={value} depth={1} />
              </dd>
            </div>
          ))}
        </dl>
      </div>
    </details>
  );
}
