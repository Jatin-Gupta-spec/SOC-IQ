import { useMemo, useState, type KeyboardEvent, type ReactElement, type ReactNode } from "react";
import "./DataTable.css";

export interface DataTableColumn<Row> {
  readonly key: string;
  readonly header: string;
  readonly render: (row: Row) => ReactNode;
  /**
   * MAX10-F-01: opt-in column sort. When `true`, the column header
   * renders as a real `<button>` -- native semantics, so keyboard
   * activation (Enter/Space) and focus come for free, no ARIA
   * reimplementation needed -- that toggles this column's sort
   * direction on click/activation. Every existing consumer
   * (Dashboard, IOC Explorer, Reports, Risk) omits this, so those
   * tables render exactly as before.
   */
  readonly sortable?: boolean;
  /**
   * Comparable value backing `sortable`. Required whenever `sortable`
   * is `true` -- `render` returns a `ReactNode`, which isn't itself
   * comparable, so a sortable column must also supply the plain
   * value behind that rendering. Return `null` for "no value" rows
   * (e.g. an unscored investigation's risk score); `null` values
   * always sort to the end of the list, in either direction.
   */
  readonly sortValue?: (row: Row) => string | number | null;
}

type SortDirection = "asc" | "desc";

interface SortState {
  readonly key: string;
  readonly direction: SortDirection;
}

/** Numbers compared numerically, everything else as a locale-aware
 * string compare. Deliberately does not handle `null` -- that's
 * `compareSortValues`'s job, so the direction multiplier below is
 * never applied to the null-ordering decision (see its own comment). */
function compareNonNullSortValues(a: string | number, b: string | number): number {
  if (typeof a === "number" && typeof b === "number") {
    return a - b;
  }
  return String(a).localeCompare(String(b));
}

/** `null` always sorts last, in *either* direction -- an unscored
 * investigation's row never jumps to the top just because the analyst
 * flipped a column to descending. This is why the direction multiplier
 * (`directionMultiplier`, applied only inside the non-null branch) is
 * kept separate from the null-ordering decision here rather than
 * wrapping this whole function. */
function compareSortValues(a: string | number | null, b: string | number | null, directionMultiplier: 1 | -1): number {
  if (a === null && b === null) {
    return 0;
  }
  if (a === null) {
    return 1;
  }
  if (b === null) {
    return -1;
  }
  return compareNonNullSortValues(a, b) * directionMultiplier;
}

export interface DataTableProps<Row> {
  readonly caption: string;
  readonly columns: readonly DataTableColumn<Row>[];
  readonly rows: readonly Row[];
  readonly getRowId: (row: Row) => string;
  /**
   * Opt-in row interaction (Phase 4J-6 Part 2C, task brief §10). When
   * provided, every row becomes a focusable, keyboard-activatable
   * control (`tabIndex`, click + Enter/Space handling) rather than a
   * plain `<tr>` -- reused as-is by any future caller that needs
   * selectable rows, rather than each page reimplementing row
   * interactivity. Omitted entirely by every other current consumer
   * (Investigations, IOC Explorer, Reports, Risk, Dashboard), so this
   * table renders exactly as before wherever it isn't passed.
   */
  readonly onRowActivate?: (row: Row) => void;
  /** Whether `row` is the current selection -- drives `aria-selected`
   * and the row's selected styling. Only meaningful alongside
   * `onRowActivate`. */
  readonly isRowSelected?: (row: Row) => boolean;
  /** Accessible name for an interactive row, read by assistive tech in
   * place of the row's own cell-by-cell content. Only meaningful
   * alongside `onRowActivate`. */
  readonly getRowAriaLabel?: (row: Row) => string;
}

/**
 * Generic list/table primitive (Phase 4G-2 Part 3, §17/§20).
 *
 * A real `<table>` with a (visually-hidden) `<caption>` rather than a
 * div-grid, per §20's "tables/lists use appropriate semantics".
 * Shared by every page that shows a row-shaped collection
 * (Investigations, IOC Explorer, Reports) instead of each
 * reimplementing table markup.
 */
