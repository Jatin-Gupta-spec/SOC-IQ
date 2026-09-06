# R3-E Build Artifact Forensic Audit

All evidence below is **FRESHLY VERIFIED** in this session unless labeled
otherwise.

## 1. Source checkpoint

- File: `SOC-IQ-R3-D-WINDOWS-INSTALLER-FINAL-CLOSURE-FULL.zip`
- SHA-256: `068efee3ecff19f4269eb35af86e21bffd9ff4f20535c05f5d64fc2f6c6f6c77`
- ZIP integrity: `unzip -t` — no errors detected
- Entries: 775 total (688 files, 87 directories), 2,365,346 bytes
- Confirmed as the exact R3-D checkpoint (SHA-256 matched the value recorded
  in the R3-D final report before any extraction or modification).

## 2. Artifact inventory

See `docs/audits/SOC-IQ-R3-E-RELEASE-ARTIFACT-MANIFEST.md` for the full table
with hashes. Summary: **zero artifacts were present in the checkpoint** — see
§16 (structural finding). All artifacts audited below were freshly built in
this session:

- Frontend production bundle (`frontend/dist/`)
- Python sidecar (PyInstaller onefile, `dist/socq-backend`)
- Native Tauri executable (`src-tauri/target/release/soc-iq`)
- Linux `.deb` bundle (`SOC-IQ_0.1.0_amd64.deb`)
- Windows MSI/NSIS/sidecar `.exe`: **NOT AVAILABLE**, environment-blocked
  (identical root cause to R3-D — see §12/§15)

## 3. Frontend artifact forensics

- `npm install` (159 packages) + `npm run build` (`tsc --noEmit && vite
  build`) run fresh in this session.
- Output: `dist/index.html`, `dist/assets/index-DpQEO4MK.css`,
  `dist/assets/index-YXA1bTo-.js` — **identical filenames** (including Vite's
  content-hash suffixes) to R3-C's build of the same unmodified source. Since
  Vite's asset filenames are derived from file content hashes, identical
  filenames across two independent builds is strong evidence the frontend
  source has not drifted and the build is effectively deterministic for this
  project.
- Inspected `index.html`: references the hashed CSS/JS assets by relative
  path, no `localhost`/dev-server URLs, no source map or debug-only script
  tags present in the production output.
- This is exactly the directory `tauri.conf.json`'s `frontendDist` points to,
  and exactly what the Tauri build in §5 actually bundled — confirmed by
  inspecting the running build log, not assumed.

## 4. Python / PyInstaller artifact forensics

- Ran the actual project build command:
  `python packaging/scripts/build_backend.py` (auto-detected host triple via
  `rustc -Vv` → `x86_64-unknown-linux-gnu`, exactly as the script's own
  fallback-detection logic documents it would).
- Output: `dist/socq-backend`, 29,082,640 bytes, ELF 64-bit executable,
  staged automatically to
  `src-tauri/binaries/socq-backend-x86_64-unknown-linux-gnu`.
- PyInstaller's own warnings file (`build/socq_backend/warn-socq_backend.txt`,
  173 lines) was inspected in full: every entry is either (a) a `ctypes`
  lookup for Windows-only libraries (`shell32`, `ole32`) that's expected to
  fail on Linux and irrelevant to this build, or (b) a standard "missing
  module" notice for genuinely optional/conditional imports (`mypy`
  type-stub internals, `yaml`, HTTP/3 support in uvicorn, unused
  `multiprocessing` exception classes) — none indicate a real missing
  runtime dependency. No `ERROR` lines, no unresolved hard dependency.
- **Functional verification, not just static inspection:** launched the
  staged binary directly. It bound a random local port, printed it to
  stdout, and answered an HTTP request with a real FastAPI JSON body. This
  is a materially stronger check than R3-B performed (R3-B, per its own
  report, worked from source inspection in an environment with no Rust
  toolchain and therefore never actually wired the sidecar into a running
  Tauri build) — R3-B's packaging-success claim is **upheld and now
  additionally corroborated** by direct execution, not merely re-asserted.

