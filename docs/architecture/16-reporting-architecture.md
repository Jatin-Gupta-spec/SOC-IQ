# Reporting Architecture

**Status:** Documentation Foundation (Phase 4A).
**Related:** Master Plan §18, §1.7 (current-state file size), Master Plan §27
(Preserve/Redesign matrix).

## CURRENT STATE (CONFIRMED)

`app/reporting/` contains a builder/service pair plus five format exporters (json, csv,
markdown, html, pdf). `html_exporter.py` is **1,861 LOC** (CONFIRMED, wc -l), the largest
single file in the codebase by a wide margin — the next-largest file, `virustotal.py`, is
1,189 LOC. This matches baseline problem #12.

## TARGET STATE (PROPOSED)

- JSON/CSV/Markdown/PDF exporters: **preserved as-is**; each sits behind the same
  `export_report` command (see `docs/contracts/command-model.md`) regardless of which
  frontend technology calls it.
- HTML exporter: **redesigned internally only** — extracted to a template-driven approach
  (e.g. Jinja2 templates + a slim Python data-assembly layer), so the exporter's job becomes
  "assemble a context dict," not "hand-build a wall of HTML/CSS strings in Python." **Report
  output content is preserved**; only the implementation's shape changes. This is explicitly
  not a rewrite of what the report contains (Master Plan §18) — a regression on report
  content would be treated as a Phase 4L failure, not an acceptable side effect of the
  refactor.

## MIGRATION NOTES

The HTML exporter refactor is Phase 4L (Master Plan §26); its exit criterion is that
"existing report tests still pass" — meaning the current reporting test suite (part of the
542-test baseline) is the acceptance check for output-content preservation, not a new,
separately-written comparison.

## UNKNOWN / REQUIRES VERIFICATION

None outstanding — file sizes and exporter list were directly confirmed by source inspection.
