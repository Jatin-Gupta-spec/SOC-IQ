"""
Custom exceptions for the secret-store layer.

Mirrors the `app.threat_intel.exceptions` convention used elsewhere
in SOC-IQ: a single base exception, with specific failure categories
below it so callers can catch broadly (`except SecretStoreError`) or
narrowly, as needed.

Design note (echoing the project's existing `NOT_FOUND != CLEAN`
discipline, applied here to secret state): "the secret was never
configured" (`SecretNotFoundError`) and "the credential store itself
is unavailable" (`SecretStoreUnavailableError`) are deliberately
distinct exceptions. Collapsing them into one would make it
impossible for a caller (or the eventual Settings UI) to tell "no key
saved yet" apart from "something is wrong with the OS keystore" --
two states that call for very different user-facing messages.
"""

from __future__ import annotations


class SecretStoreError(Exception):
    """
    Base exception for all secret-store errors.
    """


class SecretNotFoundError(SecretStoreError):
    """
    Raised by `get_secret()` when no secret is stored under the
    given name.

    This is an expected, ordinary outcome (e.g. the user has not
    configured a credential yet) -- not evidence of a broken store.
    Callers that only need to know whether a secret exists should
    use `has_secret()` instead of catching this exception.
    """


class SecretStoreUnavailableError(SecretStoreError):
    """
    Raised when the underlying OS-backed credential store cannot be
    reached or used at all (service disabled, corrupted keystore,
    unsupported/misconfigured platform backend, permission failure,
    etc.).

    This is distinct from `SecretNotFoundError`: it means the store
    itself could not be consulted, not that it was consulted and
    found empty. Per the Phase 4M-P1 audit and the Part 2A brief,
    the application must fail safely here -- it must never
    interpret "store unavailable" as license to fall back to
    plaintext storage.
    """


class SecretStoreReadOnlyError(SecretStoreUnavailableError):
    """
    Raised by `set_secret()`/`delete_secret()` on a read-only
    `SecretStore` implementation -- specifically
    `app.secrets.store.RustKeystoreHandoffSecretStore`, the Phase 4O
    Security Part 1B-2 implementation Python uses under ADR-008
    ("Rust owns OS keystore access").

    Deliberately a subclass of `SecretStoreUnavailableError` rather
    than a sibling of it: from a caller's perspective "this store
    cannot currently be written to" is a case of the store being
    unavailable *for that operation*, and every existing call site
    that already handles `SecretStoreUnavailableError` safely (e.g.
    `app/settings/repository.py`'s `_migrate_legacy_plaintext_key`,
    which must not crash `load()` just because a write attempt
    failed) continues to do the right thing here without needing to
    know about this narrower error on top of the one it already
    catches. Callers that need to distinguish "genuinely unreachable"
    from "read-only by design" can still catch this subclass
    specifically.

    A read-only store must never silently succeed or silently ignore
    a write -- that would hide the architectural misuse of writing
    credentials from the Python side. It must always raise this
    instead.
    """
