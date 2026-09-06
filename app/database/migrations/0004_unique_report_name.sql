-- 0004_unique_report_name.sql
--
-- MAX-21B-2 / F2 (MAX-21A Forensic Reliability Audit, HIGH):
-- "Concurrent duplicate investigation creation / TOCTOU race".
--
-- app.analyzer.analyze_report previously decided whether to create a
-- new investigation by calling
-- InvestigationRepository.exists_by_report_name() and then, much
-- later (after IOC extraction / TI enrichment / risk scoring),
-- calling InvestigationRepository.save(). Those two operations are
-- not atomic: two concurrent analyze_report() calls for the same
-- report file can both observe exists=False and both proceed to
-- INSERT, producing two investigations for what the application
-- intends to be a single, deduplicated report.
--
-- The only way to close this race is to make the *database* refuse
-- the second insert, so this migration adds a UNIQUE constraint on
-- investigations.report_name. app/database/repository.py's save()
-- now catches the resulting sqlite3.IntegrityError and resolves to
-- the already-persisted row (see InvestigationRepository.save's
-- updated docstring) instead of letting the second writer crash.
--
-- Existing-data safety (audit section 8):
--
-- Before this migration, the repository and schema placed no
-- uniqueness constraint on report_name at all -- app.analyzer's
-- exists_by_report_name()/save() dedup logic was the *only* thing
-- discouraging duplicates, and it is exactly this logic that F2
-- shows can race. So a database that predates this migration can
-- legitimately already contain multiple investigations that share a
-- report_name (either from a prior F2 race, or from direct
-- repository use that never went through analyze_report's dedup
-- check at all -- both are real, already-persisted investigations,
-- not corrupt data).
--
-- A UNIQUE constraint cannot be added directly on top of existing
-- duplicate values, and per audit section 8 this migration must not
-- silently delete or merge any investigation to make room for it.
-- So, before creating the constraint, this migration:
--
--   1. Finds every report_name with more than one row.
--   2. Leaves the newest row (highest id) of each duplicate group
--      under its original report_name -- this is the row
--      analyze_report's pre-existing "return the latest match"
--      semantics (InvestigationRepository.find_by_report_name is
--      ordered newest-first) would have surfaced anyway.
--   3. Renames every *older* duplicate in the group by appending a
--      deterministic, human-readable disambiguating suffix
--      (" (duplicate id=<id>)") to its report_name. The row, its id,
--      and every other column are otherwise untouched -- nothing is
--      deleted or merged. This is intentionally the smallest change
--      that allows the constraint to be added at all: it does not
--      attempt to guess which duplicate is "correct".
--
-- On a database with no duplicates (the expected case for every
-- database created at or after F2 is fixed in application code),
-- steps 1-3 match zero rows and are a no-op.

UPDATE investigations
SET report_name = report_name || ' (duplicate id=' || id || ')'
WHERE id IN (
    SELECT older.id
    FROM investigations AS older
    WHERE EXISTS (
        SELECT 1
        FROM investigations AS newer
        WHERE newer.report_name = older.report_name
          AND newer.id > older.id
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_investigations_report_name_unique
    ON investigations (report_name);
