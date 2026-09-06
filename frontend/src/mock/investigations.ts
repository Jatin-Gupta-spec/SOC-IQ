/**
 * Investigations mock domain data (Phase 4G-2 Part 3, §9/§15/§16).
 *
 * Isolated from any production repository/database shape. Static,
 * deterministic values only — no persistence, no mutation.
 */

export type InvestigationStatus = "open" | "in_progress" | "closed";
export type Severity = "low" | "medium" | "high" | "critical";

export interface InvestigationSummary {
  readonly id: string;
  readonly name: string;
  readonly status: InvestigationStatus;
  readonly severity: Severity;
  readonly owner: string;
  readonly openedLabel: string;
  readonly updatedLabel: string;
  readonly iocCount: number;
}

export const mockInvestigations: InvestigationSummary[] = [
  {
    id: "inv-1042",
    name: "Suspicious PowerShell chain — WKS-2214",
    status: "in_progress",
    severity: "high",
    owner: "A. Ramirez",
    openedLabel: "Today, 09:14",
    updatedLabel: "12 minutes ago",
    iocCount: 6,
  },
  {
    id: "inv-1041",
    name: "Phishing report — finance distribution list",
    status: "open",
    severity: "medium",
    owner: "Unassigned",
    openedLabel: "Today, 08:02",
    updatedLabel: "1 hour ago",
    iocCount: 3,
  },
  {
    id: "inv-1038",
    name: "Outbound beacon to unknown domain",
    status: "in_progress",
    severity: "critical",
    owner: "D. Okafor",
    openedLabel: "Yesterday, 22:40",
    updatedLabel: "3 hours ago",
    iocCount: 9,
  },
  {
    id: "inv-1033",
    name: "Repeated failed logons — svc-backup",
    status: "closed",
    severity: "low",
    owner: "A. Ramirez",
    openedLabel: "3 days ago",
    updatedLabel: "yesterday",
    iocCount: 1,
  },
  {
    id: "inv-1029",
    name: "Unsigned binary dropped in Temp",
    status: "closed",
    severity: "medium",
    owner: "D. Okafor",
    openedLabel: "5 days ago",
    updatedLabel: "2 days ago",
    iocCount: 4,
  },
  {
    id: "inv-1021",
    name: "Anomalous DNS query volume — subnet 10.4.0.0/22",
    status: "open",
    severity: "medium",
    owner: "Unassigned",
    openedLabel: "1 week ago",
    updatedLabel: "1 week ago",
    iocCount: 2,
  },
];
