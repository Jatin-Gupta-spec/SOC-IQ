/**
 * Investigation Workspace — IOC tab content — Phase 4J-6 Part 2A,
 * extended in Part 2B with client-side search/filter and in Part 2C
 * with row selection + a focused single-IOC detail presentation.
 *
 * The IOC workspace's real content, rendered when the workspace's
 * "IOCs" tab is selected (`InvestigationWorkspacePage.tsx`). Built
 * exclusively from the already-normalized `iocsByType`
 * (`normalizeInvestigationWorkspace()`, Phase 4J-5) -- no second
 * fetch, no `runCommand()`, no re-normalization, and no IOC-type
 * vocabulary beyond the real ten `PersistedIocType` categories the
 * normalization layer already groups by (task brief §7).
 *
 * Unlike the compact Part 1D `InvestigationOverviewIOC` summary (which
 * this component deliberately does not duplicate, per task brief §8),
 * this is the detailed IOC workspace: a fuller per-category summary
 * (all ten real categories, not just the six headline ones) plus a
 * real indicator table (`DataTable`, task brief §11) listing every
 * persisted value with its real type. Part 2C adds the ability to
 * select a row and inspect it in a focused `IocDetail` panel built
 * only from fields the normalized `IocRow` actually has (`type`,
 * `value`, and `tiState` when non-`null`) -- it still does not
 * implement enrichment actions, correlations, editing/deletion, bulk
 * actions, or live/fetched Threat Intel detail (VirusTotal lookups,
 * raw provider payloads); the detail panel is a presentation of
 * already-loaded data only (task brief §3/§19).
 *
 * # Empty vs. unavailable vs. filtered-empty (task brief §9/§10, Part
 * 2B §10)
 *
 * - `iocsByType === null` -- no successful `get_iocs` response has
 *   been normalized (missing/failed data): renders "IOC data
 *   unavailable", never fabricated zero counts or an empty table, and
 *   never renders the search/filter toolbar (Part 2B §19 -- controls
 *   only appear once a real dataset exists).
 * - `iocsByType` is a real object with every category genuinely empty
 *   (real total of `0`): renders an honest "No IOCs found" empty
 *   state -- a successful response, not an error -- and likewise no
 *   toolbar (there is nothing to search/filter).
 * - `iocsByType` contains real indicators: renders real per-category
 *   counts (including real zero categories), the search/filter
 *   toolbar, and a table of every real indicator value, each with its
 *   real type.
 * - The dataset is real and non-empty, but the current search/type
 *   filter combination matches none of it: renders a distinct "No
 *   IOCs match your filters" state (never confused with the two
 *   states above) alongside a "Clear filters" action -- the toolbar
 *   itself stays visible so the person can adjust or clear their
 *   filters directly.
 *
 * # Part 2B scope (search/filter/table usability)
 *
 * Search and the type filter are both local, derived UI state --
 * plain `useState` over the same `rows` this component already builds
 * from `iocsByType`; see task brief §5/§11/§18. Neither:
 *
 * - calls the backend or `runCommand()` (no second data-fetching
 *   mechanism, task brief §2/§5/§7);
 * - mutates `iocsByType`, `rows`, or any per-type array (`rows` is
 *   built fresh from the normalized data on every render and only
 *   ever `.filter()`ed -- never `.sort()`ed or mutated in place,
 *   task brief §11);
 * - invents IOC values, metadata, or type categories -- the type
 *   filter's options are derived from the types actually present in
 *   `rows`, not the full ten-member `PERSISTED_IOC_TYPES` union,
 *   so a category with zero indicators never appears as a selectable
 *   (and always-empty) filter option (task brief §6).
 *
 * Local filter state resets whenever `data.investigationId` changes
 * (derived during render, not an effect) so a stale search/filter
 * from a previously viewed investigation can never leak into a
 * different one (task brief §18/§21) -- this component instance is
 * not remounted on investigation switch (`InvestigationWorkspacePage`
 * renders it in the same tree position across investigations), so
 * without this reset the local `search`/`typeFilter` state would
 * otherwise persist across `useInvestigation()`'s own investigation
 * switch. This is a plain reset of this component's own local
 * display state, not a second investigation lifecycle mechanism --
 * `useInvestigation()` remains the sole source of investigation data
 * and its own switching/staleness handling (task brief §18).
 *
 * Sorting is intentionally not added: `DataTable` (`../components`)
 * has no existing sort capability to reuse, and the task brief is
 * explicit that Part 2B should not introduce one from scratch (task
 * brief §12).
 *
 * # Risk Significance badge (PD-08-P4.2)
 *
 * Adds a "Risk Significance" column to the indicator table, and a
 * matching field to the `IocDetail` panel, presenting the real
 * per-category `data.iocSignificance` value (PD-08-P3's additive
 * `get_iocs` field, already carried unchanged onto
 * `InvestigationWorkspaceData` as of PD-08-P4.1 -- see
 * `InvestigationWorkspaceIocSignificance`'s own doc comment,
 * `investigationWorkspaceModel.ts`) via the existing `StatusBadge`
 * primitive, the same one already used for this table's Type column
 * and the detail panel's Threat Intelligence field. No new fetch, no
 * new primitive, and no client-side scoring: the label is the
 * backend's own `significance` string, unchanged, and the tone
 * mapping (`significanceTone`, below) only bands that same real
 * string into an existing `StatusTone`, mirroring `severityTone`'s
 * own low/medium/high convention (`InvestigationHeaderCard.tsx`). A
 * row whose category has no `iocSignificance` entry (an older backend
 * response predating PD-08-P3) renders an honest empty cell -- never
 * a fabricated "Unknown" badge.
 */

