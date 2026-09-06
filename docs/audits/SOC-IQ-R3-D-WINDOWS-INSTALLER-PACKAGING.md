# R3-D Windows Installer Packaging

All evidence below is **FRESHLY VERIFIED** in this session unless labeled
otherwise. This gate's headline result is a genuine **environment block**,
documented in detail rather than glossed over.

## 1. Source checkpoint

- File: `SOC-IQ-R3-C-RUST-TAURI-BUILD-FINAL-CLOSURE-FULL.zip`
- SHA-256: `af8b848b423ef0a5cd8e5db526ba5ec45ae6ff8c0160b1e2f22adaf31e0139fc`
- ZIP integrity: `unzip -t` — no errors detected
- Entries: 774 total (687 files, 87 directories), 2,358,511 bytes
- Post-extraction working tree diffed byte-for-byte against a fresh
  re-extraction of the same ZIP — identical before any R3-D work began.

## 2. Windows environment

- Host OS: Ubuntu 24.04.4 LTS, x86_64, Linux sandbox. **No Windows machine of
  any kind is available.**
- No native Windows build/install/uninstall is possible here — expected and
  declared up front, not discovered partway through.

## 3. Cross-compilation attempt (real, not assumed to fail)

Rather than assume cross-compilation was impossible, I attempted it for real:

1. Installed `rustup` (1.26.0, via apt) to try to add the
   `x86_64-pc-windows-gnu` Rust target.
2. `rustup toolchain link` was used to register the existing rustc 1.91.1
   install, since it wasn't itself installed via rustup.
3. `rustup target add x86_64-pc-windows-gnu` failed: a manually-linked
   toolchain has no component manifest, so target/component management isn't
   available on it (`error: toolchain 'system-1.91' does not support
   components`).
4. Tried `rustup toolchain install stable` instead (which would fetch a
   proper, component-capable toolchain) — failed: `error: no release found
   for 'stable'`.
5. Investigated directly: `curl https://static.rust-lang.org/dist/...`
   completes a real TLS handshake but the response body is the sandbox's own
   egress-proxy message: `Host not in allowlist: static.rust-lang.org. Add
   this host to your network egress settings to allow access.` This is a
   **network policy block**, independent of the missing Windows machine.
6. Checked `apt-cache search` for a Debian/Ubuntu-packaged
   `x86_64-pc-windows-gnu` Rust standard library (the one thing that could
   have worked without needing `static.rust-lang.org`) — none exists in the
   configured mirrors. Ubuntu does not ship a Windows-target Rust std via apt.

**Conclusion: Windows cross-compilation of the Rust/Tauri layer is not
possible in this sandbox**, for a documented, reproducible reason (network
egress allowlist), not a skill or effort gap.

Independently of the above, two more blockers would remain even if Rust
cross-compilation worked:

- **MSI (WiX)**: Tauri's MSI bundler invokes WiX Toolset's `candle.exe`/
  `light.exe`, which are Windows PE binaries. There is no Linux-native WiX
  build; running them here would require Wine, which is not a genuine Windows
  build and was not attempted.
- **PyInstaller sidecar**: `packaging/scripts/build_backend.py` freezes the
  Python backend with PyInstaller, which does **not** support cross-compiling
  a Windows `.exe` from Linux — PyInstaller freezes for the platform it runs
  on. A real `socq-backend-x86_64-pc-windows-msvc.exe` can only be produced on
  actual Windows.

## 4. Historical corroboration

`packaging/scripts/build-windows.ps1` (already present in the checkpoint, not
authored in this pass) contains an explicit, pre-existing note:

> "This script only VALIDATES on Windows. It has not been executed here: this
> ... checkpoint was produced in a Linux sandbox with no Rust toolchain and no
> Windows host, so running this script is Windows-environment-blocked in that
> sandbox ... Static review only."

This is **HISTORICAL** evidence from an earlier phase of the same project,
independently corroborating this session's finding: a Windows build has never
actually been executed for this project inside any sandbox used so far, only
statically reviewed. Nothing in R3-D changes that.

## 5. Authoritative installer configuration (static audit — this part IS
achievable and was done in full)

`src-tauri/tauri.conf.json`:

- `productName`: `"SOC-IQ"`, `version`: `"0.1.0"`, `identifier`:
  `"com.soc-iq.desktop"`.
- `bundle.active`: `true`; `bundle.targets`: `["msi", "nsis"]` — both
  configured, no third format, nothing invented for this audit.
- `bundle.icon` includes `icons/icon.ico`, confirmed present and valid: `file`
  reports a genuine multi-resolution (7-image) Windows ICO resource, not a
  placeholder or corrupted file.
- `bundle.externalBin`: `["binaries/socq-backend"]` — same sidecar mechanism
  audited in R3-C; on Windows this resolves to
  `binaries/socq-backend-x86_64-pc-windows-msvc.exe` (or the `-gnu` triple,
  depending on which Rust target actually builds — moot here since neither
  can run).
- **No `bundle.windows` sub-object at all** — no NSIS `installMode`,
  `license`, `languages`, or upgrade-code overrides; no WiX `upgradeCode` or
  fragment overrides; no custom `.nsi`/`.wxs` template files exist anywhere in
  the tree (searched, none found). The project uses Tauri's built-in
  default MSI/NSIS templates unmodified.
