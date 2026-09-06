import { createContext, type ReactElement, type ReactNode, useContext } from "react";
import { Color, type ColorToken } from "@/styles/tokens";

/**
 * Theme/design-system foundation.
 *
 * SOC-IQ has one theme — the dark SOC theme ported from
 * `app/gui/design/theme/` (see `docs/architecture/FILE_STRUCTURE.md`:
 * "dark SOC theme concept carries forward via design tokens"). There is
 * no light/dark toggle in the target architecture, so this provider
 * does not implement one. Its job is narrower: give components a way
 * to reach token VALUES from JS/TS (e.g. for canvas/SVG drawing, where
 * a CSS custom property can't be read without extra plumbing) without
 * each component importing `styles/tokens` directly and re-deriving
 * its own notion of "the current theme."
 */

const ThemeContext = createContext<ColorToken>(Color);

export function ThemeProvider({
  children,
}: {
  children: ReactNode;
}): ReactElement {
  return (
    <ThemeContext.Provider value={Color}>{children}</ThemeContext.Provider>
  );
}

export function useThemeColors(): ColorToken {
  return useContext(ThemeContext);
}
