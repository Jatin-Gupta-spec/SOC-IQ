"""
Deterministic canonicalizer for SOC-IQ's Tauri capability manifest.

Phase 4O Security, Part 2A-1/2A-2 -- regression protection for the
Tauri capability surface described in `docs/security/
tauri-capability-model.md` ("a future change that widens permissions
is visible in code review rather than silent"). This module does not
judge whether a given permission is safe; it only produces a stable,
reviewable, diffable representation of the *effective* capability
configuration so that `tests/test_architecture_capability_snapshot.py`
can compare it against a committed snapshot fixture.

Authoritative sources
----------------------
- `src-tauri/capabilities/*.json` -- one file per Tauri capability
  set. As of this checkpoint there is exactly one:
  `src-tauri/capabilities/default.json`.
- `src-tauri/tauri.conf.json` -- specifically `app.security.capabilities`
  (which capability identifiers are actually wired into the app for
  which windows) and `app.security.csp` (the content-security-policy
  string, itself a security-relevant grant/restriction).

What is captured
-----------------
For each capability file: its `identifier`, `windows` list (sorted),
and `permissions` list. Each entry in `permissions` may be either a
plain string (`"core:default"`) or, per Tauri's own capability schema,
an inline-scoped permission object (e.g. `{"identifier": "fs:scope",
"allow": [...], "deny": [...]}`). Both forms are canonicalized -- see
`_canonicalize_permission_entry` -- and the resulting entry list is
sorted by its own canonical JSON text, so array *order* carries no
security meaning but *membership and content* do, for either form.
(Part 2A-1 only handled the plain-string form; Part 2A-2 added object-
form support after an independent audit found that a scoped-permission
entry would previously abort the loader with a hard error rather than
being captured -- see "Part 2A-2 audit findings" below.)

For `tauri.conf.json`: the CSP string verbatim (order/whitespace
inside a CSP is semantically meaningful, so it is captured as-is,
not reordered) and the sorted list of capability identifiers wired
into `app.security.capabilities`.

What is deliberately excluded
------------------------------
- `$schema` -- a tooling pointer, not a grant.
- `description` -- free-text prose. Capability files in this project
  carry long human-readable rationale in `description`; that text is
  valuable for reviewers but is not itself a permission, and forcing
  it into the snapshot would make the guard fire on prose edits that
  change no actual grant (the false-positive-control requirement).
- Any machine-specific path, timestamp, or generated build artifact
  -- none are present in these two source files today, but this
  canonicalizer only ever reads `permissions`/`windows`/`identifier`/
  `capabilities`/`csp`/`scope`/`remote`/`platforms` keys, so none
  could leak in even if added.

Path / environment normalization
---------------------------------
Neither authoritative source currently contains an absolute,
machine-specific filesystem path (the one `scope`-bearing example in
this codebase's test fixtures uses project-relative glob strings like
`"approved/path/*"`, not a real absolute path). No normalization of
path prefixes is performed, by design: doing so without a real example
to validate against would risk silently collapsing a meaningful scope
distinction (e.g. an approved subdirectory vs. a filesystem root) to
save portability that isn't actually needed yet. If a future capability
file legitimately needs a machine-relative path (e.g. `$APPDATA/...`,
which Tauri itself already treats as a portable variable, not a literal
machine path), that value can be captured verbatim -- it is already
portable -- with no further change needed here.

Part 2A-2 audit findings
--------------------------
Independently re-auditing the Part 2A-1 implementation (rather than
trusting its report) surfaced one real gap, fixed in this revision:

1. Object-form permission entries (Tauri's own supported
   inline-scoped-permission syntax) were rejected outright by
   `_canonicalize_capability_file`'s `all(isinstance(p, str) ...)`
   check, raising `CapabilityManifestError` and aborting the whole
   test session rather than being captured in the snapshot. This was
   a fail-loud bug (it would break the build, not silently bypass the
   guard), but it meant the guard could not actually snapshot a
   perfectly legitimate and realistic manifest shape. Fixed by
   `_canonicalize_permission_entry` below, which accepts both forms.

No other gaps were found: sorting was already stable and did not
erase `scope`/`remote` content; the committed snapshot contains no
secrets, timestamps, or machine-specific paths; and no part of the
test suite silently rewrites the fixture (see
`tests/architecture/update_capability_snapshot.py` for the one,
explicit, manually-invoked exception to that rule).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class CapabilityManifestError(Exception):
    """Raised when the capability source tree is not in the expected shape."""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CapabilityManifestError(f"missing required file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CapabilityManifestError(f"invalid JSON in {path}: {exc}") from exc


def _canonicalize_value(value: Any) -> Any:
    """
    Recursively canonicalize a JSON value for stable comparison:
    dict keys are sorted (via json.dumps(..., sort_keys=True) at
    render time), but list *order* is preserved here -- only the
    top-level `permissions` array is explicitly re-sorted by its
    callers, because that is the one place this project has verified
    order carries no security meaning. Nested arrays (e.g. `allow`/
    `deny` scope lists inside a permission object) are left in their
    original order, since scope-rule precedence is not something
    this guard can safely assume is order-independent.
    """
    if isinstance(value, dict):
        return {k: _canonicalize_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_canonicalize_value(v) for v in value]
    return value


def _canonicalize_permission_entry(entry: Any, *, path: Path) -> Any:
    """
    Canonicalize one entry of a capability file's `permissions` array.

    Tauri supports two forms here:

    - a plain permission identifier string, e.g. `"core:default"`.
    - an inline-scoped permission object, e.g.
      `{"identifier": "fs:scope", "allow": [...], "deny": [...]}`,
      used to grant a permission with an additional, narrower scope
      right at the point of use.

    Both are legitimate and must be captured -- a scope object is
    exactly the kind of security-relevant grant this guard exists to
    protect, so silently rejecting or dropping it would be a false
    negative, not a safe default.
    """
    if isinstance(entry, str):
        return entry
    if isinstance(entry, dict):
        if "identifier" not in entry or not isinstance(entry["identifier"], str):
            raise CapabilityManifestError(
                f"{path}: object-form permission entry missing a string "
                f"'identifier' field: {entry!r}"
            )
        return _canonicalize_value(entry)
    raise CapabilityManifestError(
        f"{path}: 'permissions' entries must be a string or an object with "
        f"an 'identifier' field, got {entry!r}"
    )


def _sort_permission_entries(entries: list[Any]) -> list[Any]:
    """
    Sort canonicalized permission entries deterministically. Plain
    strings sort naturally; object-form entries sort by their own
    canonical JSON text so ordering is stable and reproducible
    regardless of dict insertion order.
    """

    def sort_key(entry: Any) -> str:
        if isinstance(entry, str):
            return entry
        return json.dumps(entry, sort_keys=True)

    return sorted(entries, key=sort_key)


def _canonicalize_capability_file(path: Path) -> dict[str, Any]:
    raw = _load_json(path)

    if "identifier" not in raw:
        raise CapabilityManifestError(
            f"{path}: capability file has no 'identifier' field"
        )
    if "permissions" not in raw:
        raise CapabilityManifestError(
            f"{path}: capability file has no 'permissions' field"
        )

    permissions = raw["permissions"]
    if not isinstance(permissions, list):
        raise CapabilityManifestError(f"{path}: 'permissions' must be a list")

    canonical_permissions = _sort_permission_entries(
        [_canonicalize_permission_entry(p, path=path) for p in permissions]
    )

    windows = raw.get("windows", [])
    if not isinstance(windows, list) or not all(isinstance(w, str) for w in windows):
        raise CapabilityManifestError(f"{path}: 'windows' must be a list of strings")

    canonical: dict[str, Any] = {
        "identifier": raw["identifier"],
        "windows": sorted(windows),
        "permissions": canonical_permissions,
    }

    # Some capability files may scope specific permissions further
    # (e.g. filesystem path scopes) via a top-level "scope" key on
    # the file, or per-permission scoping. Capture it verbatim if
    # present, since scope is security-relevant and must not be
    # silently normalized away -- but do not fabricate the key when
    # it is absent, so a snapshot diff cannot be triggered by a key
    # that was never there.
    if "scope" in raw:
        canonical["scope"] = raw["scope"]

    # Remote/platform restrictions, when present, are also
    # security-relevant (they narrow *where* a capability applies).
    if "remote" in raw:
        canonical["remote"] = raw["remote"]
    if "platforms" in raw:
        canonical["platforms"] = sorted(raw["platforms"])

    return canonical


def load_capability_files(capabilities_dir: Path) -> dict[str, dict[str, Any]]:
    """
    Load and canonicalize every `*.json` capability file under
    `capabilities_dir`, keyed by the capability's own `identifier`
    (not its filename -- Tauri itself keys capabilities by
    identifier, and a rename of the file with the same identifier
    is not a security change).
    """
    if not capabilities_dir.is_dir():
        raise CapabilityManifestError(
            f"capabilities directory not found: {capabilities_dir}"
        )

    result: dict[str, dict[str, Any]] = {}
    for path in sorted(capabilities_dir.glob("*.json")):
        canonical = _canonicalize_capability_file(path)
        identifier = canonical["identifier"]
        if identifier in result:
            raise CapabilityManifestError(
                f"duplicate capability identifier {identifier!r} "
                f"(seen again in {path})"
            )
        result[identifier] = canonical
    return result


def load_effective_config(tauri_conf_path: Path) -> dict[str, Any]:
    """
    Extract the security-relevant fields of `tauri.conf.json`.

    Part 2A-3 adversarial-audit fix: earlier revisions cherry-picked
    only `app.security.capabilities` and `app.security.csp` out of
    `app.security`, which meant any *other* key Tauri recognizes under
    `app.security` -- e.g. `dangerousDisableAssetCspModification`,
    `dangerousRemoteDomainIpcAccess`, `assetProtocol`, `freezePrototype`,
    or any future security-relevant field this project has not used
    yet -- could be added with zero effect on the snapshot. That is a
    real false-negative: a change to `app.security` that has nothing to
    do with `capabilities`/`csp` specifically would silently escape
    detection entirely, which is exactly the "unsnapshotted security
    configuration" class of blind spot this stage looks for.

    Fixed by capturing the *entire* `app.security` object (deep-
    canonicalized: dict keys are order-independent by construction,
    via `json.dumps(..., sort_keys=True)` at render time; only the
    one array this project has established is order-independent --
    `capabilities`, the list of wired capability identifiers -- is
    explicitly re-sorted here). Any other array Tauri might place
    under `app.security` in the future (e.g. a list of allowed remote
    origin patterns, where match order could plausibly be meaningful)
    is left in its original order rather than assumed safe to reorder.
    """
    raw = _load_json(tauri_conf_path)

    app = raw.get("app", {})
    security = app.get("security", {})
    windows_cfg = app.get("windows", [])

    if not isinstance(security, dict):
        raise CapabilityManifestError(
            f"{tauri_conf_path}: 'app.security' must be an object"
        )

    security_canonical = _canonicalize_value(security)

    wired_capabilities = security_canonical.get("capabilities", [])
    if not isinstance(wired_capabilities, list) or not all(
        isinstance(c, str) for c in wired_capabilities
    ):
        raise CapabilityManifestError(
            f"{tauri_conf_path}: 'app.security.capabilities' must be a "
            "list of strings"
        )
    security_canonical["capabilities"] = sorted(wired_capabilities)

    window_labels = sorted(
        w.get("label", "main") for w in windows_cfg if isinstance(w, dict)
    )

    return {
        "security": security_canonical,
        "window_labels": window_labels,
    }


def _check_no_unhandled_platform_config_overrides(project_root: Path) -> None:
    """
    Part 2A-3 adversarial-audit addition: Tauri v2 supports
    platform-specific config overlays (e.g. `tauri.linux.conf.json`,
    `tauri.windows.conf.json`, `tauri.macos.conf.json`,
    `tauri.android.conf.json`, `tauri.ios.conf.json`) and a separate
    dev-only overlay (`tauri.conf.dev.json`), each merged into the
    base `tauri.conf.json` at build time. None exist in this project
    today, but if one appeared, it could silently widen
    `app.security` (or anything else) for a specific platform/profile
    with zero effect on this snapshot -- this loader only ever reads
    `src-tauri/tauri.conf.json` itself.

    Rather than guess at merge semantics for a feature this project
    does not use, this is a fail-loud tripwire: if such a file ever
    appears, loading the snapshot raises immediately, forcing a
    deliberate decision (extend this guard to merge and canonicalize
    the overlay) instead of silently shipping a snapshot that only
    covers part of the effective configuration.
    """
    src_tauri = project_root / "src-tauri"
    if not src_tauri.is_dir():
        return
    overlay_patterns = ("tauri.*.conf.json", "tauri.conf.*.json")
    found: list[Path] = []
    for pattern in overlay_patterns:
        for candidate in src_tauri.glob(pattern):
            if candidate.name == "tauri.conf.json":
                continue
            found.append(candidate)
    if found:
        names = sorted(str(p.relative_to(project_root)) for p in set(found))
        raise CapabilityManifestError(
            "found Tauri platform/profile-specific config overlay file(s) "
            f"not covered by this snapshot: {names}. These can merge "
            "additional `app.security` configuration at build time for a "
            "specific platform or profile. Extend "
            "capability_manifest_guard.py to load and canonicalize them "
            "before trusting the snapshot again."
        )


def build_capability_snapshot(project_root: Path) -> dict[str, Any]:
    """
    Build the full canonical, deterministic capability snapshot for
    the project rooted at `project_root`.

    Returns a plain, JSON-serializable dict with two top-level keys:

    - "capabilities": {identifier: canonical capability dict, ...}
    - "effective_config": canonical `tauri.conf.json` security fields
      (the full `app.security` object, plus window labels)

    The same input always produces byte-identical
    `json.dumps(..., indent=2, sort_keys=True)` output -- no
    timestamps, no absolute paths, no environment-specific values.
    """
    _check_no_unhandled_platform_config_overrides(project_root)

    capabilities_dir = project_root / "src-tauri" / "capabilities"
    tauri_conf_path = project_root / "src-tauri" / "tauri.conf.json"

    capabilities = load_capability_files(capabilities_dir)
    effective_config = load_effective_config(tauri_conf_path)

    referenced = set(effective_config["security"].get("capabilities", []))
    known = set(capabilities.keys())
    unreferenced = sorted(known - referenced)
    missing = sorted(referenced - known)
    if missing:
        raise CapabilityManifestError(
            "tauri.conf.json references capability identifier(s) with "
            f"no corresponding capability file: {missing}"
        )

    return {
        "capabilities": capabilities,
        "effective_config": effective_config,
        # Capability files that exist on disk but are not wired into
        # app.security.capabilities are not part of the *effective*
        # attack surface, but a file quietly becoming referenced (or
        # a referenced one quietly being dropped) is itself a
        # security-relevant change worth catching -- so this is
        # tracked explicitly rather than silently ignored.
        "unreferenced_capability_files": unreferenced,
    }


def render_canonical_json(snapshot: dict[str, Any]) -> str:
    """Render a snapshot dict as stable, reviewable canonical JSON text."""
    return json.dumps(snapshot, indent=2, sort_keys=True) + "\n"


def diff_summary(baseline: dict[str, Any], current: dict[str, Any]) -> str:
    """
    Produce a short human-readable summary of the top-level
    differences between two snapshots, for assertion failure
    messages. Not exhaustive -- just enough to point a reviewer at
    what changed.
    """
    baseline_text = render_canonical_json(baseline)
    current_text = render_canonical_json(current)
    if baseline_text == current_text:
        return "(no differences)"

    baseline_lines = baseline_text.splitlines()
    current_lines = current_text.splitlines()
    import difflib

    return "\n".join(
        difflib.unified_diff(
            baseline_lines,
            current_lines,
            fromfile="baseline_snapshot",
            tofile="current_manifest",
            lineterm="",
        )
    )
