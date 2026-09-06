"""
Permanent architecture regression test -- ADR-008.

Phase 4O Security, Part 1B-2 migrated SOC-IQ's Python side off the
third-party `keyring` library entirely: `app/secrets/store.py` now
exposes `RustKeystoreHandoffSecretStore`, a read-only observer of
the process-scoped environment-variable handoff Rust populates at
sidecar startup (see ADR-008, "Rust owns OS keystore access"). This
test exists so that migration can never quietly regress -- so that
some future change cannot reintroduce a direct
`keyring.get_password(...)` call (or a fresh `import keyring`)
anywhere in production Python source without a test immediately
failing.

The scanner itself (`tests/architecture/keyring_guard.py`) is
AST-based rather than a text/grep search specifically so that this
test file, and `app/secrets/store.py`'s own docstrings -- both of
which mention the word "keyring" in prose -- cannot themselves
trigger a false positive. Only a real `ast.Import`/`ast.ImportFrom`
node naming `keyring`, or real subsequent usage of a name bound by
one, counts as a violation.

Four things are verified here:

1. A controlled *forbidden* fixture (a temp file that really does
   `import keyring`) is actually detected -- proving the checker
   has teeth, not just that it stays quiet.
2. A controlled *aliased-import* forbidden fixture
   (`import keyring as kr`) is also detected.
3. A controlled *valid* fixture (ordinary code that does not touch
   `keyring` at all, including code that legitimately uses
   `RustKeystoreHandoffSecretStore`) passes cleanly.
4. The real, current `app/` production tree passes cleanly.

Scope: this test (and the checker it drives) only ever inspects
`app/` -- SOC-IQ's production Python source. It does not scan
`tests/`, `docs/`, ADRs, or this file itself for the string
"keyring"; those are expected to discuss the migration in prose.
"""

from __future__ import annotations

from pathlib import Path

from tests.architecture.keyring_guard import (
    format_violations,
    scan_directory_for_keyring_violations,
    scan_source_for_keyring_violations,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_PRODUCTION_APP_ROOT = _REPO_ROOT / "app"


class TestKeyringGuardCatchesForbiddenFixtures:
    """
    Controlled negative tests: prove the AST checker actually
    detects direct `keyring` access before trusting it to guard the
    real production tree. Every fixture here is written to a
    throwaway `tmp_path` directory and never committed to the
    repository.
    """

    def test_detects_plain_import_keyring(self, tmp_path):
        fixture = tmp_path / "violates_plain_import.py"
        fixture.write_text(
            "import keyring\n"
            "\n"
            "def read_secret(name):\n"
            "    return keyring.get_password('SOC-IQ', name)\n"
        )

        violations = scan_directory_for_keyring_violations(tmp_path)

        assert fixture in violations, (
            "expected the checker to flag a plain `import keyring` "
            f"fixture, found nothing:\n{format_violations(violations)}"
        )
        # Both the import itself and the later attribute-access
        # usage should be reported as separate sites.
        messages = [str(v) for v in violations[fixture]]
        assert any("import keyring" in m for m in messages)
        assert any("keyring.get_password" in m for m in messages)

    def test_detects_aliased_import_keyring(self, tmp_path):
        fixture = tmp_path / "violates_aliased_import.py"
        fixture.write_text(
            "import keyring as kr\n"
            "\n"
            "def write_secret(name, value):\n"
            "    kr.set_password('SOC-IQ', name, value)\n"
        )

        violations = scan_directory_for_keyring_violations(tmp_path)

        assert fixture in violations, (
            "expected the checker to flag an aliased `import keyring "
            f"as kr` fixture, found nothing:\n{format_violations(violations)}"
        )
        messages = [str(v) for v in violations[fixture]]
        assert any("keyring as kr" in m for m in messages)
        assert any("kr.set_password" in m for m in messages)

    def test_detects_from_keyring_import(self, tmp_path):
        fixture = tmp_path / "violates_from_import.py"
        fixture.write_text(
            "from keyring import get_password\n"
            "\n"
            "def read_secret(name):\n"
            "    return get_password('SOC-IQ', name)\n"
        )

        violations = scan_directory_for_keyring_violations(tmp_path)

        assert fixture in violations, (
            "expected the checker to flag `from keyring import "
            f"get_password`, found nothing:\n{format_violations(violations)}"
        )
        messages = [str(v) for v in violations[fixture]]
        assert any("from keyring import get_password" in m for m in messages)

    def test_valid_fixture_passes_cleanly(self, tmp_path):
        fixture = tmp_path / "compliant_module.py"
        fixture.write_text(
            "\"\"\"A module that legitimately never touches keyring.\"\"\"\n"
            "import os\n"
            "\n"
            "\n"
            "class RustKeystoreHandoffSecretStore:\n"
            "    def get_secret(self, name):\n"
            "        return os.environ['SOCIQ_SECRET_VIRUSTOTAL_API_KEY']\n"
        )

        violations = scan_directory_for_keyring_violations(tmp_path)

        assert violations == {}, (
            "expected a compliant fixture to pass cleanly, but the "
            f"checker reported:\n{format_violations(violations)}"
        )

    def test_prose_mentioning_keyring_does_not_trigger_false_positive(self):
        # Guards the AST-vs-grep design choice itself: a docstring
        # that merely *talks about* keyring must never be flagged.
        source = (
            '"""\n'
            "This module used to wrap the third-party `keyring` "
            "library via `keyring.get_password`, but no longer does.\n"
            '"""\n'
            "\n"
            "def noop():\n"
            "    return None\n"
        )

        violations = scan_source_for_keyring_violations(
            source, filename="<prose_fixture>"
        )

        assert violations == [], (
            "a docstring merely mentioning 'keyring' in prose must "
            f"not be flagged, but got: {violations}"
        )


class TestProductionTreeHasNoDirectKeyringAccess:
    """
    The actual regression guard: SOC-IQ's real `app/` production
    tree, as it exists right now, must contain zero direct
    `keyring` imports or usage. This is the test that fails the
    build if a future change reintroduces a direct dependency on
    the third-party `keyring` library from Python.
    """

    def test_app_tree_exists(self):
        # Fails loudly (rather than the main test silently passing
        # on an empty/missing directory) if the production tree
        # ever moves.
        assert _PRODUCTION_APP_ROOT.is_dir(), (
            f"expected a production `app/` tree at "
            f"{_PRODUCTION_APP_ROOT}, but it does not exist"
        )

    def test_no_direct_keyring_usage_in_production_app_tree(self):
        violations = scan_directory_for_keyring_violations(
            _PRODUCTION_APP_ROOT
        )

        assert violations == {}, (
            "ADR-008 regression: production Python source under "
            "app/ must never directly import or use `keyring` -- "
            "Rust is the sole owner of OS-keystore access, and "
            "Python must only read the process-scoped handoff via "
            "`RustKeystoreHandoffSecretStore` "
            "(app/secrets/store.py). Violations found:\n"
            f"{format_violations(violations)}"
        )