import { useEffect, useMemo, useRef, useState, type ReactElement } from "react";
import { Card } from "../components/Card";
import { MetricCard } from "../components/MetricCard";
import { InfoNote } from "../components/InfoNote";
import { StatusBadge, type StatusTone } from "../components/StatusBadge";
import { DataTable, type DataTableColumn } from "../components/DataTable";
import { PERSISTED_IOC_TYPES, type IocTypeSignificance, type PersistedIocType, type TiState } from "../../shared/api/types";
import type {
  InvestigationWorkspaceData,
  InvestigationWorkspaceIndicator,
  InvestigationWorkspaceIocsByType,
  InvestigationWorkspaceIocSignificance,
} from "./investigationWorkspaceModel";
import "./InvestigationIocWorkspace.css";

export interface InvestigationIocWorkspaceProps {
  readonly data: InvestigationWorkspaceData;
}

/** Human-readable, singular labels for all ten real `PersistedIocType`
 * values -- used as the table's per-row "Type" badge, and (Part 2B)
 * as the type filter's option labels. A superset of the six headline
 * groups the Part 1D summary and Overview summary already use
 * (`InvestigationOverviewIOC.tsx`/`InvestigationOverviewSummary.tsx`),
 * extended to cover the two categories those compact summaries
 * intentionally fold into the total without a dedicated metric
 * (`windows_file_paths`/`windows_registry_keys`) -- no category is
 * invented beyond the real, normalized union. */
const IOC_TYPE_LABELS: Record<PersistedIocType, string> = {
  ipv4: "IP Address",
  domains: "Domain",
  urls: "URL",
  emails: "Email",
  md5: "MD5 Hash",
  sha1: "SHA1 Hash",
  sha256: "SHA256 Hash",
  cves: "CVE",
  windows_file_paths: "Windows File Path",
  windows_registry_keys: "Windows Registry Key",
};

/** The workspace's fuller per-category summary -- the same six
 * headline groups the existing Overview summaries already establish,
 * plus the two Windows categories they fold into the total, so this
 * detailed view accounts for all ten real categories individually
 * (task brief §8's "more useful detailed context") without inventing
 * a second grouping scheme for the six shared ones. */
