/**
 * Reports mock domain data (Phase 4G-2 Part 3, §13/§15/§16).
 */

export type ReportStatus = "generated" | "generating" | "failed";
export type ReportType = "investigation_summary" | "ioc_export" | "risk_snapshot";

export interface ReportRecord {
  readonly id: string;
  readonly title: string;
  readonly type: ReportType;
  readonly status: ReportStatus;
  readonly createdLabel: string;
  readonly investigationId?: string;
}

export const REPORT_TYPE_LABELS: Record<ReportType, string> = {
  investigation_summary: "Investigation Summary",
  ioc_export: "IOC Export",
  risk_snapshot: "Risk Snapshot",
};

export const mockReports: ReportRecord[] = [
  { id: "report-0001", title: "Outbound beacon to unknown domain — summary", type: "investigation_summary", status: "generated", createdLabel: "3 hours ago", investigationId: "inv-1038" },
  { id: "report-0002", title: "Weekly IOC export", type: "ioc_export", status: "generated", createdLabel: "yesterday" },
  { id: "report-0003", title: "Suspicious PowerShell chain — draft summary", type: "investigation_summary", status: "generating", createdLabel: "12 minutes ago", investigationId: "inv-1042" },
  { id: "report-0004", title: "Q3 risk snapshot", type: "risk_snapshot", status: "generated", createdLabel: "5 days ago" },
  { id: "report-0005", title: "Phishing report distribution — export", type: "ioc_export", status: "failed", createdLabel: "1 hour ago", investigationId: "inv-1041" },
];
