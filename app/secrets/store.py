"""
The `SecretStore` protocol and its production implementation.

Phase 4M, Part 2A -- secure secret-store foundation.
Phase 4O Security, Part 1B-2 -- migrated to the read-only Rust
keystore handoff (ADR-008).

Design
------
Application code (Settings, threat-intel provider wiring, etc.) is
meant to depend only on the `SecretStore` protocol below, never on
`RustKeystoreHandoffSecretStore` or any particular credential
mechanism directly. That keeps the platform-specific implementation
detail isolated behind this one seam, per the Part 2A brief's
requirement that "application code must not know the implementation
details of the OS credential store."

ADR-008 ("Rust owns OS keystore access") moved OS-keystore
read/write onto the Rust side of SOC-IQ (`keystore-core`,
`src-tauri/src/keystore.rs`) as of Phase 4O Security Part 1B-1. Rust
retrieves the VirusTotal API key from the platform credential store
(Windows Credential Manager / macOS Keychain / Secret Service /
KWallet) and passes it to the Python sidecar process through a
short-lived, process-scoped environment-variable handoff -- see
`VIRUSTOTAL_ENV_VAR` below, which is deliberately identical to
`src-tauri/src/sidecar.rs`'s `VIRUSTOTAL_ENV_VAR` constant.

As of this migration (Part 1B-2), Python no longer talks to any OS
credential store at all -- directly or via the third-party
`keyring` library, which this module (and SOC-IQ's production
dependency set) no longer uses. `RustKeystoreHandoffSecretStore` is
read-only by construction: it can only observe the handoff Rust
already placed in this process's environment. Storing or deleting a
credential remains exclusively Rust's responsibility.

Nothing in this module reads or writes `config/settings.json`.
"""

from __future__ import annotations

import os
from typing import Protocol, runtime_checkable

from app.secrets.exceptions import (
    SecretNotFoundError,
    SecretStoreReadOnlyError,
)

#: Environment variable Rust populates for exactly the lifetime of
#: the Python sidecar child process (ADR-008). Identical, by design,
#: to `src-tauri/src/sidecar.rs::VIRUSTOTAL_ENV_VAR` -- both sides of
#: the language boundary must agree on this name for the handoff to
#: work at all. Never set by Python itself.
VIRUSTOTAL_ENV_VAR = "SOCIQ_SECRET_VIRUSTOTAL_API_KEY"

#: Maps a stored secret's `name` (the same vocabulary
#: `app/settings/repository.py`'s `_VT_API_KEY_SECRET_NAME` and the
#: former `KeyringSecretStore` both used, e.g. `"virustotal_api_key"`)
#: to the environment variable Rust hands that secret off through.
#: Only the VirusTotal API key has a Rust-owned handoff today; a
#: `name` with no entry here has no possible handoff and always
#: behaves as "not found" rather than raising, so a caller asking
#: about an unrelated/unknown name gets the same ordinary "not
#: configured" outcome as one that just hasn't been set yet.
_ENV_VAR_BY_SECRET_NAME: dict[str, str] = {
    "virustotal_api_key": VIRUSTOTAL_ENV_VAR,
}


@runtime_checkable
class SecretStore(Protocol):
    """
    Structural contract for a secure, name-keyed secret store.

    Every method is keyed by `name` -- a short, stable identifier
    for *which* secret is being read or written (e.g.
    `"virustotal_api_key"`), analogous to a dict key. The store
    itself decides how (and where) the underlying value is actually
    persisted; callers never see or choose that detail.
    """

    def set_secret(self, name: str, value: str) -> None:
        """
        Store `value` under `name`, replacing any existing value.

        Must not raise merely because a prior value already exists
        under `name` -- that is the normal "update" case, not an
        error.
        """
        ...

    def get_secret(self, name: str) -> str:
        """
        Return the secret stored under `name`.

        Raises
        ------
        SecretNotFoundError
            No secret is currently stored under `name`.
        SecretStoreUnavailableError
            The underlying credential store could not be consulted
            at all.
        """
        ...

    def delete_secret(self, name: str) -> None:
        """
        Remove the secret stored under `name`, if any.

        Deleting a secret that was never configured is not an
        error -- the end state (no secret stored under `name`) is
        identical either way, so this is idempotent by design.
        """
        ...

    def has_secret(self, name: str) -> bool:
        """
        Return whether a secret is currently stored under `name`,
        without exposing its value.

        Callers that only need to know *whether* a credential is
        configured (e.g. to show "Configured" / "Not configured" in
        a settings UI) must use this method rather than calling
        `get_secret()` and discarding the result -- the latter would
        needlessly pull the plaintext secret into memory (and into
        any surrounding stack frame/exception context) for a
        question that only needed a boolean answer.
        """
        ...


class RustKeystoreHandoffSecretStore:
    """
    Production `SecretStore` implementation for ADR-008's Python
    side (Phase 4O Security, Part 1B-2).

    Read-only by design: Rust is the sole owner of credential
    storage (`keystore-core`). This class only ever *reads* the
    process-scoped environment-variable handoff Rust already placed
    in this process's environment when it spawned the Python
    sidecar (see `VIRUSTOTAL_ENV_VAR`/`_ENV_VAR_BY_SECRET_NAME`
    above) -- it never touches an OS keystore, a file, SQLite, the
    registry, or any other storage mechanism, and it never invents a
    fallback. `set_secret()`/`delete_secret()` always raise
    `SecretStoreReadOnlyError` rather than silently succeeding or
    silently doing nothing, so a caller that mistakenly tries to
    write a credential from the Python side finds out immediately
    rather than the write being quietly swallowed.

    This class holds no secret state of its own and does not cache
    the value it reads: every `get_secret()`/`has_secret()` call
    re-reads `os.environ` directly, following the existing
    lifecycle described in ADR-008 (the credential is only ever as
    fresh, and as short-lived, as the sidecar process's own
    environment).
    """

    def __init__(
        self,
        env_var_by_name: dict[str, str] | None = None,
    ) -> None:
        # Real production default is the module-level mapping above.
        # A caller (a test, or any other collaborator that needs a
        # deterministic, non-environment-dependent mapping) may
        # inject its own -- see tests/test_secret_store.py.
        self._env_var_by_name: dict[str, str] = dict(
            env_var_by_name
            if env_var_by_name is not None
            else _ENV_VAR_BY_SECRET_NAME
        )

    def get_secret(self, name: str) -> str:
        env_var = self._env_var_by_name.get(name)

        if env_var is not None:
            value = os.environ.get(env_var, "").strip()
            if value:
                return value

        raise SecretNotFoundError(
            f"No secret is stored under {name!r}."
        )

    def has_secret(self, name: str) -> bool:
        env_var = self._env_var_by_name.get(name)

        if env_var is None:
            return False

        return bool(os.environ.get(env_var, "").strip())

    def set_secret(self, name: str, value: str) -> None:
        raise SecretStoreReadOnlyError(
            f"Cannot store secret {name!r}: this process's secret "
            "store is read-only. Per ADR-008, Rust is the sole "
            "owner of credential storage -- configure the "
            "VirusTotal API key from the desktop application, not "
            "from the Python sidecar."
        )

    def delete_secret(self, name: str) -> None:
        raise SecretStoreReadOnlyError(
            f"Cannot delete secret {name!r}: this process's secret "
            "store is read-only. Per ADR-008, Rust is the sole "
            "owner of credential storage -- remove the VirusTotal "
            "API key from the desktop application, not from the "
            "Python sidecar."
        )