const IOC_WORKSPACE_GROUPS: ReadonlyArray<{
  readonly label: string;
  readonly types: readonly PersistedIocType[];
}> = [
  { label: "IPs", types: ["ipv4"] },
  { label: "Domains", types: ["domains"] },
  { label: "URLs", types: ["urls"] },
  { label: "Emails", types: ["emails"] },
  { label: "Hashes", types: ["md5", "sha1", "sha256"] },
  { label: "CVEs", types: ["cves"] },
  { label: "Windows File Paths", types: ["windows_file_paths"] },
  { label: "Windows Registry Keys", types: ["windows_registry_keys"] },
];

function countForTypes(
  iocsByType: InvestigationWorkspaceIocsByType,
  types: readonly PersistedIocType[],
): number {
  return types.reduce((sum, type) => sum + (iocsByType[type]?.length ?? 0), 0);
}

function totalIocCount(iocsByType: InvestigationWorkspaceIocsByType): number {
  return countForTypes(iocsByType, PERSISTED_IOC_TYPES);
}

interface IocRow {
  readonly id: string;
  readonly type: PersistedIocType;
  readonly value: string;
  /** Carried over verbatim from the already-normalized
   * `InvestigationWorkspaceIndicator` (task brief §7's detail
   * presentation may only use data already in the normalized
   * workspace) -- `null` when this exact indicator has no TI
   * classification yet, distinct from all six real `TiState` values. */
  readonly tiState: InvestigationWorkspaceIndicator["tiState"];
  /** The real PD-08-P3 `IocTypeSignificance` for this row's
   * *category* (`data.iocSignificance[row.type]`, PD-08-P4.2) --
   * every row of the same `type` shares the exact same value, since
   * significance is a pure function of the category, never of an
   * individual indicator (see `IocTypeSignificance`'s own doc
   * comment, `shared/api/types.ts`). `null` when the normalized
   * `iocSignificance` map has no entry for this row's type -- an
   * older backend response predating PD-08-P3, or a category this
   * investigation doesn't include -- never fabricated as a
   * synthesized "Unknown" value. */
  readonly significance: IocTypeSignificance | null;
}

/** Flattens the normalized, per-type indicator arrays into one real
 * row per persisted indicator, in the model's own deterministic order
 * (`PERSISTED_IOC_TYPES` order, then each type's own backend array
 * order) -- no reordering, deduplication, or reinterpretation of the
 * underlying values (task brief §13). `iocSignificance` (PD-08-P4.2)
 * is the same `data.iocSignificance` already carried by
 * `InvestigationWorkspaceData` -- looked up per category here, never
 * refetched, recalculated, or duplicated from
 * `RiskScoringEngine.IOC_WEIGHTS`. */
function buildRows(
  iocsByType: InvestigationWorkspaceIocsByType,
  iocSignificance: InvestigationWorkspaceIocSignificance | null,
): readonly IocRow[] {
  const rows: IocRow[] = [];
  for (const type of PERSISTED_IOC_TYPES) {
    const indicators = iocsByType[type];
    if (indicators === undefined) {
      continue;
    }
    const significance = iocSignificance?.[type] ?? null;
    indicators.forEach((indicator, index) => {
      rows.push({
        id: `${type}:${index}:${indicator.value}`,
        type,
        value: indicator.value,
        tiState: indicator.tiState,
        significance,
      });
    });
  }
  return rows;
}

/** The distinct `PersistedIocType`s actually present in `rows`, in
 * canonical `PERSISTED_IOC_TYPES` order -- the type filter's real,
 * non-empty option set (Part 2B §6: "the options MUST come from the
 * existing normalized IOC vocabulary" / "only real normalized
 * categories are offered"). A type with zero indicators never appears
 * here, so the filter can never offer a selection that would always
 * be empty. */
function availableTypes(rows: readonly IocRow[]): readonly PersistedIocType[] {
  const present = new Set(rows.map((row) => row.type));
  return PERSISTED_IOC_TYPES.filter((type) => present.has(type));
}

const TYPE_FILTER_ALL = "all";
type TypeFilterValue = PersistedIocType | typeof TYPE_FILTER_ALL;

/** Case-insensitive substring match against an IOC's real value only
 * -- never against its type label or any other synthesized text
 * (Part 2B §5). */
