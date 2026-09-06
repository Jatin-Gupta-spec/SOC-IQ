"""
Explicit, manually-invoked regeneration of the committed capability
snapshot fixture.

Phase 4O Security, Part 2A-2 -- snapshot update policy. Normal test
execution (`pytest`, or the project's usual test command) MUST NEVER
call this module or otherwise rewrite
`tests/fixtures/capability_manifest.snapshot.json` on its own --
`tests/test_architecture_capability_snapshot.py` only ever *reads*
that fixture and asserts equality against it. Updating the baseline
is a deliberate, reviewed developer action, taken only after
confirming that a manifest change is an intentional, approved widening
or narrowing of the capability surface -- never an automatic side
effect of running the suite.

This file is intentionally named so pytest's default `test_*.py` /
`*_test.py` discovery does not collect it, and it is not imported by
any test module. It is meant to be run directly:

    python -m tests.architecture.update_capability_snapshot

Running it prints the current manifest's canonical form and the
existing committed snapshot side by side (when they differ) and,
only after an explicit `--write` flag, overwrites the fixture.
Requiring `--write` (rather than writing on every invocation) is
itself part of the safeguard: a developer can inspect the diff first
and only commit to overwriting the approved baseline as a second,
deliberate step.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tests.architecture.capability_manifest_guard import (
    build_capability_snapshot,
    diff_summary,
    render_canonical_json,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SNAPSHOT_PATH = (
    _REPO_ROOT / "tests" / "fixtures" / "capability_manifest.snapshot.json"
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Show (and, only with --write, apply) the diff between the "
            "current Tauri capability manifest and the committed snapshot "
            "baseline. Never run automatically by the test suite."
        )
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help=(
            "Overwrite tests/fixtures/capability_manifest.snapshot.json "
            "with the current manifest's canonical form. Omit this flag "
            "to only preview the diff."
        ),
    )
    args = parser.parse_args(argv)

    current_snapshot = build_capability_snapshot(_REPO_ROOT)
    current_text = render_canonical_json(current_snapshot)

    if not _SNAPSHOT_PATH.is_file():
        print(f"No existing snapshot at {_SNAPSHOT_PATH}.")
        if args.write:
            _SNAPSHOT_PATH.write_text(current_text, encoding="utf-8")
            print(f"Wrote new baseline snapshot to {_SNAPSHOT_PATH}.")
            return 0
        print("Re-run with --write to create it.")
        return 1

    baseline_text = _SNAPSHOT_PATH.read_text(encoding="utf-8")
    if current_text == baseline_text:
        print("Current manifest matches the committed snapshot. No update needed.")
        return 0

    baseline_snapshot = {}  # only used for the diff helper's type; recompute below
    print("The current manifest DIFFERS from the committed snapshot:\n")
    print(
        diff_summary(
            _snapshot_from_text(baseline_text), current_snapshot
        )
    )

    if args.write:
        _SNAPSHOT_PATH.write_text(current_text, encoding="utf-8")
        print(f"\nWrote updated baseline snapshot to {_SNAPSHOT_PATH}.")
        print(
            "Make sure this change is reviewed like any other security-"
            "relevant diff before it is committed."
        )
        return 0

    print(
        "\nThis diff was NOT applied. Re-run with --write only after "
        "confirming this manifest change is an intentional, approved "
        "one."
    )
    return 1


def _snapshot_from_text(text: str) -> dict:
    import json

    return json.loads(text)


if __name__ == "__main__":
    sys.exit(main())
