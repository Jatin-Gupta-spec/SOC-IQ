# SOC-IQ R4-B0 — CORS Remediation: Final Closure Audit

## Evidence Provenance Notice (read first)

This document combines two distinct evidence sources, and keeps them
separated throughout per this project's established Category A/B/C
convention (see `docs/audits/SOC-IQ-R4-A-INSTALLATION-LAUNCH-VERIFICATION.md`):

- **Category A — Independently verified in the Linux sandbox that produced
  this checkpoint.** Source-level facts, the CORS unit/preflight tests, the
  non-GUI backend suite, and the frontend `tsc`/build checks. These were
  actually executed and observed during the R4-B0 remediation session.
- **Category B — Reported by the Windows operator, not independently
  reproduced.** Everything about the actual Windows toolchain, the
  PyInstaller/Rust/Tauri builds, the MSI/NSIS artifacts and their hashes,
  and the install/launch/uninstall lifecycles. The Linux sandbox that
  authored this checkpoint has no Rust toolchain, no Wine/WiX/NSIS tooling,
  and no Windows OS or VM of any kind — it cannot build or run any of this
  itself, and did not. These facts are recorded exactly as reported by the
  operator who ran them on real Windows hardware.

No fact in this document is presented as independently verified unless it
is explicitly marked Category A.

## 1. Scope

Closure documentation only for the R4-B0 CORS remediation. No source,
dependency, test, or installer-configuration changes were made during this
closure pass.

## 2. Checkpoint Identity

- Checkpoint ZIP: `SOC-IQ-R4-B0-CORS-REMEDIATED-FULL-PROJECT.zip`
- SHA-256: `c29ca8945193397ad8b0617ca98f96c3c29b32a5bfb9a09e02d348c285b168bb`
  *(Category A — this is the exact hash produced when this ZIP was created
  in the Linux sandbox; independently re-confirmed against the same file
  before writing this document.)*
- 778 ZIP entries / 691 files / 87 directories — Category A, established
  at creation time.
- ZIP integrity clean; fresh extraction previously verified; no
  `node_modules`, generated `dist`, or `__pycache__` leakage — Category A.

## 3. Remediation Summary (Category A)

`app/api/app.py` was modified to register `fastapi.middleware.cors.CORSMiddleware`,
addressing the cross-origin `fetch()` failure identified during the R4-A
packaged-runtime diagnostic (Dashboard showing `Network failure calling
command "get_dashboard_summary": Failed to fetch` despite the backend
itself answering direct HTTP calls with `200`).

Configuration:
- Explicit allowed origins: `http://localhost:1420` (Tauri dev server),
  `tauri://localhost`, `https://tauri.localhost`, `http://tauri.localhost`
  (the three Tauri-v2 packaged-WebView origin candidates — which one a real
  Windows install presents was not independently observable in the Linux
  sandbox at the time this was written)
- `allow_credentials=False`
- `allow_methods=["GET", "POST", "OPTIONS"]`
- `allow_headers=["Content-Type"]`
- `SOCIQ_ALLOWED_ORIGINS` environment-variable escape hatch for pinning an
  additional exact origin without a further source edit
- No wildcard (`*`) origin anywhere

Added: `tests/test_api_cors.py` (6 tests).

No other route, command-dispatch logic, or response schema was touched.

## 4. Dedicated CORS Verification

**Linux sandbox (Category A):** `pytest tests/test_api_cors.py -v` → 6/6
passed (permitted dashboard preflight, permitted cross-origin POST,
disallowed-origin rejection, dev-server origin, health-endpoint
preservation, unknown-command envelope preservation).

**Windows (Category B, operator-reported):** dedicated CORS suite — **6
passed**, covering the same six cases. A pre-existing
`starlette`/`httpx` deprecation warning was also observed; recorded as a
warning only, no dependency change made because of it.

## 5. Full Backend Test Baseline

