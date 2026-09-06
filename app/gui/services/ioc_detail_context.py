"""
Backward-compatibility shim (Phase 4O).

The canonical implementation of the IOC detail context service moved
to `app.services.ioc_detail_context` -- it is framework-independent
business logic, not GUI presentation code, so it belongs in the
application/service layer rather than under `app.gui`.

This module re-exports the same objects unchanged so that any
remaining import of the old `app.gui.services.ioc_detail_context`
path continues to resolve to the exact same, single canonical
definition rather than a second copy. New code should import from
`app.services.ioc_detail_context` directly; this shim exists only
for backward compatibility during the migration and may be removed
once no caller depends on the old path.
"""

from __future__ import annotations

from app.services.ioc_detail_context import (  # noqa: F401
    TI_STATE_ENRICHED,
    TI_STATE_INCOMPLETE_CHECK,
    TI_STATE_NO_API_KEY,
    TI_STATE_NOT_ENRICHED,
    TI_STATE_PROVIDER_ERROR,
    TI_STATE_UNSUPPORTED_TYPE,
    build_investigation_threat_intel_overview,
    build_ioc_detail_context,
)
