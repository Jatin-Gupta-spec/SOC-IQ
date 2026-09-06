# R3-E Release Artifact Manifest

Source checkpoint: `SOC-IQ-R3-D-WINDOWS-INSTALLER-FINAL-CLOSURE-FULL.zip`,
SHA-256 `068efee3ecff19f4269eb35af86e21bffd9ff4f20535c05f5d64fc2f6c6f6c77`.

**All artifacts below were freshly regenerated in this session.** None were
inherited from the checkpoint — R3-A through R3-D's own checkpoint-cleanup
rules strip `target/`, `dist/`, `build/`, `node_modules/`, and staged sidecar
binaries before packaging, so no binary artifact from any prior phase
persisted into the R3-D checkpoint for this phase to inspect directly. This
is a structural fact about the phase-cleanup process, documented here rather
than treated as a gap: every artifact below is being observed for the first
time in the project's audit history with the real (non-synthetic) sidecar
actually wired in.

Target platform for all artifacts below: `x86_64-unknown-linux-gnu` (the only
platform this sandbox can build for — see the R3-D report and §"Windows" at
the end of this manifest for why).

| Artifact | Type | Path (relative to project root) | Size | SHA-256 | Producer |
|---|---|---|---:|---|---|
| `index.html` | Frontend HTML | `frontend/dist/index.html` | 399 B | `cd33fb9aa6208f2aa4e0a5a25ada2231f06cc35eb091777e831a57f0bf021918` | `vite build` |
| `index-DpQEO4MK.css` | Frontend CSS | `frontend/dist/assets/index-DpQEO4MK.css` | 59.4 KB | `0bc6dd7e4287e0f26817e1be57806617354a5386cdf8013129493362408cce7b` | `vite build` |
| `index-YXA1bTo-.js` | Frontend JS | `frontend/dist/assets/index-YXA1bTo-.js` | 296.9 KB | `e4246b1bd75e9d05066c9e4786df205c0920cff11c4399def6f9cae6031f6068` | `vite build` |
| `socq-backend` | Python sidecar (PyInstaller onefile) | `dist/socq-backend` | 29,082,640 B | `f256e64297d61934df7cf5b4fd919bf0c07adf98e98177f641af893472c22d08` | `pyinstaller packaging/pyinstaller/socq_backend.spec` |
| `socq-backend-x86_64-unknown-linux-gnu` | Staged sidecar | `src-tauri/binaries/socq-backend-x86_64-unknown-linux-gnu` | 29,082,640 B | `f256e64297d61934df7cf5b4fd919bf0c07adf98e98177f641af893472c22d08` | `packaging/scripts/build_backend.py` (copy of the row above) |
| `soc-iq` | Native Tauri executable | `src-tauri/target/release/soc-iq` | 6,284,688 B | `37bc92d3f12cdfbc9af64a90a7a3d9a59c1408bdcfeeae19584ebe1e13863dc0` | `cargo tauri build` (release profile) |
| `SOC-IQ_0.1.0_amd64.deb` | Linux bundle/installer | `src-tauri/target/release/bundle/deb/SOC-IQ_0.1.0_amd64.deb` | 31,365,626 B | `ff4c44a890d83719b6d276cdcd4a50495b5c2cc9b65e3bd0f9cea4fdcf876d46` | `tauri build --bundles deb` |
| `socq-backend` (inside `.deb`) | Extracted sidecar copy | `usr/bin/socq-backend` inside the `.deb` | 29,082,640 B | `f256e64297d61934df7cf5b4fd919bf0c07adf98e98177f641af893472c22d08` | Extracted via `dpkg-deb -x` and re-hashed |
| MSI installer | — | — | — | `NOT AVAILABLE` | Environment-blocked, see §Windows |
| NSIS installer | — | — | — | `NOT AVAILABLE` | Environment-blocked, see §Windows |
| Windows sidecar `.exe` | — | — | — | `NOT AVAILABLE` | Environment-blocked, see §Windows |

## Sidecar identity — verified match, not assumed

`f256e64297d61934df7cf5b4fd919bf0c07adf98e98177f641af893472c22d08` appears
identically in three places: the raw PyInstaller output (`dist/socq-backend`),
the file `tauri.conf.json`'s `externalBin` staged for the build
(`src-tauri/binaries/socq-backend-x86_64-unknown-linux-gnu`), and the copy
actually extracted back out of the built `.deb` (`usr/bin/socq-backend`).
This is a byte-for-byte match across the entire chain — the exact file
PyInstaller produced is the exact file the installer ships, with zero
substitution, staleness, or corruption at any step.

## Functional smoke check (not a substitute for R4)

The staged sidecar was launched directly and observed to: bind a random local
TCP port, print that port to stdout (the handshake contract
`src-tauri/src/sidecar.rs` parses), and respond to an HTTP request with a
genuine FastAPI JSON response (`404 {"detail":"Not Found"}` for an unrouted
path — expected FastAPI behavior, not an error). This confirms the frozen
executable is a real, running FastAPI/uvicorn process, not merely a
compiled-but-broken binary. It is **not** a substitute for R4's full
installed-runtime campaign (no Tauri-parent-to-sidecar handshake, UI, or
end-to-end workflow was exercised).

## Windows artifacts

Still `NOT AVAILABLE`, for the same reasons documented in detail in the R3-D
report and re-confirmed in this session: no Windows machine, and the sandbox's
network egress allowlist blocks `static.rust-lang.org`, so `rustup` cannot
fetch the `x86_64-pc-windows-gnu` target's standard library needed for
cross-compilation, independent of WiX/MSI and PyInstaller's own inability to
cross-target Windows from Linux. Nothing changed on this front in R3-E.