**Linux sandbox, non-GUI suite (Category A):** 1129 passed before the
change, 1135 passed after (1129 + 6 new CORS tests), 0 failed, 0
regressions. GUI suite (`tests/gui`, PySide6-dependent) was not run in the
Linux sandbox — PySide6 was not installed there.

**Windows, full suite including GUI (Category B, operator-reported):**
**1235 passed, 3 failed, 1 skipped, 3 subtests passed, 1 warning.**

Reported failures:
1. `tests/test_api_layer.py::CommandRouteTests::test_export_report_not_found_is_translated_not_raised`
2. `tests/test_application_layer.py::DispatchErrorTranslationTests::test_export_report_translates_exporter_write_failure`
3. `tests/test_export_path_traversal_adversarial.py::ExportPathTraversalAdversarialTests::test_unc_style_string_on_this_platform_is_rejected_conservatively`

Per the operator's report, all three were reproduced with the same
behavior against the unmodified R3-E baseline, and are therefore
classified **pre-existing, not introduced by R4-B0**. This classification
rests on the operator's own baseline comparison — it was not independently
re-run in the Linux sandbox. No test or production code was modified to
address these failures, per the closure task's explicit scope limits.

## 6. Windows Toolchain (Category B, operator-reported)

- Windows 11
- Python 3.14.6
- FastAPI 0.141.1, Pydantic 2.13.5
- PySide6 6.11.2, ReportLab 5.0.1, Requests 2.34.2, Platformdirs 4.9.4
- PyInstaller 6.22.2
- Node 22.23.2, npm 10.9.8
- Rust `rustc 1.97.1`, Cargo `1.97.1`
- Target: `x86_64-pc-windows-msvc`

## 7. Frontend Verification

**Linux sandbox (Category A):** `npm ci` succeeded (159 packages); `npm
exec tsc -- --noEmit` — 0 errors; `npm run build` — succeeded, 192 modules
transformed; 2 vulnerabilities reported (1 moderate, 1 high, in
`esbuild`/`vite`), not fixed; `package.json`/`package-lock.json` confirmed
byte-identical to the R3-E baseline (no dependency drift).

**Windows (Category B, operator-reported):** `npm ci` succeeded — 155
packages installed, 156 audited; 2 vulnerabilities reported (1 moderate, 1
high), no audit fix run; `tsc --noEmit` — clean pass; `npm run build` —
pass, Vite reported 192 modules transformed.

*(Package-count discrepancy note — 159 vs. 155/156 packages installed
between the two environments: not investigated further here, as it does
not affect `package-lock.json`, which is confirmed identical to baseline
in the Linux sandbox; likely explained by platform-conditional optional
dependencies, which npm resolves differently per-OS from the same
lockfile.)*

## 8. Windows Backend Sidecar Build (Category B, operator-reported)

Command: `packaging\scripts\build_backend.py --target-triple x86_64-pc-windows-msvc`

- Output: `src-tauri\binaries\socq-backend-x86_64-pc-windows-msvc.exe`
- Size: 29,857,818 bytes
- SHA-256: `033EB074BB6AA012AB2B0D553B484347706513E82CD742C620D46929576692BE`
- Build warning observed: `Hidden import "tzdata" not found!` — recorded
  as a build warning; production build completed and subsequent runtime
  verification succeeded, so treated as non-blocking per the operator's
  report. Not investigated or fixed as part of this closure.

## 9. Tauri Windows Production Build (Category B, operator-reported)

Command: `.\frontend\node_modules\.bin\tauri.cmd build`

Result: PASS. Rust release compilation succeeded. Both configured installer
formats (`msi`, `nsis`) were produced.

Rust warnings reported: unused import `RestartToken`; unused method
`is_pending`. Recorded as warnings, not build failures; not fixed as part
of this closure (source-change scope excludes it).

### Artifacts (Category B, operator-reported)

