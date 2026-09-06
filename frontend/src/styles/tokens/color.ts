/**
 * SOC-IQ Design System — Color Tokens
 *
 * PORTED 1:1 from the approved Python source of truth:
 * `app/gui/design/tokens/colors.py`. Every hex value below was read
 * directly from that file — none were invented for this port. See
 * `docs/architecture/11-design-system-architecture.md`.
 *
 * The `Verdict` group is a genuinely NEW addition (no Python source
 * exists for it — `11-design-system-architecture.md` calls this out
 * explicitly as "chosen at implementation time"). It exists to make the
 * `NOT_FOUND != CLEAN` invariant (see
 * `docs/architecture/08-threat-intelligence-architecture.md`,
 * `NON_NEGOTIABLE_RULES.md` #9) visually enforced, not just data-enforced.
 * Every verdict color is distinct from every other verdict color.
 */

export const Background = {
  primary: "#0F1117",
  secondary: "#151922",
  tertiary: "#1B2130",
} as const;

export const Surface = {
  primary: "#171C26",
  secondary: "#1E2431",
  elevated: "#252C3B",
} as const;

export const Border = {
  subtle: "#262D3A",
  default: "#313949",
  strong: "#495365",
  /** Purple brand primary — matches buttons/links, not the old blue. */
  focus: "#8B5CF6",
} as const;

export const Text = {
  primary: "#F5F7FA",
  secondary: "#C8D0DD",
  muted: "#98A2B3",
  disabled: "#667085",
  inverse: "#111827",
} as const;

export const Brand = {
  primary: "#8B5CF6",
  hover: "#A78BFA",
  pressed: "#7C3AED",
} as const;

export const Status = {
  success: "#22C55E",
  warning: "#F59E0B",
  error: "#EF4444",
  info: "#38BDF8",
} as const;

export const Severity = {
  low: "#22C55E",
  medium: "#FACC15",
  high: "#F97316",
  critical: "#DC2626",
} as const;

export const Chart = {
  blue: "#4F8CFF",
  cyan: "#38BDF8",
  teal: "#14B8A6",
  green: "#22C55E",
  lime: "#84CC16",
  yellow: "#FACC15",
  orange: "#F97316",
  red: "#EF4444",
  pink: "#EC4899",
  purple: "#8B5CF6",
} as const;

export const Interactive = {
  hover: "#212938",
  pressed: "#2A3446",
  selected: "#314A7F",
} as const;

export const Overlay = {
  modal: "#00000099",
  selection: "#8B5CF633",
} as const;

export const Divider = {
  primary: "#262D3A",
  secondary: "#1E2431",
} as const;

export const Shadow = {
  soft: "#00000055",
  medium: "#00000077",
  strong: "#00000099",
} as const;

/**
 * Threat-intelligence verdict colors. NEW — not ported from Python.
 *
 * Each state is visually distinct on purpose:
 *  - MALICIOUS / ERROR both read as "red family" but are different reds
 *    (critical-severity red vs. status-error red) so a provider failure
 *    is never confusable with a malicious verdict.
 *  - CLEAN is green; NOT_FOUND is a neutral slate — never green, never
 *    gray-disabled — so it cannot be mistaken for CLEAN at a glance,
 *    which is the whole point of the NOT_FOUND != CLEAN invariant.
 *  - UNAVAILABLE (provider is down) is a darker, distinct slate from
 *    NOT_FOUND (provider responded, found nothing) — different failure
 *    modes, different colors.
 *  - NO_API_KEY reuses the brand-hover violet: a configuration nudge,
 *    not a threat signal, so it deliberately does not sit in the
 *    red/amber/green "verdict" family.
 *  - RATE_LIMITED reuses Status.info: transient and informational, not
 *    a verdict about the indicator itself.
 */
export const Verdict = {
  malicious: Severity.critical, // "#DC2626"
  suspicious: Status.warning, // "#F59E0B"
  clean: Status.success, // "#22C55E"
  notFound: "#64748B",
  unsupported: "#94A3B8",
  noApiKey: Brand.hover, // "#A78BFA"
  unavailable: "#475569",
  rateLimited: Status.info, // "#38BDF8"
  error: Status.error, // "#EF4444"
} as const;

export const Color = {
  background: Background,
  surface: Surface,
  border: Border,
  text: Text,
  brand: Brand,
  status: Status,
  severity: Severity,
  chart: Chart,
  interactive: Interactive,
  overlay: Overlay,
  divider: Divider,
  shadow: Shadow,
  verdict: Verdict,
} as const;

export type ColorToken = typeof Color;
