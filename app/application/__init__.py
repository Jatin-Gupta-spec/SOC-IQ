"""
Phase 4D application/command-handler layer.

This package is the first real API/event contract boundary around the
existing SOC-IQ Python domain (see docs/phase4/PHASE4D_API_EVENT_ARCHITECTURE.md).

Nothing in this package modifies existing domain, service, or repository
code -- it only wraps app.analyzer.analyze_report and
app.database.service.InvestigationService with a typed command/response/
event contract that is independently testable from the PySide6 GUI.
"""