function matchesSearch(row: IocRow, normalizedQuery: string): boolean {
  return normalizedQuery === "" || row.value.toLowerCase().includes(normalizedQuery);
}

function matchesType(row: IocRow, typeFilter: TypeFilterValue): boolean {
  return typeFilter === TYPE_FILTER_ALL || row.type === typeFilter;
}

/** Tone mapping for the real PD-08-P3 `ioc_type_significance()`
 * vocabulary (`app/services/ioc_significance.py`: `"High"`,
 * `"Medium"`, `"Low"`, `"Informational"`) -- matched case-insensitively
 * for the same reason `severityTone` (`InvestigationHeaderCard.tsx`)
 * already is: `significance` is a plain backend string, not a
 * constrained enum. Mirrors that function's own low/medium/high tone
 * choices (success/warning/error) so "significant" reads the same way
 * across this workspace, plus a neutral tone for `"Informational"`,
 * the one significance band `severityTone` has no equivalent for.
 * Anything unrecognized still renders with its own real label text, at
 * a neutral tone, rather than being hidden or guessed at (task brief
 * §17: no invented categories). Kept as a local, per-file map rather
 * than a shared import, matching this file's own `TI_STATE_TONE`
 * convention above. */
const IOC_SIGNIFICANCE_TONE: Record<string, StatusTone> = {
  informational: "neutral",
  low: "success",
  medium: "warning",
  high: "error",
};

function significanceTone(significance: string): StatusTone {
  return IOC_SIGNIFICANCE_TONE[significance.trim().toLowerCase()] ?? "neutral";
}

/** Renders a row's Risk Significance cell/field: the real badge when
 * `data.iocSignificance` has an entry for this row's category, or
 * `null` (an honest empty cell, task brief §7) when it doesn't --
 * never a fabricated "Unknown"/"N/A" badge for a category the
 * normalized data genuinely has no significance entry for. */
function renderSignificance(significance: IocTypeSignificance | null): ReactElement | null {
  if (significance === null) {
    return null;
  }
  return <StatusBadge label={significance.significance} tone={significanceTone(significance.significance)} />;
}

const TABLE_COLUMNS: readonly DataTableColumn<IocRow>[] = [
  {
    key: "type",
    header: "Type",
    render: (row) => <StatusBadge label={IOC_TYPE_LABELS[row.type]} tone="neutral" />,
  },
  {
    key: "value",
    header: "Value",
    render: (row) => <span className="investigation-ioc-workspace__value">{row.value}</span>,
  },
  {
    key: "significance",
    header: "Risk Significance",
    render: (row) => renderSignificance(row.significance),
  },
];

/** Same real `TiState` vocabulary/tone grouping already established by
 * `InvestigationOverviewThreatIntel.tsx`/`ThreatIntelPage.tsx` --
 * reused by name rather than redefined with different labels, per the
 * project's existing per-file convention of a local copy of this
 * small, stable map rather than a shared import. */
const TI_STATE_LABELS: Record<TiState, string> = {
  enriched: "Enriched",
  not_enriched: "Not enriched",
  no_api_key: "No API key",
  provider_error: "Provider error",
  incomplete_check: "Incomplete check",
  unsupported_type: "Unsupported type",
};

const TI_STATE_TONE: Record<TiState, StatusTone> = {
  enriched: "success",
  not_enriched: "neutral",
  no_api_key: "warning",
  provider_error: "error",
  incomplete_check: "warning",
  unsupported_type: "neutral",
};

/** Accessible name for a selectable IOC row -- read by assistive tech
 * in place of the row's own two-cell content (task brief §10). */
function rowAriaLabel(row: IocRow): string {
  return `${IOC_TYPE_LABELS[row.type]}: ${row.value}. View details.`;
}

interface IocDetailProps {
  readonly row: IocRow;
  readonly onClose: () => void;
}

/** How long the post-copy "Copied"/"Copy failed" feedback stays
 * visible before reverting to the button's resting label. A plain
 * local constant -- the project has no existing shared
 * toast/notification duration token to reuse for this (task brief
 * §8's "do not invent a global notification system"). */
