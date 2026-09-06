-- 0001_initial.sql
--
-- Establishes the current production schema (the `investigations`
-- table, as created directly by InvestigationRepository prior to the
-- introduction of the migration runner) as migration version 1.
--
-- This migration is deliberately idempotent (CREATE TABLE IF NOT
-- EXISTS) because it must run safely against two different starting
-- states:
--
--   1. A brand-new database: no tables exist yet. This migration
--      creates `investigations` from nothing.
--
--   2. An existing database created before the migration runner
--      existed: `investigations` is already present (with data),
--      `schema_version` is absent. This migration is a no-op against
--      the existing table -- it creates nothing, alters nothing, and
--      destroys nothing -- while still allowing the runner to record
--      that the database is now at version 1.
--
-- Do not add columns, tables, constraints, or indexes to this file
-- that do not already exist in the shipped schema. Future schema
-- changes belong in a new, separately numbered migration file.

CREATE TABLE IF NOT EXISTS investigations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_name TEXT NOT NULL,
    analyzed_at TEXT NOT NULL,
    status TEXT NOT NULL,
    iocs TEXT NOT NULL,
    threat_intelligence TEXT NOT NULL,
    risk_score INTEGER NOT NULL,
    severity TEXT NOT NULL,
    confidence REAL NOT NULL,
    ioc_score INTEGER NOT NULL,
    threat_intel_score INTEGER NOT NULL,
    cve_score INTEGER NOT NULL
);
