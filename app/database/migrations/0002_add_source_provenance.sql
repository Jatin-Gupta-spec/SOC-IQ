-- 0002_add_source_provenance.sql
--
-- SOC-IQ Phase A4-P1 -- Evidence Provenance & Investigation Integrity.
--
-- Adds the source report's integrity identity to the `investigations`
-- table: the SHA-256 hex digest of the exact bytes analyzed, and their
-- size in bytes. Both columns are nullable and additive:
--
--   - Every row written before this migration (a "legacy" investigation)
--     gets NULL in both new columns via SQLite's standard ADD COLUMN
--     semantics -- no backfill, no fabricated hash. `None` in
--     `Investigation.source_sha256` means honestly "this hash was
--     never calculated", per app/database/models.py.
--   - Every row written by app.analyzer.analyze_report after this
--     migration populates both columns from
--     app.extractor.compute_source_provenance().
--
-- No existing column is altered, renamed, or dropped. No existing data
-- is rewritten. This migration is additive-only, consistent with
-- 0001_initial.sql's own "do not alter/destroy existing data" contract.

ALTER TABLE investigations ADD COLUMN source_sha256 TEXT NULL;
ALTER TABLE investigations ADD COLUMN source_size_bytes INTEGER NULL;
