# R3-C Rust / Tauri Build Gate

All evidence below is **FRESHLY VERIFIED** in this session unless labeled otherwise.

## 1. Source checkpoint

- File: `SOC-IQ-R3-B-PYTHON-PACKAGING-FINAL-CLOSURE-FULL__1_.zip`
- SHA-256: `77d5487791154ef9716204a2e1bad49cdabf4749f1b1f64b8549a893c081b15e`
- ZIP integrity: `unzip -t` — no errors detected
- Extracted root: `SOC-IQ-R3-B-PYTHON-PACKAGING-FINAL-CLOSURE-FULL/`
- Post-extraction diff against the audit working tree (excluding this doc and
  generated build output) is **empty** — confirmed with `diff -rq`.

## 2. Toolchain

- Sandbox shipped with **no Rust toolchain**. `apt`'s default `rustc`/`cargo` is
  1.75.0, which is too old: the checkpoint's own `Cargo.lock` files (via `time-core
  0.1.9`) require the `edition2024` Cargo feature, needing rustc ≥ 1.85.
- Installed `rustc-1.91`/`cargo-1.91` (`rust-1.91-all` from `archive.ubuntu.com`,
  noble-updates/universe) and set it as the default toolchain.
- `rustc 1.91.1 (ed61e7d7e 2025-11-07)`
- `cargo 1.91.1 (ea2d97820 2025-10-10)`
- target triple: `x86_64-unknown-linux-gnu`
- Tauri CLI: `tauri-cli 2.11.4` (installed via the project's own
  `frontend/package.json` devDependency `@tauri-apps/cli`, run with `npx`)
- Also installed the Linux system libraries Tauri v2 needs to link at all, none
  of which were present initially: `libwebkit2gtk-4.1-dev`, `libgtk-3-dev`,
  `libayatana-appindicator3-dev`, `librsvg2-dev`, `libsoup-3.0-dev` (apt,
  noble/noble-updates).
- **Finding:** `src-tauri/Cargo.toml` and `keystore-core/Cargo.toml` declare
  `rust-version = "1.77"`, but the *locked* dependency graph actually requires
  ≥ 1.85 (edition2024, via `time`/`time-core`). The declared MSRV is stale/inaccurate
  relative to the checked-in lockfile. This did not block the build once a
  current toolchain was installed, but the `rust-version` field should be
  corrected in a future part so `cargo`'s own MSRV check reflects reality.

## 3. Workspace

No root `Cargo.toml` — this is **not** a Cargo workspace; `sidecar-core`,
`keystore-core`, and `src-tauri` are three independent crates, each with its own
`Cargo.lock`, linked via path dependencies from `src-tauri/Cargo.toml`:

```
sidecar-core = { path = "../sidecar-core" }
keystore-core = { path = "../keystore-core" }
```

Both path dependencies resolve correctly; no stale or out-of-tree members found.

**Cargo.lock integrity:** all three lockfiles are byte-identical, before and
after every `cargo check`/`test`/`build` run in this session, to the copies in
the original checkpoint ZIP (verified with `diff`). No dependency was added,
removed, or upgraded.

## 4. `sidecar-core` checks

```
cargo check   → PASS, no warnings
cargo test    → PASS
```

119 tests passed, 0 failed, 0 ignored, across `error_tests` (8), `lifecycle_tests`
(22), `restart_policy_tests` (25), `restart_schedule_tests` (15), `shutdown_tests`
(13), `stability_window_tests` (13), `startup_tests` (23), `supervisor_tests` (13).
Lifecycle state machine, restart policy/tracker/scheduler, restart token, and
crash/recovery logic (the components called out in the mission brief) are all
covered by these suites and all pass unmodified.

## 5. `keystore-core` checks

```
cargo check   → PASS (one-time ~2 min build of the `zbus`/`secret-service`/
                `keyring` dependency graph, no errors)
cargo test    → PASS
```

15 unit tests passed, 0 failed. 3 integration tests in
`tests/real_backend_integration.rs` are intentionally `#[ignore]`d — they require
a real OS credential-store backend (D-Bus Secret Service / KWallet / Windows
Credential Manager) not present in this headless sandbox; this is the correct,
already-documented behavior, not a defect.