## 5. Tauri / native artifact forensics

- Ran the real build command: `cd src-tauri && npx --prefix ../frontend
  tauri build --bundles deb` (same command R3-C used, this time with the
  real sidecar in place instead of R3-C's synthetic placeholder).
- Output: `src-tauri/target/release/soc-iq`, 6,284,688 bytes — **identical
  size** to R3-C's build (which also produced a 6,284,688-byte binary from a
  synthetic sidecar of a different size). This is expected: the sidecar is
  bundled as an external file via `externalBin`, not statically linked into
  `soc-iq` itself, so replacing the sidecar content does not change the
  Tauri binary's own size. Confirms the two artifacts are cleanly decoupled,
  as the architecture intends.
- Product identity embedded in the build matches `tauri.conf.json`:
  `productName: SOC-IQ`, `identifier: com.soc-iq.desktop`, `version: 0.1.0`.
- `frontendDist` relationship: the `beforeBuildCommand` (`npm run build`)
  ran automatically as part of `tauri build` and produced the exact
  `frontend/dist/` inspected in §3 — verified by reading the live build log,
  not inferred.
- Same 2 benign warnings as R3-C (`unused import: RestartToken`,
  `method 'is_pending' is never used`) — unchanged, since `src-tauri`'s
  source is unchanged from R3-C. No new warnings introduced.

## 6. Sidecar identity verification

**Verified via cryptographic hash, not filename inspection alone:**

```
sha256(dist/socq-backend)
  = f256e64297d61934df7cf5b4fd919bf0c07adf98e98177f641af893472c22d08
sha256(src-tauri/binaries/socq-backend-x86_64-unknown-linux-gnu)
  = f256e64297d61934df7cf5b4fd919bf0c07adf98e98177f641af893472c22d08
sha256(usr/bin/socq-backend, extracted from the built .deb via dpkg-deb -x)
  = f256e64297d61934df7cf5b4fd919bf0c07adf98e98177f641af893472c22d08
```

All three identical. **No mismatch, no stale sidecar, no old-vs-current
divergence.** This is the first time in this project's audit history (R3-A
through R3-E) that this specific check — hash-verified sidecar identity
across the full build→stage→bundle chain — has actually been performed with
a real (non-synthetic) sidecar; R3-C's equivalent check necessarily used a
labeled placeholder since a real Windows-vs-Linux sidecar wasn't the point
of that phase.

## 7. Cross-artifact consistency / dependency chain

| Boundary | Result |
|---|---|
| Frontend source → frontend production build | PASS — `vite build` succeeded, deterministic filenames vs. R3-C |
| Frontend production build → Tauri `frontendDist` | PASS — path match confirmed in `tauri.conf.json` and exercised by a real build |
| Tauri native executable → Python sidecar (`externalBin`) | PASS — hash-identical across build/stage/bundle (§6) |
| Native executable + sidecar → Linux bundle (`.deb`) | PASS — both present and correctly named inside the `.deb`; sidecar hash-verified post-extraction |
| Linux bundle → Windows bundle/installer | **NOT APPLICABLE** — Windows artifacts do not exist (§12) |

## 8. Hash / integrity record

See the manifest (`SOC-IQ-R3-E-RELEASE-ARTIFACT-MANIFEST.md`) for the full
table. All hashes above were computed with `sha256sum` against the actual
files on disk in this session — none were copied from a prior report or
assumed.

## 9. Installer content cross-check

The `.deb` (the only installable bundle this environment can produce) was
extracted with `dpkg-deb -x` and its contents compared against the
standalone artifacts:

- `usr/bin/soc-iq` — present, correct.
- `usr/bin/socq-backend` — present, hash-identical to the standalone sidecar
  (§6). Not stale, not a different build.