| Artifact | Path | Size | SHA-256 |
|---|---|---|---|
| Backend sidecar | `src-tauri\binaries\socq-backend-x86_64-pc-windows-msvc.exe` | 29,857,818 bytes | `033EB074BB6AA012AB2B0D553B484347706513E82CD742C620D46929576692BE` |
| Main executable | `src-tauri\target\release\soc-iq.exe` | 3,676,160 bytes | `2CF7C62ACB807ADE894579D4F45EC9C933C1602F9EC9F8BF41E77371B2028805` |
| MSI | `src-tauri\target\release\bundle\msi\SOC-IQ_0.1.0_x64_en-US.msi` | 31,453,184 bytes | `31D36A0F36B3D42CCD9BC211B2D8FA9EA0B81DD0429843FC7915FEE0833A44B5` |
| NSIS | `src-tauri\target\release\bundle\nsis\SOC-IQ_0.1.0_x64-setup.exe` | 30,982,362 bytes | `260D411175643C49718105325AE86396EB84A6173292F2CCA52F6B545753C353` |

None of these four hashes/sizes were independently recomputed outside the
Windows environment that reported them — no such artifact exists in, or
was producible from, the Linux sandbox.

## 10. MSI Installation / Runtime / Uninstall (Category B, operator-reported)

- Initial non-elevated silent install failed (Windows Installer error
  1925/1603) — the PowerShell session was at Medium Mandatory Level.
- An elevated (`RunAs`, High Mandatory Level) session then installed
  successfully (`$LASTEXITCODE = 0`).
- Registered as Product `SOC-IQ`, Version `0.1.0`, Provider MSI.
- Installed to `C:\Program Files\SOC-IQ\soc-iq.exe` and
  `C:\Program Files\SOC-IQ\socq-backend.exe`.
- First runtime launch reproduced the original pre-remediation CORS
  failure (`Dashboard Unavailable` / `Failed to fetch`) — this is recorded
  as the historical evidence that motivated the R4-B0 fix, **not** a
  current R4-B0 failure; direct backend calls (`/docs`, `get_dashboard_summary`)
  returned HTTP 200 throughout, matching the original diagnostic.
- MSI was subsequently uninstalled; installation directory and processes
  reported cleaned successfully.

**Note:** per the closure task's explicit scope (§9 of the closure brief:
"do not describe the original CORS failure as a current R4-B0 failure"),
this section documents the pre-remediation reproduction only. The
post-remediation MSI Dashboard-load result is not separately reported
here — see §11 for the NSIS post-remediation runtime evidence, which is
the lifecycle that was reported end-to-end with the fix in place.

## 11. NSIS Installation / Runtime / Uninstall (Category B, operator-reported)

Installer: `SOC-IQ_0.1.0_x64-setup.exe` (SHA-256 as in §9 table).

- Registered: DisplayName `SOC-IQ`, DisplayVersion `0.1.0`, Provider
  Programs, InstallLocation `D:\cyber projects`, UninstallString
  `D:\cyber projects\uninstall.exe`.
