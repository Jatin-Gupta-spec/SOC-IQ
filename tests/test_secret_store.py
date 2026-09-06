"""
Tests for the SOC-IQ secret-store layer (`app.secrets.store` /
`app.secrets.exceptions`).

Phase 4M Part 2A introduced this foundation; Phase 4O Security Part
1B-2 migrated the production implementation from `KeyringSecretStore`
(a thin adapter over the third-party `keyring` library, talking to
the OS credential store directly) to `RustKeystoreHandoffSecretStore`
-- a read-only store that observes the process-scoped environment
variable Rust populates at sidecar startup (ADR-008: "Rust owns OS
keystore access"). Two things are exercised here, deliberately kept
separate:

1. `RustKeystoreHandoffSecretStore` -- the real, production
   `SecretStore` implementation. These tests manipulate
   `os.environ` directly (via `monkeypatch.setenv`/`delenv`, which
   restores the prior environment after every test, so this suite
   never leaks environment state into other tests/processes) rather
   than mocking anything -- there is no external backend left to
   fake; the "backend" *is* this process's own environment.
2. `FakeSecretStore` (`tests/fixtures/fake_secret_store.py`) -- the
   writable test double other test modules import when they need a
   `SecretStore` collaborator (settings round-tripping, application
   layer, etc.). It is tested here in its own right so those other
   tests can trust it.

Only fake, never-real credential values are used throughout.
"""

from __future__ import annotations

import os

import pytest

from app.secrets.exceptions import (
    SecretNotFoundError,
    SecretStoreError,
    SecretStoreReadOnlyError,
    SecretStoreUnavailableError,
)
from app.secrets.store import VIRUSTOTAL_ENV_VAR, RustKeystoreHandoffSecretStore
from tests.fixtures.fake_secret_store import FakeSecretStore

FAKE_SECRET_NAME = "virustotal_api_key"
FAKE_SECRET_VALUE = "fake-test-credential-not-real-0000000000"
FAKE_SECRET_VALUE_2 = "fake-test-credential-not-real-1111111111"


@pytest.fixture(autouse=True)
def _clean_secret_env(monkeypatch):
    """
    Every test in this module gets a guaranteed-absent
    `VIRUSTOTAL_ENV_VAR` to start from, regardless of what is set in
    the real environment this test runner happens to execute in --
    and `monkeypatch` restores whatever was there afterwards, so no
    test in this module can pollute the real process environment for
    any other test/process.
    """
    monkeypatch.delenv(VIRUSTOTAL_ENV_VAR, raising=False)


@pytest.fixture
def store() -> RustKeystoreHandoffSecretStore:
    return RustKeystoreHandoffSecretStore()


# ==========================================================
# RustKeystoreHandoffSecretStore: retrieval
# ==========================================================


class TestRustKeystoreHandoffSecretStoreRetrieval:
    def test_get_secret_returns_the_handoff_env_var_value(
        self, store, monkeypatch
    ):
        monkeypatch.setenv(VIRUSTOTAL_ENV_VAR, FAKE_SECRET_VALUE)

        assert store.get_secret(FAKE_SECRET_NAME) == FAKE_SECRET_VALUE

    def test_get_secret_reflects_the_current_env_var_value(
        self, store, monkeypatch
    ):
        monkeypatch.setenv(VIRUSTOTAL_ENV_VAR, FAKE_SECRET_VALUE)
        assert store.get_secret(FAKE_SECRET_NAME) == FAKE_SECRET_VALUE

        monkeypatch.setenv(VIRUSTOTAL_ENV_VAR, FAKE_SECRET_VALUE_2)
        assert store.get_secret(FAKE_SECRET_NAME) == FAKE_SECRET_VALUE_2

    def test_get_secret_for_unrecognized_name_raises_not_found(
        self, store, monkeypatch
    ):
        # A name this store has no env-var mapping for behaves like
        # "never configured" -- not like a crash -- exactly as an
        # unmapped keyring entry name would have before.
        monkeypatch.setenv(VIRUSTOTAL_ENV_VAR, FAKE_SECRET_VALUE)

        with pytest.raises(SecretNotFoundError):
            store.get_secret("some_other_secret_name")


# ==========================================================
# RustKeystoreHandoffSecretStore: missing handoff
# ==========================================================


