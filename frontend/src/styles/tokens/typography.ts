/**
 * SOC-IQ Design System — Typography Tokens
 * Ported 1:1 from `app/gui/design/tokens/typography.py`.
 *
 * Note: `FontFamily.primary` ("Segoe UI") is a Windows system font. It
 * is kept as the ported value (not invented here) but should resolve
 * through a web-safe stack at CSS-variable definition time — see
 * `styles/globals.css`. Not a target-state exception, just a rendering
 * detail; the token value itself is unchanged from Python.
 */

export const FontFamily = {
  primary: "Segoe UI",
  monospace: "JetBrains Mono",
} as const;

export const FontWeight = {
  light: 300,
  regular: 400,
  medium: 500,
  semibold: 600,
  bold: 700,
} as const;

export const FontSize = {
  display: 28,
  heading: 22,
  title: 18,
  subtitle: 16,
  body: 12,
  bodySmall: 11,
  label: 11,
  caption: 10,
  code: 10,
} as const;

export const LineHeight = {
  tight: 1.1,
  normal: 1.3,
  relaxed: 1.5,
} as const;

export interface TextStyle {
  family: string;
  size: number;
  weight: number;
}

function textStyle(family: string, size: number, weight: number): TextStyle {
  return { family, size, weight };
}

export const Typography = {
  display: textStyle(FontFamily.primary, FontSize.display, FontWeight.bold),
  heading: textStyle(
    FontFamily.primary,
    FontSize.heading,
    FontWeight.semibold,
  ),
  title: textStyle(FontFamily.primary, FontSize.title, FontWeight.semibold),
  subtitle: textStyle(
    FontFamily.primary,
    FontSize.subtitle,
    FontWeight.medium,
  ),
  body: textStyle(FontFamily.primary, FontSize.body, FontWeight.regular),
  bodySmall: textStyle(
    FontFamily.primary,
    FontSize.bodySmall,
    FontWeight.regular,
  ),
  label: textStyle(FontFamily.primary, FontSize.label, FontWeight.medium),
  caption: textStyle(
    FontFamily.primary,
    FontSize.caption,
    FontWeight.regular,
  ),
  code: textStyle(FontFamily.monospace, FontSize.code, FontWeight.regular),
} as const;

export type TypographyToken = typeof Typography;