export function DataTable<Row>({
  caption,
  columns,
  rows,
  getRowId,
  onRowActivate,
  isRowSelected,
  getRowAriaLabel,
}: DataTableProps<Row>): ReactElement {
  const interactive = onRowActivate !== undefined;
  const [sortState, setSortState] = useState<SortState | null>(null);

  // Sorting is opt-in per column (`column.sortable`) and owned entirely
  // by `DataTable`, per MAX-9 2C's established "DataTable already owns
  // delegated state cleanly" pattern rather than introducing a second
  // state mechanism in each page. When no sortable column has been
  // activated yet, `sortedRows` is the exact same array reference as
  // `rows` -- zero behavioral change for every consumer that doesn't
  // opt in.
  const sortedRows = useMemo(() => {
    if (sortState === null) {
      return rows;
    }
    const column = columns.find((candidate) => candidate.key === sortState.key);
    if (column === undefined || column.sortValue === undefined) {
      return rows;
    }
    const sortValue = column.sortValue;
    const directionMultiplier: 1 | -1 = sortState.direction === "asc" ? 1 : -1;
    return [...rows].sort((a, b) => compareSortValues(sortValue(a), sortValue(b), directionMultiplier));
  }, [rows, sortState, columns]);

  function toggleSort(column: DataTableColumn<Row>): void {
    if (!column.sortable) {
      return;
    }
    setSortState((current) => {
      if (current === null || current.key !== column.key) {
        return { key: column.key, direction: "asc" };
      }
      return { key: column.key, direction: current.direction === "asc" ? "desc" : "asc" };
    });
  }

  function ariaSortFor(column: DataTableColumn<Row>): "ascending" | "descending" | "none" | undefined {
    if (!column.sortable) {
      return undefined;
    }
    if (sortState === null || sortState.key !== column.key) {
      return "none";
    }
    return sortState.direction === "asc" ? "ascending" : "descending";
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTableRowElement>, row: Row): void {
    if (event.key !== "Enter" && event.key !== " ") {
      return;
    }
    // Prevent the space key from also scrolling the page, matching
    // the standard button/row activation convention.
    event.preventDefault();
    onRowActivate?.(row);
  }

  return (
    // MAX-3 (Part 3/5): a dense table's header row (`white-space: nowrap`
    // per DataTable.css) can outgrow the page's available width at the
    // 1280px compact tier even though body cells wrap. Scoping the
    // horizontal scroll to this wrapper -- rather than the page --
    // keeps `PageLayout`'s page-level scroll vertical-only (task brief
    // §3/§11.4: "constrain scrolling ... local to the component that
    // needs it"). No visual change at widths where the table already
    // fits; this only activates when content genuinely requires it.
    <div className="data-table__scroll">
      <table className="data-table">
        <caption className="data-table__caption">{caption}</caption>
        <thead>
          <tr>
            {columns.map((column) =>
              column.sortable ? (
                <th key={column.key} scope="col" aria-sort={ariaSortFor(column)}>
                  <button type="button" className="data-table__sort-button" onClick={() => toggleSort(column)}>
                    {column.header}
                    <span className="data-table__sort-icon" aria-hidden="true">
                      {sortState?.key === column.key ? (sortState.direction === "asc" ? "▲" : "▼") : "⇅"}
                    </span>
                  </button>
                </th>
              ) : (
                <th key={column.key} scope="col">
                  {column.header}
                </th>
              ),
            )}
          </tr>
        </thead>
        <tbody>
          {sortedRows.map((row) => {
            const selected = interactive ? (isRowSelected?.(row) ?? false) : undefined;
            return (
              <tr
                key={getRowId(row)}
                className={selected ? "data-table__row data-table__row--selected" : interactive ? "data-table__row" : undefined}
                tabIndex={interactive ? 0 : undefined}
                aria-selected={interactive ? selected : undefined}
                aria-label={interactive ? getRowAriaLabel?.(row) : undefined}
                onClick={interactive ? () => onRowActivate?.(row) : undefined}
                onKeyDown={interactive ? (event) => handleKeyDown(event, row) : undefined}
              >
                {columns.map((column) => (
                  <td key={column.key}>{column.render(row)}</td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
