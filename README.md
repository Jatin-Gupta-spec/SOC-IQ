# SOC-IQ

Security Operations Center Intelligence & IOC Analysis Tool.

SOC-IQ analyzes malware/incident reports, extracts indicators of
compromise (IOCs), scores risk, enriches findings against threat
intelligence providers, and lets an analyst investigate, review
history, and export reports.

## Architecture

SOC-IQ is mid-migration from a PySide6 desktop GUI to a
Tauri (Rust) + React (TypeScript) desktop shell over a local Python
backend, communicating over a loopback HTTP + Server-Sent-Events
sidecar (see `docs/architecture/` for the full architecture set and
`docs/architecture/PROJECT_CONSTITUTION.md` / `NON_NEGOTIABLE_RULES.md`
for binding invariants).

```
frontend/     React + TypeScript UI (Vite, Vitest)
src-tauri/    Tauri desktop shell (Rust)
sidecar-core/ Sidecar process supervision (Rust)
app/          Python backend: analysis, scoring, threat intel,
              database, application/command layer, FastAPI sidecar
              (app/api/), and the legacy PySide6 GUI (app/gui/)
tests/        Backend + GUI test suites
docs/         Architecture, security, migration, and phase records
```

Major technologies: Python (FastAPI, SQLite, PySide6 for the legacy
GUI), TypeScript/React (Vite, Vitest), Rust (Tauri, sidecar
supervision).

### IOC / Threat Intel are investigation-scoped (PD-05)

Per **PD-05** (`docs/phase4/PD05_IOC_TI_TOPLEVEL_RETIREMENT.md`), there
is no top-level IOC Explorer or top-level Threat Intel destination.
IOC and threat-intelligence data are reached only through an
investigation:

```
Investigations
    ↓
Investigation Workspace
    ├── Overview
    ├── IOCs
    ├── Threat Intel
    └── Correlations
```

A direct or bookmarked navigation to the old `#/ioc-explorer` or
`#/threat-intel` paths falls through to the app's normal
unknown-path redirect (`/dashboard`) — those routes no longer exist.

## Current status — Phase 4O (closed, Option B)

The project has completed its architectural migration to the
Tauri + React + Python-sidecar stack. Phase 4O — legacy GUI
retirement — is closed under **Option B: complete with intentional
retained legacy**: 42 of the original 108 legacy `app/gui/**`
production files (and 5 of 12 `tests/gui/**` suites) have been
retired as provably redundant with the modern stack; **66 legacy
files and 7 test suites remain, intentionally**, because they cover
behavior with no verified modern equivalent yet. The legacy GUI is
**not** the shipped application's entrypoint — `app/main.py` is a
CLI entrypoint, the desktop shell is Tauri (`src-tauri/`, building
`frontend/dist`), and the FastAPI sidecar (`app/api/`) has no
dependency on `app.gui`.

Full rationale, verification evidence, and the intentionally-retained
list live in `docs/phase4/PHASE4O_FINAL_CLOSURE_AUDIT.md`.

### Modern frontend pages — integration status

There are five top-level destinations (`NAVIGATION_ITEMS`); IOC
Explorer and Threat Intel are not among them — see PD-05 above — and
neither is a standalone Risk page — see PD-06 below.

| Page | Status |
|---|---|
| Dashboard | Real, backend-integrated (`get_dashboard_summary` command) |
| Analyze | Real, backend-integrated — real file selection/validation, real `analyze_report` execution with SSE progress, real completed/failed result handling and retry (see "Analyze" below) |
| Investigations | Real, backend-integrated |
| Investigation Workspace (Overview / IOCs / Threat Intel / Correlations) | Real, backend-integrated |
| Reports | Real, backend-integrated (`export_report` command) |
| Settings | Real, backend-integrated — theme, export directory, and VirusTotal credential write all implemented; see "Settings" below |

There is no top-level Risk destination — see **PD-06** below. Real
risk score, severity, and confidence remain available, backend-
integrated, inside the Investigation Workspace's Overview tab
(`InvestigationOverviewRisk.tsx`) and on the Dashboard
(`DashboardRiskOverview.tsx`); the risk engine (`app/scoring/`) and
`RiskExplanationService` are unaffected by the standalone page's
retirement.

