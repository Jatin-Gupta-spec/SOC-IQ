"""
Secure secret-store foundation for SOC-IQ.

Phase 4M, Part 2A. Provides an application-layer abstraction over
credential storage so application code never has to know how (or
where) a secret is actually persisted.

Phase 4O Security, Part 1B-2: the production implementation is now
`RustKeystoreHandoffSecretStore`, a read-only store that observes
the process-scoped environment handoff Rust establishes at sidecar
startup (ADR-008 -- "Rust owns OS keystore access"). Python no
longer talks to any OS credential store directly.
"""

from __future__ import annotations

from app.secrets.exceptions import (
    SecretNotFoundError,
    SecretStoreError,
    SecretStoreReadOnlyError,
    SecretStoreUnavailableError,
)
from app.secrets.store import RustKeystoreHandoffSecretStore, SecretStore

__all__ = [
    "RustKeystoreHandoffSecretStore",
    "SecretNotFoundError",
    "SecretStore",
    "SecretStoreError",
    "SecretStoreReadOnlyError",
    "SecretStoreUnavailableError",
]
