/**
 * Settings mock domain data (Phase 4G-2 Part 3, §14/§15/§16).
 *
 * Section list restricted to what
 * `docs/architecture/13-frontend-information-architecture.md` and
 * related docs actually support — no invented sections. Controls
 * carry a `value` for display only; nothing here reads from or
 * writes to real persisted settings.
 *
 * SOC-IQ Part 2B-1: the Appearance section's "Theme" control and the
 * former Integrations section's VirusTotal API key control have been
 * removed from this mock list -- both are now real, backend-backed
 * controls rendered directly by `SettingsPage.tsx`
 * (`settings/ThemeControl.tsx`, `settings/VirustotalControl.tsx`), so
 * keeping mock entries for them here would render a second, fake copy
 * next to the real one. Every remaining section/control below is
 * still non-functional mock display, unchanged.
 */

export type SettingControlKind = "toggle" | "select";

export interface SettingControl {
  readonly id: string;
  readonly label: string;
  readonly kind: SettingControlKind;
  readonly value: string;
}

export interface SettingsSection {
  readonly id: string;
  readonly title: string;
  readonly description: string;
  readonly controls: readonly SettingControl[];
}

export const mockSettingsSections: SettingsSection[] = [
  {
    id: "appearance",
    title: "Appearance",
    description: "Display density for the SOC-IQ interface.",
    controls: [
      { id: "density", label: "Density", kind: "select", value: "Comfortable" },
    ],
  },
  {
    id: "application",
    title: "Application",
    description: "General application behavior.",
    controls: [
      { id: "start-page", label: "Start page", kind: "select", value: "Dashboard" },
      { id: "confirm-close", label: "Confirm before closing an investigation", kind: "toggle", value: "On" },
    ],
  },
  {
    id: "notifications",
    title: "Notifications",
    description: "Alerts for investigation and analysis activity.",
    controls: [
      { id: "notify-critical", label: "Notify on critical findings", kind: "toggle", value: "On" },
      { id: "notify-analysis", label: "Notify when analysis completes", kind: "toggle", value: "Off" },
    ],
  },
  {
    id: "security",
    title: "Security",
    description: "Session and access controls.",
    controls: [
      { id: "session-timeout", label: "Session timeout", kind: "select", value: "30 minutes" },
    ],
  },
];