#### Analyze

The Analyze page drives a real `idle → ready → analyzing →
completed/failed` workflow (`frontend/src/pages/AnalyzePage.tsx`,
`pages/analyze/useAnalysisExecution.ts`) against the backend's
`analyze_report` command (`app/application/handlers.py`,
wrapping `app.analyzer.analyze_report`), consuming real progress over
the existing SSE event stream (`analysis.started` /
`analysis.progress`) and offering a real retry on failure. It does
not render IOC or Threat Intel detail inline — that remains the
Investigation Workspace's job, reached via the completed-analysis
handoff link.

#### Settings

| Capability | Current state |
|---|---|
| Theme persistence | Implemented — `ThemeControl.tsx` → `save_settings` (`SettingsService.update_theme`) |
| Export directory persistence | Implemented — `ExportDirectoryControl.tsx` → `save_settings` (`SettingsService.update_export_directory`) |
| VirusTotal credential write | Implemented — `VirustotalControl.tsx` → `keystore_set_secret` |

The modern Settings page (`frontend/src/pages/SettingsPage.tsx`) now
renders `ThemeControl`, `ExportDirectoryControl`, and
`VirustotalControl`, each wired to a real save path. Theme and export
directory go through the existing `save_settings` backend command
(`app/settings/service.py`, `app/application/handlers.py`). The
VirusTotal API key goes through the Rust `keystore-core` write path
(`keystore_set_secret`, registered as a Tauri command in
`src-tauri/src/keystore.rs`); saving updates the OS keystore
immediately, but the currently running Python sidecar keeps its
existing credential until the application is restarted — a process-
scoped environment-variable handoff at sidecar startup
(`src-tauri/src/sidecar.rs`) picks up the new credential on next
launch. Python does not read the OS keystore directly or via
`keyring` — it only observes that handoff (`app/secrets/store.py`),
read-only by construction.

### Product decisions

| Decision | Status |
|---|---|
| PD-02 — IOC Explorer investigation context/picker | MOOT — superseded by PD-05 |
| PD-03 — Threat Intel investigation context/picker | MOOT — superseded by PD-05 |
| PD-04 — Cross-investigation aggregate backend commands | DEFERRED |
| PD-06 — Standalone Risk page | RETIRE — implemented: page, route, navigation entry, and command-palette entry removed; the real risk engine, `RiskExplanationService`, and the Investigation Workspace's Overview risk region are unaffected |
| PD-07 — Settings | PARTIAL BUILD: theme + export directory — implemented, wired to `save_settings` |
| Settings — VirusTotal credential write path | ADR-008 / Part 1B-3 — implemented, wired to `keystore_set_secret` |

Full rationale for each: `docs/phase4/PD05_IOC_TI_TOPLEVEL_RETIREMENT.md`
(PD-02 through PD-05), `docs/phase4/PD06_STANDALONE_RISK_RETIREMENT.md`,
`docs/phase4/PD07_SETTINGS_PARTIAL_BUILD.md`.

## Testing / verification status

As of the Part 3 standalone-Risk-retirement closure (PD-06 implemented
in code; see the product decisions table above), re-run directly
against this checkpoint:

- Backend: `pytest tests/` (non-GUI) → 856 passed (re-run this session); `tests/gui` (offscreen) — not re-run this session (`PySide6` not installed in this sandbox)
- Frontend: `npx vitest run` → 1006 passed (77 files, re-run this session); `npx tsc --noEmit` → clean; `npm run build` → succeeds (189 modules)
- Rust (`src-tauri/`, `sidecar-core/`, `keystore-core/`): **environment-blocked** — no working `cargo`/`rustc` toolchain (and missing GTK/WebKit headers for a full Tauri build) in the verification sandbox; not run

**Phase A1 re-verification (later session, `cargo`/`PySide6` available)** —
corrects the two environment-dependent claims above, which were
accurate for *that* sandbox but are not universally true:

- Backend, full: `pytest --ignore=tests/gui` → **883 passed**; `pytest tests/gui` (PySide6 6.11.2 installed) → **104 passed**. 987/987 collected, 0 failed. (The 856 vs. 883 gap vs. the entry above reflects tests added since that session, not a regression — see the repo's own commit/phase history for what changed.) One finding from this pass: `tests/test_reporting.py::test_pdf_exporter_includes_all_four_ti_categories` depends on `pypdf`, which was not declared in `requirements.txt` — it happened to already be present in this particular verification environment, but a clean install from `requirements.txt` alone would silently *skip* this test rather than run it. Declared now (`requirements.txt`, optional/test-only) — see that file's own comment for why it's kept separate from the required set.
- Frontend, re-confirmed unchanged: `npx vitest run` → 1006 passed (77 files); `npx tsc --noEmit` → clean; `vite build` → succeeds (189 modules).
- Rust: `cargo` **is installable** (`apt-get install cargo` → rustc/cargo 1.75.0) and is not universally blocked. With that toolchain: `keystore-core` → `cargo test` → **15 passed, 3 correctly self-skipped** (real-OS-keystore-only tests). `sidecar-core` → `cargo test` → **36 passed** (23 + 13 across two suites). `src-tauri` → `cargo check` fails specifically on a transitive dependency (`dlopen2_derive`) requiring Rust's `edition2024`, which Cargo/rustc 1.75 does not support — this one crate genuinely needs a newer toolchain than apt provides here; it is not a general "no cargo" problem, and `keystore-core`/`sidecar-core` were deliberately pinned to `rust-version = 1.75` in their own `Cargo.toml` for exactly this reason (see those files' own comments) — confirmed correct by this test.

**Phase A2 re-verification** (same findings, independently re-run to build the CI workflow below): `pytest` (non-GUI + `tests/gui`, offscreen) → **987/987 passed**; frontend `npx vitest run` → **1006 passed** (77 files), `npx tsc --noEmit` → clean, `npm run build` → succeeds (189 modules); `keystore-core` → `cargo test` → **15 passed, 3 correctly self-skipped**; `sidecar-core` → `cargo test` → **36 passed**; `src-tauri` → `cargo check` still fails on the same `edition2024` requirement under this sandbox's apt-provided Rust 1.75.0 — unchanged from Phase A1's finding, so the CI workflow below uses a current stable toolchain (`dtolnay/rust-toolchain@stable` on `ubuntu-latest`) rather than the sandbox's fixed 1.75.0, precisely to cover that crate.

## Continuous integration

`.github/workflows/ci.yml` runs on every push and pull request and is the
project's automated quality gate. Three independent jobs cover the three
technical surfaces above:

| Job | What it runs | Authoritative source |
|---|---|---|
| `python` | `pytest` (non-GUI + `tests/gui`, offscreen) against `requirements.lock.txt` | `pytest.ini`, this README's own verified command |
| `frontend` | `npm ci`, `npm test` (Vitest), `npm run typecheck` (`tsc --noEmit`), `npm run build` | `frontend/package.json` scripts |
| `rust` | `cargo test` for `keystore-core` and `sidecar-core`; `cargo check` + `cargo test` for `src-tauri` (Linux, current stable toolchain, Tauri's documented Linux build dependencies installed) | each crate's own `Cargo.toml` |

**What CI validates:** that the real, current test suites for all three
layers pass from a clean checkout, that the frontend type-checks and
produces a production build, and that all Rust crates — including
`src-tauri`, which this sandbox's fixed Rust 1.75.0 toolchain cannot check
(see above) — compile and pass their non-GUI unit tests on Linux with a
current stable Rust toolchain.

**What CI does NOT validate:** it does not build, sign, or run the actual
Windows desktop application (`SOC-IQ.exe`), does not produce or verify the
MSI/NSIS installers, and does not exercise the real Tauri webview/GUI at
runtime. Windows-native release verification remains a release-engineering
responsibility (`packaging/scripts/build-windows.ps1`,
`docs/architecture/18-packaging-release-architecture.md`), not something a
Linux-hosted CI job can honestly claim to cover.

No secrets or external network/API access are required to run this
workflow: VirusTotal access is mocked in tests, and `tests/gui/conftest.py`
sets `QT_QPA_PLATFORM=offscreen` itself.

A status badge is intentionally not embedded here yet: this checkpoint is
not yet pushed to a GitHub repository, and a badge URL pointing at a
nonexistent repo would be exactly the "fake/static badge" this phase's own
brief prohibits. Once pushed, add:
`[![CI](https://github.com/<owner>/<repo>/actions/workflows/ci.yml/badge.svg)](https://github.com/<owner>/<repo>/actions/workflows/ci.yml)`.

## Known limitations

- There is no top-level IOC Explorer or Threat Intel page by design
  (PD-05), and no top-level Risk page by design (PD-06); that
  functionality lives in the Investigation Workspace (and, for risk,
  the Dashboard).
- Bulk CSV export of investigation history, the "why this risk?"
  narrative, and the per-category risk-significance badge exist only
  in the legacy GUI; no modern equivalent has been built or verified.
- Rust: `keystore-core` and `sidecar-core` build and pass their full
  test suites given a Rust 1.75+ toolchain. `src-tauri` itself
  additionally needs a Rust toolchain new enough for `edition2024`
  (not just any working `cargo`) — that specific requirement is
  unverifiable in this sandbox (fixed apt-provided Rust 1.75.0) but is
  covered by CI (`.github/workflows/ci.yml`'s `rust` job uses a
  current stable toolchain on `ubuntu-latest`).
- CI (`.github/workflows/ci.yml`) validates all three layers on Linux
  only. It does not build, package, sign, or runtime-test the actual
  Windows desktop application — see "Continuous integration" above.
- `npm audit` (Phase A3 baseline) reports one moderate/high finding:
  `esbuild <=0.24.2` (via `vite`) allows any website to send requests to
  the local Vite **dev server** and read the response
  ([GHSA-67mh-4wv8-2f99](https://github.com/advisories/GHSA-67mh-4wv8-2f99)).
  This affects `npm run dev` only, not the production build `npm run
  build` produces or the shipped app — no `esbuild`/dev-server code ships
  in `frontend/dist`. The fix (`npm audit fix --force`) is a breaking
  `vite` 5→8 major-version upgrade, out of scope for A3's no-mass-upgrade
  rule; tracked here as a confirmed, currently-unremediated, low-blast-
  radius finding for a future dependency-modernization phase.
- `LICENSE` is present and contains the MIT License (Gate 1 closure). See `THIRD-PARTY-NOTICES.md` for the separate, evidence-based inventory of third-party dependency licenses, which remain governed by their own respective terms.
- No Python lockfile is committed as policy; `requirements.lock.txt`
  (added in Phase A1) is an additive, verified-good pin snapshot for
  reproducible installs, not a replacement for `requirements.txt`'s
  floor-based policy — see that file's own header for why.
- No `database/soc_iq.db` test-isolation layer exists: several backend
  tests deliberately snapshot/restore the real default-path database
  file around themselves (see `tests/test_application_layer.py`,
  `tests/test_integration_e2e.py`, `tests/test_analyzer_pipeline_options.py`)
  rather than using an isolated fixture database. This works today but
  is a fragile pattern worth revisiting in a future phase — out of
  scope for Phase A1 (test architecture, not repository hygiene).

## Getting started

Backend dependencies: `pip install -r requirements.txt` (or
`pip install -r requirements.lock.txt` for the exact, Phase-A3-verified
pin set — see that file's header). Supported Python: 3.12
(`.python-version`).
Frontend dependencies: `cd frontend && npm install` (or `npm ci` for a
reproducible install from the committed lockfile). Supported Node: 22
(`frontend/.nvmrc`, `frontend/package.json`'s `engines.node`).

Exact run/build commands are defined in `frontend/package.json`
(`npm run dev`, `npm run build`) and `src-tauri/tauri.conf.json`.

Full dependency-management model (what's authoritative per ecosystem, how
CI installs, how to update a dependency): see
`docs/security/dependency-supply-chain-security-model.md`.