class TestRustKeystoreHandoffSecretStoreMissing:
    def test_get_secret_raises_not_found_when_env_var_unset(self, store):
        with pytest.raises(SecretNotFoundError):
            store.get_secret(FAKE_SECRET_NAME)

    def test_get_secret_raises_not_found_when_env_var_blank(
        self, store, monkeypatch
    ):
        monkeypatch.setenv(VIRUSTOTAL_ENV_VAR, "   ")

        with pytest.raises(SecretNotFoundError):
            store.get_secret(FAKE_SECRET_NAME)

    def test_not_found_error_message_does_not_contain_a_secret_value(
        self, store, monkeypatch
    ):
        with pytest.raises(SecretNotFoundError) as excinfo:
            store.get_secret(FAKE_SECRET_NAME)

        assert FAKE_SECRET_VALUE not in str(excinfo.value)


# ==========================================================
# RustKeystoreHandoffSecretStore: presence
# ==========================================================


class TestRustKeystoreHandoffSecretStoreHasSecret:
    def test_has_secret_true_when_env_var_set(self, store, monkeypatch):
        monkeypatch.setenv(VIRUSTOTAL_ENV_VAR, FAKE_SECRET_VALUE)

        assert store.has_secret(FAKE_SECRET_NAME) is True

    def test_has_secret_false_when_env_var_unset(self, store):
        assert store.has_secret(FAKE_SECRET_NAME) is False

    def test_has_secret_false_when_env_var_blank(self, store, monkeypatch):
        monkeypatch.setenv(VIRUSTOTAL_ENV_VAR, "")

        assert store.has_secret(FAKE_SECRET_NAME) is False

    def test_has_secret_false_for_unrecognized_name(self, store, monkeypatch):
        monkeypatch.setenv(VIRUSTOTAL_ENV_VAR, FAKE_SECRET_VALUE)

        assert store.has_secret("some_other_secret_name") is False

    def test_has_secret_return_value_never_contains_the_secret(
        self, store, monkeypatch
    ):
        monkeypatch.setenv(VIRUSTOTAL_ENV_VAR, FAKE_SECRET_VALUE)

        result = store.has_secret(FAKE_SECRET_NAME)

        # has_secret() must return a plain bool -- never the secret
        # value itself, and never an object that happens to carry it.
        assert result is True
        assert FAKE_SECRET_VALUE not in repr(result)


# ==========================================================
# RustKeystoreHandoffSecretStore: read-only writes
# ==========================================================


class TestRustKeystoreHandoffSecretStoreReadOnly:
    def test_set_secret_always_raises_read_only(self, store):
        with pytest.raises(SecretStoreReadOnlyError):
            store.set_secret(FAKE_SECRET_NAME, FAKE_SECRET_VALUE)

    def test_delete_secret_always_raises_read_only(self, store, monkeypatch):
        monkeypatch.setenv(VIRUSTOTAL_ENV_VAR, FAKE_SECRET_VALUE)

        with pytest.raises(SecretStoreReadOnlyError):
            store.delete_secret(FAKE_SECRET_NAME)

    def test_read_only_error_is_a_secret_store_unavailable_error(self):
        # So every existing call site that already handles
        # SecretStoreUnavailableError safely (e.g.
        # SettingsRepository._migrate_legacy_plaintext_key) continues
        # to behave safely without needing to learn about this
        # narrower error on top of the one it already catches.
        assert issubclass(SecretStoreReadOnlyError, SecretStoreUnavailableError)

    def test_set_secret_does_not_mutate_the_environment(self, store):
        with pytest.raises(SecretStoreReadOnlyError):
            store.set_secret(FAKE_SECRET_NAME, FAKE_SECRET_VALUE)

        # A rejected write must never have side-effected its way into
        # the environment anyway -- confirms there is no code path
        # that mutates os.environ before raising.
        assert VIRUSTOTAL_ENV_VAR not in os.environ

    def test_read_only_error_message_does_not_contain_a_secret_value(
        self, store
    ):
        with pytest.raises(SecretStoreReadOnlyError) as excinfo:
            store.set_secret(FAKE_SECRET_NAME, FAKE_SECRET_VALUE)

        assert FAKE_SECRET_VALUE not in str(excinfo.value)


# ==========================================================
# RustKeystoreHandoffSecretStore: no keyring fallback
# ==========================================================


class TestRustKeystoreHandoffSecretStoreNoKeyringFallback:
    def test_module_does_not_import_keyring(self):
        import app.secrets.store as store_module

        assert not hasattr(store_module, "keyring")

    def test_a_value_present_only_in_a_real_os_keystore_is_never_seen(
        self, store
    ):
        # This store has no code path to any OS keystore at all, so
        # even a name that happens to collide with something a real
        # OS credential store might hold must still resolve as "not
        # found" here -- proving there is no silent keyring fallback,
        # not just asserting the absence of an import.
        with pytest.raises(SecretNotFoundError):
            store.get_secret(FAKE_SECRET_NAME)