const COPY_FEEDBACK_MS = 2000;

type CopyStatus = "idle" | "copied" | "error";

/**
 * Focused single-IOC detail presentation (task brief §7, polished in
 * Part 2D). Renders only fields that genuinely exist on the
 * already-normalized `IocRow` -- `type` and `value` always (the only
 * two fields every persisted indicator has), plus `tiState` only when
 * it is a real, non-`null` classification (task brief §8: never
 * converting a missing/not-yet-classified value into a fabricated
 * "Unknown"/"N/A" row). No confidence, reputation, first/last-seen,
 * source, or provider fields are ever rendered -- the normalized
 * model has none of those, and none are invented here.
 *
 * Part 2D adds a local copy-to-clipboard action for the value field
 * (task brief §7 of Part 2D) -- there was no existing
 * copy-to-clipboard pattern anywhere in the project to reuse, so this
 * is a small, local one rather than a new shared/global abstraction.
 */
function IocDetail({ row, onClose }: IocDetailProps): ReactElement {
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const [copyStatus, setCopyStatus] = useState<CopyStatus>("idle");
  const copyTimeoutRef = useRef<number | null>(null);

  // Moves focus into the detail panel's Close control whenever a new
  // IOC becomes selected, so keyboard users land somewhere
  // understandable inside the newly-opened detail (task brief §11) --
  // the smallest accessible option available given the project has no
  // existing global focus-management system to reuse (task brief
  // §11's "do not introduce a custom global focus-management
  // system"). Keyed on `row.id` so this only fires on an actual
  // selection change, not on every unrelated re-render.
  useEffect(() => {
    closeButtonRef.current?.focus();
  }, [row.id]);

  // Any in-flight "Copied"/"Copy failed" feedback belongs to whichever
  // IOC was selected when the copy happened -- reset it (and clear
  // its pending timeout) the moment selection changes, so a stale
  // "Copied" message can never appear to describe a different value.
  useEffect(() => {
    setCopyStatus("idle");
    return () => {
      if (copyTimeoutRef.current !== null) {
        window.clearTimeout(copyTimeoutRef.current);
        copyTimeoutRef.current = null;
      }
    };
  }, [row.id]);

  function handleCopy(): void {
    // `navigator.clipboard` may be unavailable (older/unsupported
    // environments) -- guarded rather than assumed, per task brief §7
    // ("must not require backend access", not "must always succeed").
    const clipboard = typeof navigator !== "undefined" ? navigator.clipboard : undefined;
    if (clipboard === undefined) {
      reportCopyResult("error");
      return;
    }
    clipboard.writeText(row.value).then(
      () => reportCopyResult("copied"),
      () => reportCopyResult("error"),
    );
  }

  function reportCopyResult(status: CopyStatus): void {
    if (copyTimeoutRef.current !== null) {
      window.clearTimeout(copyTimeoutRef.current);
    }
    setCopyStatus(status);
    copyTimeoutRef.current = window.setTimeout(() => {
      setCopyStatus("idle");
      copyTimeoutRef.current = null;
    }, COPY_FEEDBACK_MS);
  }

  return (
    <Card title="IOC Detail" className="investigation-ioc-workspace__detail transition-fade">
      <dl className="investigation-ioc-workspace__detail-fields">
        <div className="investigation-ioc-workspace__detail-field">
          <dt>Type</dt>
          <dd>
            <StatusBadge label={IOC_TYPE_LABELS[row.type]} tone="neutral" />
          </dd>
        </div>
        <div className="investigation-ioc-workspace__detail-field">
          <dt>Value</dt>
          <dd className="investigation-ioc-workspace__detail-value-row">
            <span className="investigation-ioc-workspace__detail-value">{row.value}</span>
            <button
              type="button"
              className="investigation-ioc-workspace__copy"
              onClick={handleCopy}
              aria-label="Copy IOC value"
            >
              Copy
            </button>
            {/* Text-based feedback (never color-only, task brief §8):
                a real word announced via `role="status"` so keyboard
                and screen-reader users both learn the result, not
                just sighted users watching a color flash. Empty when
                idle so nothing is announced before a copy happens. */}
            <span className="investigation-ioc-workspace__copy-status" role="status" aria-live="polite">
              {copyStatus === "copied" ? "Copied" : copyStatus === "error" ? "Copy failed" : ""}
            </span>
          </dd>
        </div>
        {row.tiState !== null ? (
          <div className="investigation-ioc-workspace__detail-field">
            <dt>Threat Intelligence</dt>
            <dd>
              <StatusBadge label={TI_STATE_LABELS[row.tiState]} tone={TI_STATE_TONE[row.tiState]} />
            </dd>
          </div>
        ) : null}
        {row.significance !== null ? (
          <div className="investigation-ioc-workspace__detail-field">
            <dt>Risk Significance</dt>
            <dd>{renderSignificance(row.significance)}</dd>
          </div>
        ) : null}
      </dl>
      <button
        ref={closeButtonRef}
        type="button"
        className="investigation-ioc-workspace__detail-close"
        onClick={onClose}
      >
        Close
      </button>
    </Card>
  );
}