- **Note:** installed outside the Windows-conventional `C:\Program Files`
  location — into `D:\cyber projects` instead. Recorded as observed, not
  investigated further in this closure pass (would require inspecting the
  NSIS installer script/config, which is out of this task's scope).
- One transient first-launch observation was reported: an initial error
  on first open, followed by successful opening after interaction. No
  root cause is claimed for this — recorded exactly as observed, per the
  operator's explicit instruction not to invent one. A second launch
  opened normally.
- Post-launch runtime verification reported: SOC-IQ and backend child
  processes running; an active localhost backend port listening; `/docs`
  → HTTP 200; `get_dashboard_summary` → HTTP 200; **Dashboard UI rendered
  normally with the expected empty-state values**; Analysis Engine showed
  "Connected"; Quick Actions available.
- Classified by the operator as: **PASS WITH DOCUMENTED TRANSIENT
  FIRST-LAUNCH OBSERVATION.**
- Uninstall via `D:\cyber projects\uninstall.exe` completed successfully;
  post-uninstall verification confirmed the registry entry, `soc-iq.exe`,
  `uninstall.exe`, and `socq-backend.exe` all removed, and no SOC-IQ
  processes remained.

This is the one lifecycle in this document where the *post-remediation*
Dashboard was reported as actually loading successfully on real Windows —
the concrete evidence that the CORS fix worked against a real packaged
WebView, not just against `TestClient` in the Linux sandbox.

## 12. Installer Authority

`src-tauri/tauri.conf.json` configures `"targets": ["msi", "nsis"]`. Both
were built (Category B) and both were independently runtime-verified
(Category B, §10–§11). No project document designates one as the sole
authoritative release installer.

**Status: MSI and NSIS are both configured and operational; no single
authoritative installer format is explicitly designated by project
configuration.** Recorded as a release-governance/documentation condition,
not a functional failure. Not resolved in this closure pass, per explicit
instruction not to silently choose one.

## 13. Version Metadata

Unchanged from prior audits: Tauri/Cargo/frontend package version `0.1.0`
vs. Python `APP_VERSION = "1.0.0"`. Not modified during this closure.
Recorded as a documented release/version-governance condition.

## 14. Warnings / Conditions Summary

1. Three backend test failures (§5) are pre-existing from R3-E per the
   operator's baseline comparison, not introduced by R4-B0.
2. One PyInstaller hidden-import warning (`tzdata`) — non-blocking per
   reported build/runtime success.
3. Two non-fatal Rust warnings (unused import, unused method).
4. npm reports 1 moderate + 1 high vulnerability (`esbuild`/`vite`); no
   fix applied (out of scope; would mutate the frozen dependency graph).
5. NSIS had one transient, uncharacterized first-launch observation;
   subsequent launch and full runtime verification passed.
6. MSI installation required an elevated (RunAs) session in the tested
   environment; non-elevated install failed with Windows Installer errors
   1925/1603.
7. MSI and NSIS are both configured; installer authority remains
   undocumented (§12).
8. Version metadata mismatch remains open (§13).
9. **All of §6–§11 (Windows toolchain, builds, artifact hashes,
   install/launch/uninstall lifecycles) is Category B — reported by the
   Windows operator and not independently reproduced or verified by the
   agent that authored this document.** Only §3–§5 (remediation source,
   dedicated CORS tests, and the non-GUI backend/frontend checks run in
   the Linux sandbox) are Category A.

## 15. Final Verdict

**PASS WITH DOCUMENTED CONDITIONS — R4-B0 CORS REMEDIATION VERIFIED
(Category A, in-sandbox) AND WINDOWS INSTALLER/RUNTIME LIFECYCLES REPORTED
(Category B, operator-observed, not independently reproduced)**

This verdict should be read as two layered claims, not one: the CORS fix
itself is independently, mechanically verified (source diff, dedicated
tests, full non-GUI regression suite, all executed and observed directly).
The Windows packaging, installer, and install/launch/uninstall lifecycle
evidence is real operator-reported data, consistent internally and with
the earlier R4-A diagnostic, but exists in this document as a transcription
of that report — not as something the closure-document author verified
independently, because no Windows/Rust/installer toolchain is available in
that environment.

## 16. Evidence Limitations

- No Windows toolchain, Rust compiler, or installer tooling exists in the
  environment that authored this document or the R4-B0 source checkpoint;
  every Windows-side fact above is transcribed from the operator's report,
  not independently reproduced.
- The three pre-existing test failures (§5) were not independently
  re-run against the R3-E baseline by this document's author to confirm
  they are unrelated to R4-B0 — that comparison is the operator's own.
- The NSIS transient first-launch observation (§11) has no established
  root cause; none is claimed here.
- The `D:\cyber projects` NSIS install-location deviation from
  `C:\Program Files` (§11) is recorded but not investigated.