- **No code-signing configuration anywhere** — no `signCommand`,
  `certificateThumbprint`, `.pfx`/`.p12` reference, or signing script in
  `tauri.conf.json`, `packaging/`, or any `.ps1`/`.md` file (pattern-searched).

**CODE SIGNING: NOT CONFIGURED.**

## 6. Release input inventory / build sequencing

`packaging/scripts/build-windows.ps1` is the single documented, authoritative
Windows release path (confirmed to be a thin, honest sequencer, not a second
undocumented build system):

```
python packaging/scripts/build_backend.py   → src-tauri/binaries/socq-backend-<triple>.exe
cd src-tauri; cargo tauri build             → target/release/bundle/{msi,nsis}/
```

Both steps require a real Windows host; neither was runnable here (§3).

## 7. Persistence boundary (source-level verification — achievable and done)

`app/config.py` resolves the persistent application-data root via
`platformdirs.user_data_dir(APP_NAME, APP_AUTHOR, roaming=True)`, which on
Windows consults `%APPDATA%` — **not** `sys.argv[0]`, **not** `__file__`, and
critically **not** anything installer-location-dependent. `BASE_DIR`
(`Path(__file__).resolve().parent.parent`) is explicitly documented in the
source as bundled-resources-only and is never used for the database, logs, or
settings; those are `APP_DATA_ROOT / {"database","logs","config"}`,
independent of `APP_DATA_ROOT`.

Consequence: **wherever the installer places the executable — a
protected `Program Files` tree (MSI's typical default) or a per-user
`%LOCALAPPDATA%\Programs` tree (NSIS's typical Tauri default) — the
application never attempts to write into its own install/extraction
directory.** This is exactly the separation R2-A/R2-E already established;
R3-D's installer-layer configuration does not disturb it, and no installer
setting in `tauri.conf.json` overrides or redirects `%APPDATA%`. This is
**HISTORICAL** architecture (R2-A/R2-E), reconfirmed **FRESHLY VERIFIED**
against this exact checkpoint's source in this session.

## 8. Secrets / development-data audit

Checkpoint-wide sweep (pattern search for AWS-style keys, PEM private-key
headers, certificate blocks; filename search for `.env`, `.pyc`,
`__pycache__`, `node_modules`, `*.log`):

- No `.env`, no API keys, no tokens, no private keys, no certificates found.
- **One pre-existing item flagged, not fixed:** `database/soc_iq.db`, a
  28 KB SQLite file at the repository root. Inspected directly (not just by
  name): schema-only, `investigations` and `timeline_events` tables both
  have **0 rows**; `schema_version` has 1 row (a migration marker). This is
  not user data, not a secret, and not test/dev output containing real
  content. It is also **not referenced anywhere in `tauri.conf.json`'s
  `bundle` config** (no `bundle.resources` key exists), so it is not staged
  into, and would never ship inside, any installer this project builds.
  Flagged for visibility; left untouched, since removing or relocating it
  would be a Python/database-layer change outside R3-D's Rust/installer-only
  scope, and it has zero effect on installer contents either way.

## 9. Installer build

**NOT PERFORMED — see §3.** No `.msi`, no `.nsis`/`.exe` installer artifact
was produced. No installer contents, metadata, shortcuts, or uninstall
behavior could be inspected because no installer exists to inspect. Sections
9–15 of the underlying mission brief (artifact inspection, metadata audit,
install/uninstall smoke test, installed-file-layout audit, shortcut
forensics, upgrade/version-safety audit) are each recorded below as
`NOT VERIFIED — NO ARTIFACT PRODUCED`, not silently skipped.

## 10. Fixes made

**None.** No source file was modified. `packaging/scripts/build-windows.ps1`
already correctly documents the environment-blocked status from an earlier
phase; nothing needed correcting there. The `tauri.conf.json`
`bundle`/`icon`/`externalBin` configuration was audited and found consistent
with R3-C's already-verified Linux build — no packaging-layer defect was
found that a fix could address, because the defect (no Windows build
capability) is environmental, not configuration-level.

## 11. Tests

No installer-specific regression tests were added (Part 18 of the mission
brief permits skipping this when "real installer verification remains the
authoritative evidence" and no artifact exists to protect against
regressing). `sidecar-core`/`keystore-core`/`src-tauri` Rust test suites were
not re-run in this pass — R3-D's scope is installer packaging, not Rust
source verification, which R3-C already covered for this exact, unmodified
source tree.

## 12. Environment limitations (exhaustive, not partial)

1. No Windows machine, real or virtual.
2. Network egress allowlist blocks `static.rust-lang.org`, preventing
   `rustup` from fetching the `x86_64-pc-windows-gnu` Rust standard library —
   demonstrated with a real `curl` request and a real `rustup` failure, not
   assumed.
3. No Debian/Ubuntu-packaged alternative exists for a Windows-target Rust
   std library.
4. WiX Toolset (`candle.exe`/`light.exe`) has no Linux-native build; only a
   Wine-hosted path exists, which was not used because it does not constitute
   a genuine Windows build.
5. PyInstaller cannot cross-compile a Windows executable from Linux under any
   configuration.

## 13. Unresolved findings

1. No installer has ever been built for this project in any sandboxed
   environment used across its audit history (§4) — a real Windows build
   machine is required before R3-D can be closed with a PASS verdict.
2. `database/soc_iq.db` (§8) — cosmetic source-tree cleanliness item, zero
   installer impact, left for a future part with Python-layer scope if
   desired.
