"""
Architecture-regression checks for SOC-IQ.

These are not ordinary unit tests: they inspect the shape of the
production source tree itself (via `ast`), rather than any single
module's runtime behaviour, to keep past architectural decisions
(e.g. ADR-008) from silently regressing.
"""

from __future__ import annotations