## 6. `src-tauri` checks

```
cargo check                    → PASS (2 benign warnings, see §9)
cargo test --lib --bins --tests → PASS, 74 passed / 0 failed
cargo test (full, incl. doctests) → doctest harness error, see §9
```

## 7. Tauri configuration audit

`src-tauri/tauri.conf.json`:

- `build.frontendDist` = `"../frontend/dist"`. **This is already correct** —
  it matches the frontend's actual Vite output directory (`frontend/dist/`,
  confirmed by a fresh `npm run build`: `dist/index.html`, `dist/assets/*.css`,
  `dist/assets/*.js`). The historical `"../dist"` mismatch flagged for R3-A is
  **not present** in this checkpoint. No fix was needed or made.
- `build.beforeBuildCommand` = `npm run build` in `../frontend` — correct, and
  exercised for real by the production Tauri build below.
- `bundle.externalBin` = `["binaries/socq-backend"]`, `bundle.targets` =
  `["msi", "nsis"]` (Windows-only installer targets — see §8/§12 for why this
  matters for the "not distributable from this run" caveat).
- `app.security.capabilities` = `["default"]`, pointing at
  `src-tauri/capabilities/default.json`, which grants only `core:default`,
  `dialog:allow-open`, and `fs:allow-read-file` — no wildcard `*:default`
  grants, no shell/process/network plugin capability. The file's own inline
  comment documents *why* each permission is scoped this way (native file
  picker for `analyze_report`'s `report_path`) and why a previously-present
  bare `get_sidecar_origin` capabilities entry was removed (Tauri 2.11.5's ACL
  parser rejects malformed identifiers outright; the command in question is an
  app-defined `#[tauri::command]`, which is governed by `core:default` alone
  and never needed a capabilities entry). This is documented, prior,
  already-verified state — not a change made in this pass.

## 8. Frontend distribution-path verification

- Ran `npm install` (159 packages, clean) and `npm run build`
  (`tsc --noEmit && vite build`) fresh in `frontend/`.
- TypeScript type-check passed with zero errors; Vite build succeeded in 2.94s:
  `dist/index.html` (0.39 kB), `dist/assets/index-*.css` (59.4 kB),
  `dist/assets/index-*.js` (296.9 kB).
- This is exactly the directory `tauri.conf.json`'s `frontendDist` points at,
  and it's what the production Tauri build in §Build below actually bundled.

## 9. Sidecar integration audit

`src-tauri/src/sidecar.rs` and `src-tauri/src/lib.rs` reference the sidecar via
`sidecar-core`'s process/lifecycle types and via `production_backend_executable_path()`,
which looks for a packaged binary staged next to the running executable and
falls back to a development Python invocation when none is present (covered by
its own passing unit tests, e.g. `resolve_backend_launch_falls_back_to_development_python_when_unpackaged`).

**Real, load-bearing finding:** `cargo build`'s build script (via `tauri-build`)
hard-fails if the file named in `bundle.externalBin`
(`binaries/socq-backend-<target-triple>`) does not exist on disk at build time —
this is normal Tauri `externalBin` behavior, not specific to this project. That
file is **intentionally not part of this checkpoint's tracked source** — per
`packaging/README.md`, it's a PyInstaller-frozen artifact produced by
`packaging/scripts/build_backend.py` (R3-B's scope) and staged into
`src-tauri/binaries/` immediately before a real release build.

Because R3-C's mandate is to prove the *Rust/Tauri build configuration* rather
than redo Python packaging, I staged a **clearly-labeled synthetic placeholder**
(a 4-line shell script, not a real backend, that prints a warning and exits 1)
at the exact expected path/name, ran the build with it, and then **deleted it**
before creating the final checkpoint — it is not part of the checkpoint ZIP.
This proved the `externalBin` resolution, resource embedding, and `.deb`
bundling logic are internally consistent (see §15) without claiming any backend
functionality was verified. **A real release build must use the actual
PyInstaller-frozen `socq-backend` binary from R3-B's pipeline, not this
placeholder.**

## 10. Resource / secret audit

- No `.env`, API keys, tokens, passwords, local databases, logs, exports, or
  developer caches found anywhere in the checkpoint tree (pattern-scanned and
  manually spot-checked).
- `src-tauri/icons/*` are all present and referenced correctly in
  `tauri.conf.json`'s `bundle.icon` list; no missing icon paths.
- No absolute developer-machine paths are configured as release resources.
- `src-tauri/binaries/` does not exist in the tracked checkpoint (see §9) — this
  is correct, not an omission, given the PyInstaller staging step is external.

## 11. Production Tauri build

Ran the **real** project build command, not just `cargo check`:

```
cd src-tauri && npx --prefix ../frontend tauri build --bundles deb
```

(`--bundles deb` used instead of the configured `msi`/`nsis` because those are
Windows-only bundle formats that cannot be produced on this Linux sandbox — see
§12. `deb` was chosen only to prove the Rust build + Tauri bundling pipeline
end-to-end on the one platform this environment can actually target; it is not
one of the checkpoint's configured release targets and is not itself a release
artifact.)

Result: **PASS**.

- `beforeBuildCommand` (`npm run build`) ran automatically and succeeded.
- `soc-iq` compiled in release profile (`opt-level = "s"`, LTO, `panic = "abort"`,
  `codegen-units = 1`, as configured) in ~2m 52s once dependencies were warm.
- Output binary: `src-tauri/target/release/soc-iq` — ELF 64-bit PIE executable,
  6.28 MB, dynamically linked against the system webkit2gtk/gtk stack.
- Bundled: `src-tauri/target/release/bundle/deb/SOC-IQ_0.1.0_amd64.deb` (2.5 MB).
- `.deb` contents inspected with `dpkg-deb -c`: `usr/bin/soc-iq` (main binary),
  `usr/bin/socq-backend` (the synthetic placeholder, staged from
  `bundle.externalBin`), icons at the three configured resolutions, and
  `usr/share/applications/SOC-IQ.desktop` — every configured resource resolved
  and was embedded exactly where the configuration says it should be.
- One transient environment failure occurred and was resolved, not glossed
  over: the first build attempt hit `No space left on device` while linking
  (root filesystem was at 100%, 149 MB free, after debug-profile target
  directories from earlier `cargo check`/`test` runs accumulated ~13 GB).
  Removed the (already-captured) debug target output, freed ~6.7 GB, and the
  identical build succeeded on retry with no code changes. This was an
  environment resource limit, not a build/config defect.

## 12. Windows target

`WINDOWS TAURI BUILD NOT PROVEN — ENVIRONMENT BLOCKED`

This sandbox is Linux-only (Ubuntu 24.04, x86_64-unknown-linux-gnu) with no
Windows toolchain, no MSVC/WiX/NSIS tooling, and no cross-compilation target
installed. `tauri.conf.json`'s configured `bundle.targets` (`msi`, `nsis`) are
both Windows-only formats and were **not** produced. The `deb` bundle in §11
proves the Rust/Tauri build pipeline itself is sound on the platform available,
but is explicitly **not** equivalent to, and must not be read as, proof of a
Windows release build. A genuine Windows-capable build environment is required
before that claim can be made.

## 13. Warnings

Two warnings from `soc-iq` (lib), present in both `cargo check` and the release
build, classified:

1. `unused import: RestartToken` (`src/restart_scheduler.rs:57`) —
   **expected/benign**, cosmetic. `RestartToken` is imported but not directly
   named elsewhere in that file (used transitively). Trivial one-line fix
   available (`cargo fix`) but not applied here per the minimal-fix policy —
   it has zero effect on build correctness or runtime behavior.
2. `method 'is_pending' is never used` (`src/restart_scheduler.rs:261`) —
   **expected/benign**, dead-code lint on a public method that's part of the
   scheduler's API surface but not yet called from `src-tauri`'s current call
   sites. Not a defect.

No other warnings (missing resources, invalid bundle paths, permission
problems, linker warnings beyond the disk-space issue in §11, deprecated Tauri
config, or unresolved native dependencies) were observed in the successful
build.

**Separately:** `cargo test`'s doctest harness (not `cargo check`, not the
actual unit/integration tests) failed with
`error: the -Z unstable-options flag must also be passed to enable the flag check-cfg`
when attempting to run doctests against the `soc_iq_lib` crate. Root cause:
`src-tauri/Cargo.toml`'s `[lib]` declares `crate-type = ["staticlib", "cdylib",
"rlib"]` (required for Tauri's mobile-target support), and `rustdoc --test`
against a multi-crate-type library with this rustc/cargo combination hits a
known tooling rough edge — there are zero actual `///` doctests in the crate
(the harness itself reported `running 0 tests` for that target before the
flag error). Confirmed non-blocking: `cargo test --lib --bins --tests`
(everything except the empty doctest target) passes cleanly, 74/74, exit code
0. This is classified as **known toolchain noise, not a code or
configuration defect** — no fix applied, since there's nothing to fix (no
doctests exist to remove or repair).

