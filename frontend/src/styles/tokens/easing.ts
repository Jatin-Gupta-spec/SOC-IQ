/**
 * SOC-IQ Design System — Easing Tokens
 *
 * `app/gui/design/tokens/easing.py` defines these as `QEasingCurve.Type`
 * enum members, which have no numeric/hex value to port literally — Qt's
 * curve math isn't expressible as a source constant the way a hex color
 * or a millisecond count is. What's ported here is the *curve identity*
 * (which named curve each semantic alias maps to), translated to the
 * standard CSS cubic-bezier approximation of that named Qt curve. This
 * is a translation, not an invention — the semantic mapping (e.g.
 * `sidebar` → `InOutCubic`) is unchanged from the Python source.
 */

const linear = "linear";
/** Qt QEasingCurve.InOutQuad */
const inOutQuad = "cubic-bezier(0.455, 0.03, 0.515, 0.955)";
/** Qt QEasingCurve.OutQuad */
const outQuad = "cubic-bezier(0.25, 0.46, 0.45, 0.94)";
/** Qt QEasingCurve.InOutCubic */
const inOutCubic = "cubic-bezier(0.645, 0.045, 0.355, 1)";

export const Easing = {
  linear,
  in: inOutQuad,
  out: outQuad,
  inOut: inOutCubic,

  // Semantic aliases (mirrors the Python class attributes)
  hover: outQuad,
  button: outQuad,
  sidebar: inOutCubic,
  pageTransition: inOutCubic,
  dialog: outQuad,
  tooltip: outQuad,
  toast: outQuad,
  cardLift: outQuad,
  loading: linear,
} as const;

export type EasingToken = typeof Easing;
