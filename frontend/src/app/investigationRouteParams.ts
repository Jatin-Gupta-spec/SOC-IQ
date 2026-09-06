/**
 * `:investigationId` route-parameter parsing/validation (Phase 4J-3).
 *
 * `investigation_id` is a backend integer ID -- `GetInvestigationRequest`
 * (`app/application/dto.py`) rejects anything that isn't a positive
 * `int` (`investigation_id <= 0` raises `CommandValidationError`,
 * mirrored here as the zero/negative cases). This module is the one
 * place that turns the raw `string | undefined` React Router hands
 * `useParams()` into that same validated positive-integer contract --
 * kept independent of any route component so it's unit-testable on
 * its own and reusable by the eventual data-fetch hook (out of scope
 * for 4J-3, see docs/phase4/... 4J-3 scope).
 *
 * Deliberately strict rather than forgiving: `Number("12abc")` is
 * `NaN` (safe), but `Number("12 ")` or `parseInt("12abc")` would
 * silently coerce a malformed value into a "valid" one. This parser
 * rejects anything that isn't *exactly* an optional leading `-`
 * followed by digits -- no surrounding whitespace, no partial
 * matches, no decimal point, no exponent notation, no leading `+`.
 */

export type InvestigationIdParseResult =
  | { readonly valid: true; readonly investigationId: number }
  | { readonly valid: false };

const INVALID: InvestigationIdParseResult = { valid: false };

/** Exactly one or more ASCII digits -- no sign, no whitespace, no
 * decimal point, no exponent, no leading zeros excluded (backend
 * itself does no such exclusion; "007" is a plain digit string that
 * parses to 7 and is left to the backend's own positive-integer
 * check). */
const DIGITS_ONLY = /^[0-9]+$/;

/**
 * Parse and validate a raw `:investigationId` route-parameter value.
 *
 * Rejects (returns `{ valid: false }`):
 * - `undefined` / missing parameter
 * - empty string
 * - whitespace-only string
 * - any non-numeric content (including a trailing/leading non-digit,
 *   e.g. `"12abc"`, `"abc12"`)
 * - decimals (`"1.5"`)
 * - negative numbers (`"-1"`)
 * - zero (`"0"`) -- the backend's own `investigation_id <= 0` check
 *   defines zero as invalid; nothing in the verified contract defines
 *   0 as a valid investigation id
 * - values outside `Number.isSafeInteger`'s range
 *
 * Accepts (`{ valid: true, investigationId }`):
 * - any string matching `DIGITS_ONLY` that parses to a positive safe
 *   integer, e.g. `"1"`, `"123"`, `"9007199254740991"`
 */
export function parseInvestigationId(
  raw: string | undefined,
): InvestigationIdParseResult {
  if (raw === undefined) {
    return INVALID;
  }

  if (!DIGITS_ONLY.test(raw)) {
    // Covers: empty string, whitespace-only, decimals, negatives,
    // "+"-prefixed values, and any non-numeric/mixed content.
    return INVALID;
  }

  const parsed = Number(raw);

  if (!Number.isSafeInteger(parsed)) {
    return INVALID;
  }

  if (parsed <= 0) {
    return INVALID;
  }

  return { valid: true, investigationId: parsed };
}