- Icons at all three configured resolutions (32×32, 128×128, 256×256@2) —
  present, non-empty, non-corrupt (re-verified: same `file`-reported PNG
  headers as R3-D's icon audit).
- `usr/share/applications/SOC-IQ.desktop` — present.
- **No unexpected files.** No `.env`, no `database/soc_iq.db` (confirmed —
  see §14), no `.git` metadata, no `__pycache__`, no `node_modules`, no test
  fixtures, no stray files of any kind beyond the eleven listed above.

MSI/NSIS content cross-check: **NOT APPLICABLE**, no such artifacts exist.

## 10. Version consistency

| Component | Version | Source |
|---|---|---|
| `tauri.conf.json` (product/installer version) | `0.1.0` | `src-tauri/tauri.conf.json` |
| `src-tauri` (Cargo) | `0.1.0` | `src-tauri/Cargo.toml` |
| `frontend` (npm) | `0.1.0` | `frontend/package.json` |
| `keystore-core` (internal library crate) | `0.1.0` | `keystore-core/Cargo.toml` |
| `sidecar-core` (internal library crate) | `0.2.0` | `sidecar-core/Cargo.toml` |
| `app.config.APP_VERSION` (Python) | `1.0.0` | `app/config.py` |

**Genuine, undocumented divergence found:** the Tauri/installer-facing
product version is `0.1.0` everywhere it actually ships (Cargo, npm, Tauri
config — all consistent with each other), but the Python backend's own
`APP_VERSION` constant says `1.0.0`. No comment, changelog entry, or doc
anywhere in the tree explains this (searched `docs/` for
`APP_VERSION`/"version divergence"/"version mismatch" — no results).

**Investigated whether this actually reaches a user, rather than assumed
either way:** `APP_VERSION` is consumed by exactly two call sites,
`app/cli.py` (an `argparse` `--version` flag) and `app/display.py` (a
"Version : {APP_VERSION}" banner line). Neither `app.cli` nor `app.display`
is imported by `app/api/entrypoint.py` — the actual sidecar entry point that
`packaging/pyinstaller/socq_backend.spec` freezes — confirmed both by
`grep`ing the import graph and by `strings`-searching the frozen
`dist/socq-backend` binary for the literal text `"Version :"`, which
appears **zero times**. So this divergence exists in source but is
**unreachable from the shipped desktop artifact chain this project
currently releases** — `app/cli.py` is a separate, un-packaged, dev-only
entry point, in the same spirit as the already-documented, deliberately
unpackaged PySide6 GUI (§ R3-D, §12 of the earlier PyInstaller spec
comments). Internal crate versions (`sidecar-core` 0.2.0, `keystore-core`
0.1.0) are independent library version numbers, not user-facing product
versions, and their divergence from `0.1.0` is normal and expected — not
flagged as an issue.

**Classification: `OPEN` (see §18)** — real, unforced, worth fixing for
source-hygiene reasons, but confirmed **not** release-blocking since it
cannot reach an installed build today.

## 11. Architecture consistency

All Linux artifacts target `x86_64-unknown-linux-gnu` consistently:
`rustc -Vv`'s host triple, the PyInstaller-staged sidecar's filename suffix,
and the `.deb`'s own `amd64` architecture field all agree. No 32-bit
artifact exists anywhere. No architecture mismatch found. Windows
architecture: **NOT AVAILABLE** (no artifact exists to check).

## 12. Windows artifacts — re-confirmed, not re-litigated from scratch

Re-verified this session, not merely copied from R3-D: the sandbox still has
no Windows machine, and `curl`-testing `static.rust-lang.org` (rustup's
toolchain distribution server) still returns the sandbox's own egress-proxy
block message rather than real content. No new workaround was found or
attempted beyond what R3-D already exhausted. This is the identical,
already-documented environment limitation — carried forward accurately, not
re-declared as if newly discovered.

## 13. Release content security audit

Checkpoint- and artifact-wide sweep (pattern search for AWS-style keys, PEM
private-key/certificate headers; filename search for `.env`, `.pyc`,
`__pycache__`, `node_modules`, `.git`, database/log/export files) run against
both the source tree and the freshly built `.deb`'s extracted contents:

- **No secrets found** anywhere — source tree or built artifacts.
- **No developer runtime data** in any built artifact (confirmed by
  listing, not assumed — see §9's exhaustive `.deb` content list).
- The same pre-existing, empty, schema-only `database/soc_iq.db` flagged in
  the R3-D report is still present in the *source tree* (0 rows of real
  data, unchanged) but — newly confirmed this session by actually building
  and inspecting the `.deb` — **it does not appear inside the built
  installer artifact at all**, because it was never referenced by
  `tauri.conf.json`'s `bundle` config. R3-D predicted this from
  configuration inspection; R3-E confirms it by direct artifact inspection.

## 14. Path leakage audit

- Native executable (`soc-iq`): `strings`-scanned, contains
  `/root/.cargo/registry/src/index.crates.io-.../<crate>/src/...` paths —
  standard embedded Rust debug/panic-location metadata present in every
  non-stripped Rust release binary built anywhere (would show whatever
  machine compiled it — a CI runner's `/home/runner/...`, a developer's
  `/Users/...`, etc.). Generic build-machine cargo-cache paths, not
  SOC-IQ-specific developer information, not credentials, does not affect
  runtime correctness. Documented per Part 13's instruction to record
  harmless debug metadata paths even when not release-blocking.
- Python sidecar (`dist/socq-backend`): `strings`-scanned for the same
  patterns — **zero matches**. Clean.
- No `C:\Users\...`-style developer paths found anywhere (expected — no
  Windows artifact exists to contain them).

## 15. Mutable-data leakage audit

Covered directly by §9 and §13's exhaustive `.deb` content listing: no
database, no logs, no generated reports, no exports, no runtime state of any
kind ships inside the built artifact. Consistent with, and does not disturb,
the R2 persistence architecture already verified at the source level in
R3-D §7 (`platformdirs.user_data_dir(...)`, independent of install/bundle
location).

## 16. Structural finding: no artifacts persist between phases

**This is the most important process-level finding of R3-E.** Every
artifact this report examines was built fresh, in this session, because
R3-A/B/C/D's own checkpoint-cleanup instructions (each phase's "Part
19"/"Part 22"/"Part 24") explicitly strip `target/`, `dist/`, `build/`,
`node_modules/`, and staged sidecar binaries before creating each phase's
final ZIP. The R3-D checkpoint this phase started from contained **zero**
binary artifacts of any kind (verified directly — see §2). R3-E's own
mission brief assumes there are "release build artifacts produced by
R3-A through R3-D" to audit; in the literal sense of *persisted files*,
there were none. What R3-E could and did verify instead is that the
project's source, when built fresh from the current checkpoint, produces
artifacts that are internally consistent, correctly wired together, and
free of the defect classes this audit is scoped to catch — which is the
substantively meaningful version of this gate's intent, just not the
literal one.

## 17. Reproducibility / provenance

Not claimed as bit-for-bit deterministic (the project makes no such
promise, and Rust release builds embed non-deterministic build-machine
paths per §14). What *is* established with direct evidence:

- `Cargo.lock` (all three crates) is byte-identical to R3-C's and R3-D's
  checkpoints — confirmed by `diff`, not assumed.
- Frontend build output filenames (content-hash-derived) are identical to
  R3-C's build of the same source.
- The sidecar's SHA-256 is internally consistent across every stage of this
  session's own build (§6) — a chain-of-custody proof *within* this build,
  which is the strongest provenance claim honestly available without a
  second independent machine to rebuild on.
- Every artifact in the manifest was built directly from the exact,
  hash-verified R3-D source checkpoint in this same session, with no
  intervening edits to `sidecar-core`, `keystore-core`, or `src-tauri`
  (confirmed by the diff in §23).

**Conclusion: provenance is credibly established for all Linux artifacts.**
Windows artifacts remain `NOT AVAILABLE`, not `PROVENANCE UNCERTAIN` — there
is nothing to have uncertain provenance about.

## 18. R3-A/B/C/D discrepancy audit

| Discrepancy | Classification |
|---|---|
| R3-B claimed PyInstaller packaging success from an environment with no Rust toolchain, meaning the sidecar was never actually wired into a running Tauri app | **RESOLVED** — R3-E built the real sidecar, wired it into a real Tauri build, hash-verified it through the full chain, and functionally smoke-tested it. R3-B's claim is upheld, now with stronger evidence than R3-B itself had. |
| R3-C used a synthetic, explicitly non-functional placeholder sidecar (documented as such at the time) | **RESOLVED** — R3-E replaces this with the real, functional PyInstaller sidecar and confirms the build/bundle pipeline behaves identically with real content. |
| `APP_VERSION = "1.0.0"` (Python) vs. `0.1.0` (Tauri/Cargo/npm) | **OPEN** — real, undocumented, but confirmed unreachable from the shipped artifact chain (§10). Recommended for a future part with Python-layer scope, since fixing it is outside R3-E's Rust/artifact-only minimal-fix policy. |
| `database/soc_iq.db` present in source tree | **ACCEPTED WITH EVIDENCE** — confirmed harmless (0 rows), confirmed absent from every built artifact (§9, §13). Not a release concern; a source-tree-cleanliness item only. |
| Windows installer non-existence (R3-D) | **ACCEPTED WITH EVIDENCE, unchanged** — re-verified rather than re-asserted (§12); root cause unchanged since R3-D. |
| No artifacts persisted from R3-A–D into this checkpoint | **ACCEPTED WITH EVIDENCE** — structural consequence of each phase's own documented cleanup policy, not a defect introduced by any single phase (§16). |

No hash mismatches, no filename mismatches, no architecture mismatches, and
no undocumented packaging changes were found anywhere in this audit.

## 19. Fixes made

**None.** No source file was modified in `sidecar-core/`, `keystore-core/`,
`src-tauri/`, `frontend/`, or `app/`. Two new documentation files were added
(this audit and the artifact manifest). The `APP_VERSION` divergence (§10)
was investigated and documented but deliberately **not** touched — fixing it
would be a Python source change, outside R3-E's Rust/artifact-audit-only
minimal-fix policy (Part 19 of the mission brief).

## 20. Tests

No new regression tests were added. Part 20 of the mission brief permits
this when no genuine artifact-*selection*/*configuration* defect was found
to protect against — every defect class actually found in this session
(the version divergence, the source-tree database file) is either
Python-source-layer (out of scope) or already provably harmless with no
packaging-configuration component to regress-test. The sidecar functional
smoke test (§4, §6) is real, fresh evidence but is a manual verification
step, not an automated regression test — documented as such rather than
mischaracterized.

## 21. Environment limitations

Identical to R3-D, re-verified rather than assumed carried-over: no Windows
machine; network egress blocks `static.rust-lang.org`; no apt-packaged
Windows-target Rust std; no Linux-native WiX; PyInstaller cannot cross-target
Windows from Linux. Nothing new on this front in R3-E.

## 22. Unresolved findings

1. `APP_VERSION` divergence (§10, §18) — source-hygiene issue, confirmed
   non-release-blocking, left for a future Python-scoped part.
2. `database/soc_iq.db` in the source tree (§9, §13, §18) — cosmetic,
   confirmed harmless and absent from all built artifacts.
3. Windows artifact unavailability (§12) — unchanged from R3-D; requires an
   actual Windows build environment to resolve, not fixable from within this
   sandbox.

None of these block declaring the Linux artifact chain internally consistent
and correctly wired end-to-end.
