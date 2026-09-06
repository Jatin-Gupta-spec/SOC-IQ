import type { ReactElement, SVGProps } from "react";

/**
 * Navigation icon set (Phase 4G-2 Part 2).
 *
 * The repository has no frontend icon system yet — `app/gui/design/icons`
 * (the PySide6 side) is an empty stub, and no icon library is a project
 * dependency. Per §9, the fallback when no appropriate icon exists is to
 * establish one locally rather than add a dependency for eight icons.
 * These are small, self-authored, currentColor-stroked line icons — no
 * emoji, no arbitrary Unicode glyphs.
 *
 * Every icon shares the same 20x20 viewBox and prop shape so they are
 * interchangeable in `NavigationItem.icon`. `aria-hidden`/`focusable`
 * are set by the consumer (`NavigationLink`), not baked in here, since
 * an icon rendered standalone elsewhere might need different semantics.
 */

type IconProps = SVGProps<SVGSVGElement>;

const shared: IconProps = {
  viewBox: "0 0 20 20",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.6,
  strokeLinecap: "round",
  strokeLinejoin: "round",
};

export function DashboardIcon(props: IconProps): ReactElement {
  return (
    <svg {...shared} {...props}>
      <rect x="3" y="3" width="6" height="6" rx="1" />
      <rect x="11" y="3" width="6" height="6" rx="1" />
      <rect x="3" y="11" width="6" height="6" rx="1" />
      <rect x="11" y="11" width="6" height="6" rx="1" />
    </svg>
  );
}

export function AnalyzeIcon(props: IconProps): ReactElement {
  return (
    <svg {...shared} {...props}>
      <circle cx="8.5" cy="8.5" r="5" />
      <line x1="16.5" y1="16.5" x2="12.6" y2="12.6" />
    </svg>
  );
}

export function InvestigationsIcon(props: IconProps): ReactElement {
  return (
    <svg {...shared} {...props}>
      <path d="M3 5.5c0-.55.45-1 1-1h3.7l1.3 1.7H16c.55 0 1 .45 1 1v8.3c0 .55-.45 1-1 1H4c-.55 0-1-.45-1-1V5.5Z" />
    </svg>
  );
}

export function IocExplorerIcon(props: IconProps): ReactElement {
  return (
    <svg {...shared} {...props}>
      <circle cx="10" cy="10" r="6.5" />
      <circle cx="10" cy="10" r="1.4" fill="currentColor" stroke="none" />
      <line x1="10" y1="2" x2="10" y2="4.6" />
      <line x1="10" y1="15.4" x2="10" y2="18" />
      <line x1="2" y1="10" x2="4.6" y2="10" />
      <line x1="15.4" y1="10" x2="18" y2="10" />
    </svg>
  );
}

export function ThreatIntelIcon(props: IconProps): ReactElement {
  return (
    <svg {...shared} {...props}>
      <path d="M10 2.5 16.5 5v5c0 4.1-2.75 6.9-6.5 8-3.75-1.1-6.5-3.9-6.5-8V5L10 2.5Z" />
    </svg>
  );
}

export function RiskIcon(props: IconProps): ReactElement {
  return (
    <svg {...shared} {...props}>
      <path d="M10 3 17.5 16H2.5L10 3Z" />
      <line x1="10" y1="8.2" x2="10" y2="12" />
      <circle cx="10" cy="14.2" r="0.15" fill="currentColor" />
    </svg>
  );
}

export function ReportsIcon(props: IconProps): ReactElement {
  return (
    <svg {...shared} {...props}>
      <path d="M5 2.8h7l3 3v11.4a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V3.8a1 1 0 0 1 1-1Z" />
      <line x1="6.8" y1="9" x2="13.2" y2="9" />
      <line x1="6.8" y1="12" x2="13.2" y2="12" />
      <line x1="6.8" y1="15" x2="10.5" y2="15" />
    </svg>
  );
}

export function SettingsIcon(props: IconProps): ReactElement {
  return (
    <svg {...shared} {...props}>
      <circle cx="10" cy="10" r="2.6" />
      <path d="M10 3.2v1.9M10 14.9v1.9M16.8 10h-1.9M5.1 10H3.2M14.9 5.1l-1.35 1.35M6.45 13.55 5.1 14.9M14.9 14.9l-1.35-1.35M6.45 6.45 5.1 5.1" />
    </svg>
  );
}