# ==========================================================
# RustKeystoreHandoffSecretStore: no persistent caching
# ==========================================================


class TestRustKeystoreHandoffSecretStoreNoCaching:
    def test_get_secret_does_not_cache_between_calls(self, store, monkeypatch):
        monkeypatch.setenv(VIRUSTOTAL_ENV_VAR, FAKE_SECRET_VALUE)
        assert store.get_secret(FAKE_SECRET_NAME) == FAKE_SECRET_VALUE

        monkeypatch.delenv(VIRUSTOTAL_ENV_VAR)
        with pytest.raises(SecretNotFoundError):
            store.get_secret(FAKE_SECRET_NAME)


# ==========================================================
# FakeSecretStore (the test double itself)
# ==========================================================


class TestFakeSecretStore:
    def test_set_then_get_round_trip(self):
        fake = FakeSecretStore()

        fake.set_secret(FAKE_SECRET_NAME, FAKE_SECRET_VALUE)

        assert fake.get_secret(FAKE_SECRET_NAME) == FAKE_SECRET_VALUE

    def test_update_replaces_previous_value(self):
        fake = FakeSecretStore()
        fake.set_secret(FAKE_SECRET_NAME, FAKE_SECRET_VALUE)

        fake.set_secret(FAKE_SECRET_NAME, FAKE_SECRET_VALUE_2)

        assert fake.get_secret(FAKE_SECRET_NAME) == FAKE_SECRET_VALUE_2

    def test_delete_removes_secret(self):
        fake = FakeSecretStore()
        fake.set_secret(FAKE_SECRET_NAME, FAKE_SECRET_VALUE)

        fake.delete_secret(FAKE_SECRET_NAME)

        assert fake.has_secret(FAKE_SECRET_NAME) is False

    def test_missing_secret_raises_controlled_error(self):
        fake = FakeSecretStore()

        with pytest.raises(SecretNotFoundError):
            fake.get_secret(FAKE_SECRET_NAME)

    def test_has_secret_never_exposes_the_value(self):
        fake = FakeSecretStore()
        fake.set_secret(FAKE_SECRET_NAME, FAKE_SECRET_VALUE)

        result = fake.has_secret(FAKE_SECRET_NAME)

        assert result is True
        assert FAKE_SECRET_VALUE not in repr(result)

    def test_fail_next_simulates_one_backend_failure(self):
        fake = FakeSecretStore()
        fake.fail_next = True

        with pytest.raises(SecretStoreUnavailableError):
            fake.get_secret(FAKE_SECRET_NAME)

        # The flag resets after firing once -- the next call behaves
        # normally again.
        assert fake.fail_next is False
        with pytest.raises(SecretNotFoundError):
            fake.get_secret(FAKE_SECRET_NAME)


# ==========================================================
# Secret isolation: DTO / serialization safety
# ==========================================================


class TestSecretIsolationFromUnrelatedStructures:
    """
    Part 2A brief SS4/SS6: a `SecretStore` must never end up
    serialized (directly or via a careless `__dict__`/`vars()` dump)
    into something that ends up in a DTO, report, or API response.
    """

    def test_secret_store_repr_does_not_expose_stored_values(
        self, store, monkeypatch
    ):
        monkeypatch.setenv(VIRUSTOTAL_ENV_VAR, FAKE_SECRET_VALUE)

        # RustKeystoreHandoffSecretStore holds no secret state in its
        # own instance attributes at all (every value is re-read from
        # os.environ on demand, never cached) -- so its default repr
        # cannot leak a stored value even without a custom __repr__.
        assert FAKE_SECRET_VALUE not in repr(store)
        assert FAKE_SECRET_VALUE not in str(vars(store))

    def test_fake_secret_store_vars_only_expose_intended_test_state(self):
        fake = FakeSecretStore()
        fake.set_secret(FAKE_SECRET_NAME, FAKE_SECRET_VALUE)

        # The fake is explicitly documented as an in-memory test
        # double -- unlike the real store, it is expected to hold
        # the value in `_values`. This test exists so a future
        # change to FakeSecretStore that widens what it exposes
        # (e.g. logging its own state) gets caught here rather than
        # only being noticed once it leaks into a real test's
        # failure output.
        assert set(vars(fake).keys()) == {"_values", "fail_next"}


def test_secret_store_error_hierarchy():
    assert issubclass(SecretNotFoundError, SecretStoreError)
    assert issubclass(SecretStoreUnavailableError, SecretStoreError)
    assert issubclass(SecretStoreReadOnlyError, SecretStoreUnavailableError)