/**
 * Renders the workspace's real IOC tab content. Callers only render
 * this once `InvestigationWorkspaceData` actually exists
 * (`useInvestigation()`'s `"success"`/`"partial"` states) and the IOCs
 * tab is selected -- matches every other workspace region's
 * convention.
 */
export function InvestigationIocWorkspace({ data }: InvestigationIocWorkspaceProps): ReactElement {
  const { iocsByType, investigationId } = data;
  // `data.iocSignificance` is typed optional purely for the
  // pre-existing-literal compatibility reason its own doc comment
  // gives (`investigationWorkspaceModel.ts`) -- normalized to `null`
  // here, the same treatment `iocsByType`'s own nullability already
  // gets, rather than threading `| undefined` into `buildRows`.
  const iocSignificance = data.iocSignificance ?? null;

  // Hooks are called unconditionally, before any of the early
  // availability/empty returns below, per the Rules of Hooks.
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<TypeFilterValue>(TYPE_FILTER_ALL);
  // The selected IOC's stable row id (task brief §18: selection stores
  // a stable identifier, not a mutable reference into `iocsByType`).
  // `null` means no row is currently selected.
  const [selectedIocId, setSelectedIocId] = useState<string | null>(null);

  // Resets local search/filter/selection display state the moment the
  // investigation changes, derived during render rather than via an
  // effect (the React-recommended pattern for "reset state when a
  // prop changes") -- see the module comment's "Local filter state
  // resets" note. `lastInvestigationId` intentionally lives beside
  // `search`/`typeFilter`/`selectedIocId` as plain component state,
  // not a new investigation lifecycle mechanism.
  const [lastInvestigationId, setLastInvestigationId] = useState(investigationId);
  if (investigationId !== lastInvestigationId) {
    setLastInvestigationId(investigationId);
    setSearch("");
    setTypeFilter(TYPE_FILTER_ALL);
    setSelectedIocId(null);
  }

  // `rows` must be computed unconditionally too (it feeds the memo
  // below, and hooks can't be called after an early return) --
  // `iocsByType` is treated as `{}` only for this local computation
  // when unavailable; the actual unavailable/empty rendering below
  // still checks the real `iocsByType`/`total` values, so this
  // substitution never leaks into what's displayed.
  const rows = useMemo(() => buildRows(iocsByType ?? {}, iocSignificance), [iocsByType, iocSignificance]);

  const filteredRows = useMemo(() => {
    const normalizedQuery = search.trim().toLowerCase();
    return rows.filter((row) => matchesType(row, typeFilter) && matchesSearch(row, normalizedQuery));
  }, [rows, typeFilter, search]);

  const typeOptions = useMemo(() => availableTypes(rows), [rows]);

  // Derived, never stored: the selected row is looked up fresh from
  // `filteredRows` on every render (task brief §6), so changing the
  // search/type filter such that the previously-selected IOC no
  // longer matches automatically un-selects it -- there is no stale
  // detail view to separately guard against, because a row id that
  // has fallen out of `filteredRows` simply stops resolving to
  // anything here.
  const selectedRow = selectedIocId === null ? null : (filteredRows.find((row) => row.id === selectedIocId) ?? null);

  function handleRowActivate(row: IocRow): void {
    // Clicking/activating the already-selected row toggles the detail
    // panel closed again, matching the explicit close control's own
    // effect (task brief §9) without requiring a second click target.
    setSelectedIocId((current) => (current === row.id ? null : row.id));
  }

  function closeDetail(): void {
    setSelectedIocId(null);
  }

  if (iocsByType === null) {
    return (
      <Card title="IOC Workspace" className="investigation-ioc-workspace">
        <InfoNote>IOC data unavailable for this investigation.</InfoNote>
      </Card>
    );
  }

  const total = totalIocCount(iocsByType);

  if (total === 0) {
    return (
      <Card title="IOC Workspace" className="investigation-ioc-workspace">
        <InfoNote>No IOCs found for this investigation.</InfoNote>
      </Card>
    );
  }

  const hasActiveFilter = search.trim() !== "" || typeFilter !== TYPE_FILTER_ALL;

  function resetFilters(): void {
    setSearch("");
    setTypeFilter(TYPE_FILTER_ALL);
  }

  return (
    <div className="investigation-ioc-workspace">
      <Card title="IOC Summary" className="investigation-ioc-workspace__summary">
        <div className="investigation-ioc-workspace__metrics">
          <MetricCard label="Total" value={String(total)} />
          {IOC_WORKSPACE_GROUPS.map((group) => (
            <MetricCard key={group.label} label={group.label} value={String(countForTypes(iocsByType, group.types))} />
          ))}
        </div>
      </Card>
      <Card title="Indicators" className="investigation-ioc-workspace__table">
        <div className="investigation-ioc-workspace__toolbar">
          <div className="investigation-ioc-workspace__field">
            <label htmlFor="investigation-ioc-search" className="investigation-ioc-workspace__field-label">
              Search
            </label>
            <input
              id="investigation-ioc-search"
              type="search"
              className="investigation-ioc-workspace__search-input"
              placeholder="Search IOCs..."
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>
          <div className="investigation-ioc-workspace__field">
            <label htmlFor="investigation-ioc-type-filter" className="investigation-ioc-workspace__field-label">
              Type
            </label>
            <select
              id="investigation-ioc-type-filter"
              className="investigation-ioc-workspace__type-filter"
              value={typeFilter}
              onChange={(event) => setTypeFilter(event.target.value as TypeFilterValue)}
            >
              <option value={TYPE_FILTER_ALL}>All types</option>
              {typeOptions.map((type) => (
                <option key={type} value={type}>
                  {IOC_TYPE_LABELS[type]}
                </option>
              ))}
            </select>
          </div>
          {hasActiveFilter ? (
            <button type="button" className="investigation-ioc-workspace__reset" onClick={resetFilters}>
              Clear filters
            </button>
          ) : null}
          <span className="investigation-ioc-workspace__count">
            Showing {filteredRows.length} of {total} IOCs
          </span>
        </div>
        {filteredRows.length === 0 ? (
          <div className="investigation-ioc-workspace__no-matches">
            <InfoNote>No IOCs match your filters.</InfoNote>
            <button type="button" className="investigation-ioc-workspace__reset" onClick={resetFilters}>
              Clear filters
            </button>
          </div>
        ) : (
          <DataTable
            caption="Indicators of compromise for this investigation"
            columns={TABLE_COLUMNS}
            rows={filteredRows}
            getRowId={(row) => row.id}
            onRowActivate={handleRowActivate}
            isRowSelected={(row) => row.id === selectedIocId}
            getRowAriaLabel={rowAriaLabel}
          />
        )}
      </Card>
      {selectedRow !== null ? <IocDetail row={selectedRow} onClose={closeDetail} /> : null}
    </div>
  );
}
