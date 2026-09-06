"""
Permanent architecture regression test -- Tauri capability manifest.

Phase 4O Security, Part 2A-1. `docs/security/tauri-capability-model.md`
calls for "a capability-manifest snapshot test added so a future
change that widens permissions is visible in code review rather than
silent" (Master Plan Top-10 security risks, #1: "Tauri capability
manifest over-scoped 'to save time'"). This test is that guard.

The authoritative capability manifest is `src-tauri/capabilities/
default.json` (the only capability file in the project as of this
checkpoint), together with the security-relevant fields of
`src-tauri/tauri.conf.json` (`app.security.capabilities`,
`app.security.csp`). `tests/architecture/capability_manifest_guard.py`
turns those sources into a stable, diffable canonical form; this test
compares that canonical form against the committed snapshot fixture
at `tests/fixtures/capability_manifest.snapshot.json`.

Nine things are verified here (Part 2A-1 established 1-5; Part 2A-2
added 6-7 during independent hardening; Part 2A-3's adversarial audit
added 8-9 after finding that `app.security` fields other than
`capabilities`/`csp` were previously invisible to the snapshot, and
that a Tauri platform/profile config overlay could merge additional
security config with zero effect on it):

1. A controlled *capability-addition* fixture (a brand new
   capability file granting a fresh permission) is detected as a
   snapshot mismatch.
2. A controlled *scope-expansion* fixture (an existing permission's
   scope widened from a narrow path to `*`) is detected.
3. A controlled *shell-permission-addition* fixture is detected.
4. A harmless *reordering* fixture (same permissions, different
   array order) does NOT cause a false-positive mismatch --
   normalization must not swallow real changes, but must swallow
   meaningless ones.
5. The real, current project tree matches the committed baseline
   snapshot exactly.
6. Object-form (inline-scoped) permission entries are captured,
   diffed, and sorted stably alongside plain string permissions.
7. Formatting-only JSON differences (whitespace, key order) never
   change the snapshot.
8. Any key under `app.security` -- not just `capabilities`/`csp` --
   changes the snapshot if it changes (e.g.
   `dangerousDisableAssetCspModification`,
   `dangerousRemoteDomainIpcAccess`).
9. A Tauri platform/profile config overlay file
   (`tauri.<platform>.conf.json`, `tauri.conf.dev.json`, etc.), which
   this guard does not know how to merge, causes a hard failure
   rather than being silently ignored.

Scope: this test only inspects `src-tauri/capabilities/*.json` and
`src-tauri/tauri.conf.json`. It does not attempt to compile the Rust/
Tauri crate graph -- the manifest is plain JSON and can be verified
without a working Rust toolchain; see `docs/security/
tauri-capability-model.md` for the broader capability model this
snapshot protects one slice of.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.architecture.capability_manifest_guard import (
    CapabilityManifestError,
    build_capability_snapshot,
    render_canonical_json,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SNAPSHOT_PATH = (
    _REPO_ROOT / "tests" / "fixtures" / "capability_manifest.snapshot.json"
)


def _write_project_fixture(tmp_path: Path, capability_json: dict, tauri_conf: dict) -> Path:
    """Build a throwaway project tree with just enough shape for the
    guard to load: `src-tauri/capabilities/default.json` and
    `src-tauri/tauri.conf.json`."""
    project = tmp_path / "project"
    caps_dir = project / "src-tauri" / "capabilities"
    caps_dir.mkdir(parents=True)
    (caps_dir / "default.json").write_text(json.dumps(capability_json), encoding="utf-8")
    (project / "src-tauri" / "tauri.conf.json").write_text(
        json.dumps(tauri_conf), encoding="utf-8"
    )
    return project


_BASE_TAURI_CONF = {
    "app": {
        "windows": [{"label": "main"}],
        "security": {
            "csp": "default-src 'self'",
            "capabilities": ["default"],
        },
    }
}

_BASE_CAPABILITY = {
    "identifier": "default",
    "windows": ["main"],
    "permissions": [
        "core:default",
        "dialog:allow-open",
        "fs:allow-read-file",
    ],
}


class TestCapabilitySnapshotCatchesForbiddenChanges:
    """
    Controlled negative tests: prove the snapshot mechanism actually
    detects unauthorized capability changes before trusting it to
    guard the real project.
    """

    def test_baseline_fixture_is_internally_stable(self, tmp_path):
        # Sanity check: building the same fixture twice produces an
        # identical canonical snapshot (determinism).
        project = _write_project_fixture(tmp_path, _BASE_CAPABILITY, _BASE_TAURI_CONF)
        snap_a = build_capability_snapshot(project)
        snap_b = build_capability_snapshot(project)
        assert render_canonical_json(snap_a) == render_canonical_json(snap_b)

    def test_detects_capability_addition(self, tmp_path):
        baseline_project = _write_project_fixture(
            tmp_path / "baseline", _BASE_CAPABILITY, _BASE_TAURI_CONF
        )
        baseline_snapshot = build_capability_snapshot(baseline_project)

        modified_capability = dict(_BASE_CAPABILITY)
        modified_capability["permissions"] = _BASE_CAPABILITY["permissions"] + [
            "shell:allow-execute"
        ]
        modified_project = _write_project_fixture(
            tmp_path / "modified", modified_capability, _BASE_TAURI_CONF
        )
        modified_snapshot = build_capability_snapshot(modified_project)

        assert render_canonical_json(baseline_snapshot) != render_canonical_json(
            modified_snapshot
        ), "expected a newly added permission to change the snapshot, but it did not"

    def test_detects_scope_expansion(self, tmp_path):
        narrow_capability = dict(_BASE_CAPABILITY)
        narrow_capability["scope"] = ["approved/path/*"]
        baseline_project = _write_project_fixture(
            tmp_path / "baseline", narrow_capability, _BASE_TAURI_CONF
        )
        baseline_snapshot = build_capability_snapshot(baseline_project)

        widened_capability = dict(_BASE_CAPABILITY)
        widened_capability["scope"] = ["*"]
        modified_project = _write_project_fixture(
            tmp_path / "modified", widened_capability, _BASE_TAURI_CONF
        )
        modified_snapshot = build_capability_snapshot(modified_project)

        assert render_canonical_json(baseline_snapshot) != render_canonical_json(
            modified_snapshot
        ), "expected a filesystem scope expanded to '*' to change the snapshot"

    def test_detects_shell_permission_addition(self, tmp_path):
        baseline_project = _write_project_fixture(
            tmp_path / "baseline", _BASE_CAPABILITY, _BASE_TAURI_CONF
        )
        baseline_snapshot = build_capability_snapshot(baseline_project)

        with_shell = dict(_BASE_CAPABILITY)
        with_shell["permissions"] = _BASE_CAPABILITY["permissions"] + [
            "shell:allow-open"
        ]
        modified_project = _write_project_fixture(
            tmp_path / "modified", with_shell, _BASE_TAURI_CONF
        )
        modified_snapshot = build_capability_snapshot(modified_project)

        assert render_canonical_json(baseline_snapshot) != render_canonical_json(
            modified_snapshot
        ), "expected a newly added shell permission to change the snapshot"

    def test_detects_privileged_command_wiring_change(self, tmp_path):
        # A capability identifier being wired into (or dropped from)
        # app.security.capabilities without its file changing is
        # itself a security-relevant change.
        baseline_project = _write_project_fixture(
            tmp_path / "baseline", _BASE_CAPABILITY, _BASE_TAURI_CONF
        )
        baseline_snapshot = build_capability_snapshot(baseline_project)

        conf_without_wiring = json.loads(json.dumps(_BASE_TAURI_CONF))
        conf_without_wiring["app"]["security"]["capabilities"] = []
        # A capability file that exists but is unwired is still
        # loadable (it's simply reported under
        # "unreferenced_capability_files"), so this models "someone
        # quietly stopped wiring the manifest in" rather than a
        # loader error.
        modified_project = _write_project_fixture(
            tmp_path / "modified", _BASE_CAPABILITY, conf_without_wiring
        )
        modified_snapshot = build_capability_snapshot(modified_project)

        assert render_canonical_json(baseline_snapshot) != render_canonical_json(
            modified_snapshot
        ), "expected capability wiring to be removed to change the snapshot"


class TestCapabilitySnapshotIgnoresHarmlessChanges:
    def test_permission_reordering_does_not_change_snapshot(self, tmp_path):
        baseline_project = _write_project_fixture(
            tmp_path / "baseline", _BASE_CAPABILITY, _BASE_TAURI_CONF
        )
        baseline_snapshot = build_capability_snapshot(baseline_project)

        reordered_capability = dict(_BASE_CAPABILITY)
        reordered_capability["permissions"] = list(
            reversed(_BASE_CAPABILITY["permissions"])
        )
        reordered_project = _write_project_fixture(
            tmp_path / "reordered", reordered_capability, _BASE_TAURI_CONF
        )
        reordered_snapshot = build_capability_snapshot(reordered_project)

        assert render_canonical_json(baseline_snapshot) == render_canonical_json(
            reordered_snapshot
        ), "harmless permission reordering must not trigger a snapshot mismatch"

    def test_description_change_does_not_change_snapshot(self, tmp_path):
        baseline_project = _write_project_fixture(
            tmp_path / "baseline", _BASE_CAPABILITY, _BASE_TAURI_CONF
        )
        baseline_snapshot = build_capability_snapshot(baseline_project)

        with_description = dict(_BASE_CAPABILITY)
        with_description["description"] = "Updated rationale, no grants changed."
        modified_project = _write_project_fixture(
            tmp_path / "modified", with_description, _BASE_TAURI_CONF
        )
        modified_snapshot = build_capability_snapshot(modified_project)

        assert render_canonical_json(baseline_snapshot) == render_canonical_json(
            modified_snapshot
        ), "a documentation-only 'description' edit must not trigger a snapshot mismatch"


def _write_raw_project_fixture(tmp_path: Path, capability_text: str, tauri_conf_text: str) -> Path:
    """Like `_write_project_fixture`, but takes raw JSON text instead
    of a dict -- used for formatting-only-change tests, where the
    exact byte representation (whitespace, key order, indentation)
    is the thing under test, not the parsed value."""
    project = tmp_path / "project"
    caps_dir = project / "src-tauri" / "capabilities"
    caps_dir.mkdir(parents=True)
    (caps_dir / "default.json").write_text(capability_text, encoding="utf-8")
    (project / "src-tauri" / "tauri.conf.json").write_text(
        tauri_conf_text, encoding="utf-8"
    )
    return project


class TestCapabilitySnapshotHandlesFormattingAndObjectPermissions:
    """
    Part 2A-2 independent-audit additions: formatting-only changes
    must not create false positives, and Tauri's object-form
    (inline-scoped) permission entries -- not just plain permission
    strings -- must actually be captured and diffed, not silently
    dropped or rejected outright.
    """

    def test_formatting_only_change_does_not_change_snapshot(self, tmp_path):
        compact_capability = json.dumps(_BASE_CAPABILITY)
        compact_conf = json.dumps(_BASE_TAURI_CONF)
        baseline_project = _write_raw_project_fixture(
            tmp_path / "baseline", compact_capability, compact_conf
        )
        baseline_snapshot = build_capability_snapshot(baseline_project)

        # Same semantic content, deliberately different formatting:
        # pretty-printed, reordered keys, extra whitespace.
        reformatted_capability = json.dumps(
            {
                "permissions": list(_BASE_CAPABILITY["permissions"]),
                "windows": list(_BASE_CAPABILITY["windows"]),
                "identifier": _BASE_CAPABILITY["identifier"],
            },
            indent=4,
        )
        reformatted_conf = json.dumps(_BASE_TAURI_CONF, indent=2, sort_keys=True)
        reformatted_project = _write_raw_project_fixture(
            tmp_path / "reformatted", reformatted_capability, reformatted_conf
        )
        reformatted_snapshot = build_capability_snapshot(reformatted_project)

        assert render_canonical_json(baseline_snapshot) == render_canonical_json(
            reformatted_snapshot
        ), "formatting-only (whitespace/key-order) differences must not change the snapshot"

    def test_object_form_permission_is_captured(self, tmp_path):
        # Tauri's inline-scoped-permission syntax: an object with its
        # own "identifier" plus an "allow" scope list, not a plain
        # string. Part 2A-1's loader rejected this outright; Part
        # 2A-2 fixed it, so it must now round-trip into the snapshot.
        with_object_permission = dict(_BASE_CAPABILITY)
        with_object_permission["permissions"] = _BASE_CAPABILITY["permissions"] + [
            {"identifier": "fs:scope", "allow": [{"path": "$APPDATA/db/**"}]}
        ]
        project = _write_project_fixture(
            tmp_path, with_object_permission, _BASE_TAURI_CONF
        )
        snapshot = build_capability_snapshot(project)

        rendered = render_canonical_json(snapshot)
        assert "fs:scope" in rendered
        assert "$APPDATA/db/**" in rendered

    def test_object_form_permission_scope_expansion_is_detected(self, tmp_path):
        narrow = dict(_BASE_CAPABILITY)
        narrow["permissions"] = _BASE_CAPABILITY["permissions"] + [
            {"identifier": "fs:scope", "allow": [{"path": "$APPDATA/db/**"}]}
        ]
        baseline_project = _write_project_fixture(tmp_path / "baseline", narrow, _BASE_TAURI_CONF)
        baseline_snapshot = build_capability_snapshot(baseline_project)

        widened = dict(_BASE_CAPABILITY)
        widened["permissions"] = _BASE_CAPABILITY["permissions"] + [
            {"identifier": "fs:scope", "allow": [{"path": "**"}]}
        ]
        modified_project = _write_project_fixture(tmp_path / "modified", widened, _BASE_TAURI_CONF)
        modified_snapshot = build_capability_snapshot(modified_project)

        assert render_canonical_json(baseline_snapshot) != render_canonical_json(
            modified_snapshot
        ), "expected an object-form permission's scope to be expandable-and-detectable, not opaque"

    def test_object_form_permission_reordering_does_not_change_snapshot(self, tmp_path):
        # The two permission entries (one string, one object) should
        # sort the same way regardless of the order they were
        # authored in the source file.
        forward = dict(_BASE_CAPABILITY)
        forward["permissions"] = _BASE_CAPABILITY["permissions"] + [
            {"identifier": "fs:scope", "allow": [{"path": "$APPDATA/db/**"}]}
        ]
        forward_project = _write_project_fixture(tmp_path / "forward", forward, _BASE_TAURI_CONF)
        forward_snapshot = build_capability_snapshot(forward_project)

        backward = dict(_BASE_CAPABILITY)
        backward["permissions"] = [
            {"identifier": "fs:scope", "allow": [{"path": "$APPDATA/db/**"}]}
        ] + _BASE_CAPABILITY["permissions"]
        backward_project = _write_project_fixture(tmp_path / "backward", backward, _BASE_TAURI_CONF)
        backward_snapshot = build_capability_snapshot(backward_project)

        assert render_canonical_json(forward_snapshot) == render_canonical_json(
            backward_snapshot
        ), "reordering a mix of string and object permission entries must not change the snapshot"


class TestCapabilitySnapshotDetectsSecurityKeyBlindSpots:
    """
    Part 2A-3 adversarial audit: prove the specific blind spot found
    during independent re-audit is actually closed, and prove the
    platform/profile config-overlay tripwire actually fires.
    """

    def test_dangerous_asset_csp_modification_flag_is_detected(self, tmp_path):
        # Before the Part 2A-3 fix, only `capabilities` and `csp`
        # were read out of `app.security` -- any other key here was
        # invisible to the snapshot. `dangerousDisableAssetCspModification`
        # is a real Tauri security-relevant flag; its addition must
        # now change the snapshot.
        baseline_project = _write_project_fixture(
            tmp_path / "baseline", _BASE_CAPABILITY, _BASE_TAURI_CONF
        )
        baseline_snapshot = build_capability_snapshot(baseline_project)

        conf_with_dangerous_flag = json.loads(json.dumps(_BASE_TAURI_CONF))
        conf_with_dangerous_flag["app"]["security"][
            "dangerousDisableAssetCspModification"
        ] = True
        modified_project = _write_project_fixture(
            tmp_path / "modified", _BASE_CAPABILITY, conf_with_dangerous_flag
        )
        modified_snapshot = build_capability_snapshot(modified_project)

        assert render_canonical_json(baseline_snapshot) != render_canonical_json(
            modified_snapshot
        ), (
            "a new key under app.security (e.g. "
            "dangerousDisableAssetCspModification) must change the "
            "snapshot even though it is neither 'capabilities' nor 'csp'"
        )

    def test_remote_domain_ipc_access_addition_is_detected(self, tmp_path):
        baseline_project = _write_project_fixture(
            tmp_path / "baseline", _BASE_CAPABILITY, _BASE_TAURI_CONF
        )
        baseline_snapshot = build_capability_snapshot(baseline_project)

        conf_with_remote_access = json.loads(json.dumps(_BASE_TAURI_CONF))
        conf_with_remote_access["app"]["security"][
            "dangerousRemoteDomainIpcAccess"
        ] = [{"domain": "example.com", "windows": ["main"]}]
        modified_project = _write_project_fixture(
            tmp_path / "modified", _BASE_CAPABILITY, conf_with_remote_access
        )
        modified_snapshot = build_capability_snapshot(modified_project)

        assert render_canonical_json(baseline_snapshot) != render_canonical_json(
            modified_snapshot
        ), "granting remote-domain IPC access must change the snapshot"

    def test_platform_specific_config_overlay_is_a_hard_failure(self, tmp_path):
        # A platform overlay (tauri.linux.conf.json etc.) can merge
        # additional app.security config at build time. Rather than
        # silently ignore it, the guard must refuse to produce a
        # snapshot at all until it is explicitly handled.
        project = _write_project_fixture(tmp_path, _BASE_CAPABILITY, _BASE_TAURI_CONF)
        (project / "src-tauri" / "tauri.linux.conf.json").write_text(
            json.dumps({"app": {"security": {"capabilities": ["default", "linux-extra"]}}}),
            encoding="utf-8",
        )

        with pytest.raises(CapabilityManifestError, match="overlay"):
            build_capability_snapshot(project)

    def test_dev_profile_config_overlay_is_a_hard_failure(self, tmp_path):
        project = _write_project_fixture(tmp_path, _BASE_CAPABILITY, _BASE_TAURI_CONF)
        (project / "src-tauri" / "tauri.conf.dev.json").write_text(
            json.dumps({"app": {"security": {"capabilities": ["default"]}}}),
            encoding="utf-8",
        )

        with pytest.raises(CapabilityManifestError, match="overlay"):
            build_capability_snapshot(project)

    def test_base_conf_filename_alone_is_not_mistaken_for_an_overlay(self, tmp_path):
        # Regression guard for the tripwire itself: the ordinary,
        # single `tauri.conf.json` file must never trip the overlay
        # check on its own.
        project = _write_project_fixture(tmp_path, _BASE_CAPABILITY, _BASE_TAURI_CONF)
        build_capability_snapshot(project)  # must not raise


class TestRealProjectMatchesCommittedSnapshot:
    """
    The actual regression guard: SOC-IQ's real capability manifest,
    as it exists right now, must match the committed baseline
    snapshot exactly. A future PR that changes the effective
    capability surface must update
    `tests/fixtures/capability_manifest.snapshot.json` deliberately
    (and thus be visible in code review) rather than have the
    change go unnoticed.
    """

    def test_snapshot_fixture_exists(self):
        assert _SNAPSHOT_PATH.is_file(), (
            f"expected a committed capability snapshot at {_SNAPSHOT_PATH}; "
            "if this is the first time this test runs, generate it from "
            "the approved manifest and commit it deliberately"
        )

    def test_current_manifest_matches_committed_snapshot(self):
        current_snapshot = build_capability_snapshot(_REPO_ROOT)
        current_text = render_canonical_json(current_snapshot)
        baseline_text = _SNAPSHOT_PATH.read_text(encoding="utf-8")

        assert current_text == baseline_text, (
            "Tauri capability manifest changed without an updated, "
            "reviewed snapshot. If this change is intentional and "
            "approved, regenerate "
            "tests/fixtures/capability_manifest.snapshot.json from the "
            "new manifest and commit it as part of this change.\n\n"
            f"--- committed snapshot ---\n{baseline_text}\n"
            f"--- current manifest ---\n{current_text}"
        )

    def test_running_the_suite_does_not_mutate_the_committed_snapshot(self):
        # Bypass-resistance check (Part 2A-2 §8/§9): the snapshot
        # fixture's own bytes must be unaffected by having just run
        # every other test in this module. Nothing in this test file
        # (or capability_manifest_guard.py) may write to
        # _SNAPSHOT_PATH -- only tests/architecture/
        # update_capability_snapshot.py may, and only when invoked
        # directly with --write, never as a side effect of pytest.
        before = _SNAPSHOT_PATH.read_bytes()
        # Re-run the comparison this module already exercises, to
        # simulate "the suite ran" without relying on test ordering.
        build_capability_snapshot(_REPO_ROOT)
        after = _SNAPSHOT_PATH.read_bytes()
        assert before == after, (
            "the committed snapshot fixture must never be modified by "
            "running the test suite"
        )


@pytest.mark.parametrize(
    "case",
    ["capability_addition", "scope_expansion", "shell_permission_addition"],
)
def test_all_required_change_categories_are_detectable(tmp_path, case):
    """
    Consolidated check (Part 2A-1 §11) that every required change
    category is actually caught by the mechanism, not just the
    hand-picked examples above.
    """
    baseline_project = _write_project_fixture(
        tmp_path / "baseline", _BASE_CAPABILITY, _BASE_TAURI_CONF
    )
    baseline_snapshot = render_canonical_json(build_capability_snapshot(baseline_project))

    modified_capability = dict(_BASE_CAPABILITY)
    if case == "capability_addition":
        modified_capability["permissions"] = _BASE_CAPABILITY["permissions"] + [
            "os:allow-platform"
        ]
    elif case == "scope_expansion":
        modified_capability["scope"] = ["*"]
    elif case == "shell_permission_addition":
        modified_capability["permissions"] = _BASE_CAPABILITY["permissions"] + [
            "shell:allow-spawn"
        ]

    modified_project = _write_project_fixture(
        tmp_path / "modified", modified_capability, _BASE_TAURI_CONF
    )
    modified_snapshot = render_canonical_json(build_capability_snapshot(modified_project))

    assert baseline_snapshot != modified_snapshot, f"{case} was not detected"