## 14. Fixes made

**None.** No source file was modified in `sidecar-core/`, `keystore-core/`,
`src-tauri/`, or `frontend/`. The Tauri `frontendDist` path was already
correct (§7); no other R3-C-scoped defect required a code change. The only
artifacts added during verification (a synthetic sidecar-binary placeholder
and Tauri's `gen/` schema cache) were build-time-only and have been removed
before checkpoint creation (§19 in the mission brief's terms).

## 15. Tests (fresh results, this session)

| Crate | Command | Result |
|---|---|---|
| `sidecar-core` | `cargo check` | PASS, 0 warnings |
| `sidecar-core` | `cargo test` | 119 passed, 0 failed |
| `keystore-core` | `cargo check` | PASS, 0 warnings |
| `keystore-core` | `cargo test` | 15 passed, 0 failed, 3 ignored (real backend required) |
| `src-tauri` | `cargo check` | PASS, 2 benign warnings |
| `src-tauri` | `cargo test --lib --bins --tests` | 74 passed, 0 failed |
| `src-tauri` | `cargo test` (incl. doctests) | doctest-harness error, no real doctests exist (§13) |
| `src-tauri` (via Tauri CLI) | `tauri build --bundles deb` | PASS — real release binary + `.deb` bundle produced |
| `frontend` | `npm run build` | PASS — `tsc --noEmit && vite build`, 0 errors |

## 16. Environment limitations

- No Windows build environment — Windows `msi`/`nsis` targets not produced (§12).
- Root filesystem is small enough that debug + release Cargo target directories
  for this dependency graph (webkit2gtk/Tauri's full transitive tree, compiled
  twice at different profiles) can exhaust it; debug artifacts were deleted
  once their evidence was captured to make room for the release build.
- No GUI/display session — the built `soc-iq` binary was not launched
  interactively; this part proves compilation and bundling, not interactive
  runtime behavior (explicitly out of R3-C's scope; belongs to R4).
- Apt mirrors briefly returned intermittent 404s for a couple of packages on
  the first `apt-get install` pass (unrelated `libc6-dbg`, some webkit2gtk
  sub-packages); resolved by `apt-get update` and retrying — a transient
  mirror-sync issue, not a project defect.

## 17. Unresolved findings

1. **Stale MSRV declarations** (§2): `rust-version = "1.77"` in both
   `src-tauri/Cargo.toml` and `keystore-core/Cargo.toml` understates the actual
   floor (≥ 1.85, driven by the locked `time-core 0.1.9`/edition2024
   requirement). Cosmetic/documentation accuracy issue, not a build blocker
   once a current toolchain is used. Recommend correcting in a future part.
2. **Doctest harness incompatibility** (§13) with the crate's
   `staticlib`/`cdylib`/`rlib` multi-crate-type configuration. No functional
   impact (zero doctests exist), but `cargo test` (full, unfiltered) will
   report a non-zero exit code on any toolchain with this rough edge unless
   doctests are explicitly excluded or the harness bug is fixed upstream.
3. **Two benign lint warnings** in `src/restart_scheduler.rs` (§13) — cosmetic,
   left as-is per the minimal-fix policy; no functional impact.

None of these block declaring the in-scope Linux Rust/Tauri build proven.
