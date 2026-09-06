"""
Deterministic in-memory `SecretStore` test double.

TEST DOUBLE ONLY -- this class deliberately keeps secrets in a plain
Python dict in process memory. It exists solely so unit tests can
exercise code that depends on `app.secrets.store.SecretStore`
without touching a real OS credential store (which is unavailable,
slow, and stateful in CI/sandbox environments) or a real process
environment handoff. It must never be imported or constructed by
production code -- production code depends on
`app.secrets.store.SecretStore` and is wired to
`RustKeystoreHandoffSecretStore` (the read-only Rust keystore
handoff, ADR-008), never to this class. Unlike the real production
store, `FakeSecretStore` remains fully writable (`set_secret`/
`delete_secret` do not raise) -- it exists to let non-secret-store
tests (settings round-tripping, the application layer, etc.)
exercise a `SecretStore` collaborator without depending on either a
real OS keystore or a real Rust-populated environment variable.
"""

from __future__ import annotations

from app.secrets.exceptions import (
    SecretNotFoundError,
    SecretStoreUnavailableError,
)


class FakeSecretStore:
    """
    In-memory `SecretStore` implementation for tests.

    Set `fail_next` to `True` to make the *next* call to any method
    raise `SecretStoreUnavailableError`, simulating a real backend
    failure (e.g. Credential Manager service disabled/corrupted)
    without needing to mock `keyring` itself. The flag resets after
    one use so subsequent calls behave normally again.
    """

    def __init__(self) -> None:
        self._values: dict[str, str] = {}
        self.fail_next: bool = False

    def _maybe_fail(self) -> None:
        if self.fail_next:
            self.fail_next = False
            raise SecretStoreUnavailableError(
                "Simulated secret-store backend failure."
            )

    def set_secret(self, name: str, value: str) -> None:
        self._maybe_fail()
        self._values[name] = value

    def get_secret(self, name: str) -> str:
        self._maybe_fail()
        try:
            return self._values[name]
        except KeyError:
            raise SecretNotFoundError(
                f"No secret is stored under {name!r}."
            ) from None

    def delete_secret(self, name: str) -> None:
        self._maybe_fail()
        self._values.pop(name, None)

    def has_secret(self, name: str) -> bool:
        self._maybe_fail()
        return name in self._values
