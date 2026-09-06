/**
 * SOC-IQ Design System — Spacing Tokens
 * Ported 1:1 from `app/gui/design/tokens/spacing.py` (values in px).
 */

export const Spacing = {
  none: 0,
  xxs: 2,
  xs: 4,

  sm: 8,
  md: 12,
  lg: 16,

  xl: 24,
  xxl: 32,
  xxxl: 48,

  pageMargin: 24,
  sectionGap: 24,
  cardPadding: 16,
  panelPadding: 20,

  gridGap: 20,
  cardGap: 16,
  widgetGap: 12,

  tableCellPadding: 8,
  rowHeight: 32,

  labelGap: 6,
  fieldGap: 12,
  contentGap: 16,

  sidebarPadding: 16,
  sidebarItemHeight: 44,
  sidebarIconGap: 12,

  toolbarHeight: 52,
  headerHeight: 64,
  statusbarHeight: 28,

  dialogPadding: 24,
} as const;

export type SpacingToken = typeof Spacing;
