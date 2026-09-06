"""
AST-based architecture guard: forbid direct `keyring` usage in
SOC-IQ's production Python source tree.

Phase 4O Security, Part 1B-3 -- permanent regression protection for
ADR-008 ("Rust owns OS keystore access"). Part 1B-2 migrated
`app/secrets/store.py` off the third-party `keyring` library onto
`RustKeystoreHandoffSecretStore`, a read-only observer of the
process-scoped environment-variable handoff Rust populates at
sidecar startup. This module exists so that migration cannot quietly
regress: it inspects actual Python source via the `ast` module (not
a text/grep search, which would also match the word "keyring"
inside comments, docstrings, and this very module) and reports every
production file that still imports or uses `keyring` directly.

Scope
-----
This is deliberately narrow: it only understands the `keyring`
module itself (however imported or aliased) and names imported
directly from it. It does not attempt general-purpose static
analysis, does not follow re-exports through intermediate modules,
and does not detect dynamic access (e.g. `importlib.import_module
("keyring")`). That is an intentional trade-off -- see the Part
1B-3 brief's "keep this test narrow, maintainable, and obvious".

Usage
-----
    from tests.architecture.keyring_guard import (
        scan_directory_for_keyring_violations,
    )

    violations = scan_directory_for_keyring_violations(app_root)
    assert not violations
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class KeyringViolation:
    """One forbidden `keyring` import or usage site."""

    lineno: int
    message: str

    def __str__(self) -> str:  # pragma: no cover - purely cosmetic
        return f"line {self.lineno}: {self.message}"


class _KeyringUsageVisitor(ast.NodeVisitor):
    """
    Walks a single module's AST looking for:

    1. Any `import keyring` / `import keyring as <alias>` /
       `import keyring.<submodule>` statement.
    2. Any `from keyring import <name>` / `from keyring.<sub>
       import <name>` statement (regardless of `as <alias>`).
    3. Subsequent attribute access on a name bound to the `keyring`
       module itself (e.g. `keyring.get_password(...)`,
       `kr.set_password(...)`).
    4. Subsequent direct use of a name bound to a symbol imported
       *from* `keyring` (e.g. `get_password(...)` after
       `from keyring import get_password`).

    Violations from (1)/(2) are reported at the import statement
    itself; a file need not go on to actually *call* anything for
    the import alone to already be forbidden (see the Part 1B-3
    brief, section 3: forbidden imports are forbidden regardless of
    whether the imported name is ever used).
    """

    def __init__(self) -> None:
        self.violations: list[KeyringViolation] = []
        # Names bound to the `keyring` module object itself, e.g.
        # `keyring` from `import keyring`, or `kr` from
        # `import keyring as kr`.
        self._module_aliases: set[str] = set()
        # Names bound to a symbol imported directly from `keyring`,
        # e.g. `get_password` (or its alias) from
        # `from keyring import get_password`.
        self._symbol_aliases: set[str] = set()

    @staticmethod
    def _is_keyring_module(dotted_name: str) -> bool:
        return dotted_name == "keyring" or dotted_name.startswith("keyring.")

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if self._is_keyring_module(alias.name):
                bound_name = alias.asname or alias.name.split(".")[0]
                self._module_aliases.add(bound_name)
                shown = (
                    f"import {alias.name} as {alias.asname}"
                    if alias.asname
                    else f"import {alias.name}"
                )
                self.violations.append(
                    KeyringViolation(
                        node.lineno,
                        f"forbidden direct keyring import (`{shown}`)",
                    )
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        if self._is_keyring_module(module):
            for alias in node.names:
                bound_name = alias.asname or alias.name
                self._symbol_aliases.add(bound_name)
                shown = (
                    f"from {module} import {alias.name} as {alias.asname}"
                    if alias.asname
                    else f"from {module} import {alias.name}"
                )
                self.violations.append(
                    KeyringViolation(
                        node.lineno,
                        f"forbidden direct keyring import (`{shown}`)",
                    )
                )
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if (
            isinstance(node.value, ast.Name)
            and node.value.id in self._module_aliases
        ):
            self.violations.append(
                KeyringViolation(
                    node.lineno,
                    "forbidden direct keyring usage "
                    f"(`{node.value.id}.{node.attr}`)",
                )
            )
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load) and node.id in self._symbol_aliases:
            self.violations.append(
                KeyringViolation(
                    node.lineno,
                    f"forbidden direct keyring usage (`{node.id}`)",
                )
            )
        self.generic_visit(node)


def scan_source_for_keyring_violations(
    source: str, filename: str = "<string>"
) -> list[KeyringViolation]:
    """
    Parse `source` (the text of one Python module) and return every
    forbidden direct-`keyring` import or usage site found in it.

    Raises `SyntaxError` if `source` is not valid Python -- this is
    deliberate: a production file that fails to parse is itself a
    problem the caller should see, not something to silently skip.
    """
    tree = ast.parse(source, filename=filename)
    visitor = _KeyringUsageVisitor()
    visitor.visit(tree)
    return visitor.violations


def scan_directory_for_keyring_violations(
    root: Path,
) -> dict[Path, list[KeyringViolation]]:
    """
    Recursively scan every `*.py` file under `root` and return a
    mapping of {file path: [violations]} for files that contain at
    least one forbidden direct-`keyring` import or usage site.

    Files with zero violations are omitted from the result, so
    `scan_directory_for_keyring_violations(root) == {}` is the
    "clean" outcome callers should assert on.
    """
    violations_by_file: dict[Path, list[KeyringViolation]] = {}
    for path in sorted(root.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        file_violations = scan_source_for_keyring_violations(
            source, filename=str(path)
        )
        if file_violations:
            violations_by_file[path] = file_violations
    return violations_by_file


def format_violations(
    violations_by_file: dict[Path, list[KeyringViolation]],
) -> str:
    """Render a violations mapping as a human-readable report block."""
    lines: list[str] = []
    for path, file_violations in violations_by_file.items():
        lines.append(str(path))
        for violation in file_violations:
            lines.append(f"    {violation}")
    return "\n".join(lines)
