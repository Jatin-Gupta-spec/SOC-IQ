# §20 Security Hardening — Backlog Reconciliation (Part 2D-1)

Audit-first pass. No production code, test, or behavior changes were made
in this part. The one incidental change during exploration — this
session's own manual adversarial calls writing to `database/soc_iq.db` —
was reverted before packaging; the repository in this checkpoint is
byte-identical to `SOC-IQ-Phase4O-SECURITY-P2C-FINAL-FROZEN.zip` except for
this new document.

## §20 Master Matrix

| Control | Authority | Threat | Current State | Tests | Status |
|---|---|---|---|---|---|
| Rust-owned OS keystore, Python read-only | ADR-008; `docs/security/secret-management-model.md` | API-key theft via Python-side keyring access | Rust owns secret storage; Python has no direct `keyring` import in production | `tests/test_architecture_no_direct_keyring.py`, `tests/test_secret_store.py` — 35 passed | **CLOSED** |
| Tauri capability manifest snapshot | `docs/security/tauri-capability-model.md`; ADR-010 | Undetected capability/scope expansion (privilege creep) | Snapshot present, deterministic, diffed against committed baseline | `tests/test_architecture_capability_snapshot.py` — 22 passed | **CLOSED** |
| Export path traversal | `docs/security/filesystem-security-model.md`; threat-model.md "Path traversal on export" row | Frontend-supplied path escapes the intended export directory | Export path resolution happens through capability-scoped writers, not a trusted raw string | `tests/test_export_path_traversal_adversarial.py` — 18 passed | **CLOSED** |
| Report ingestion size cap | `docs/security/report-ingestion-security-model.md` TARGET STATE; threat-model.md "Oversized report / regex DoS" row | Uncapped report read → local resource exhaustion before regex passes | `read_report()` rejects via `stat()` before any `open()`, single choke point for every caller | `tests/test_report_ingestion_size_cap.py` — 12 passed, mutation-kill re-confirmed | **CLOSED** (Part 2C) |
| Phase 4O legacy GUI retirement | `docs/phase4/PHASE4O_FINAL_CLOSURE_AUDIT.md` | Stale/duplicate legacy production entrypoint reappearing | 66/66 `app/gui` files retained as designed, 7/7 GUI test suites present, no legacy production entrypoint found on search | GUI suite — 104 passed | **CLOSED** |
| IPC/CSP loopback wildcard | `docs/security/ipc-security-model.md` §"CSP / Loopback Wildcard" | Overly broad `connect-src 'self' http://127.0.0.1:*` lets the webview reach any loopback port, not just the sidecar's, widening blast radius if the webview is ever compromised (e.g. malicious/compromised JS dependency) | `src-tauri/tauri.conf.json` still carries the wildcard, unchanged since the Phase 4A foundation checkpoint. The doc's own stated blocker — "no sidecar supervisor exists yet to hand a concrete port to the CSP" — is **no longer true**: `app/api/entrypoint.py` now performs the documented synchronous stdout port handshake, `src-tauri/src/sidecar.rs` reads it, and `frontend/src/shared/api/client.ts` resolves the sidecar origin at runtime via the `get_sidecar_origin` Tauri command and never hardcodes a port. The doc explicitly says "Phase 2A must reconcile before it can call this closed" — the codebase is now well past Phase 2A. | None (the wildcard itself was never exercised by an adversarial test — no XSS/JS-injection vector exists in this codebase to demonstrate live exploitation, matching the doc's original note that "nothing exploits this yet") | **OPEN** |
| Dependency/supply-chain locking + audit | `docs/security/dependency-supply-chain-security-model.md`; threat-model.md "Dependency/supply-chain attack" row | Unpinned/floor-only dependency versions let a compromised or unexpectedly-upgraded package enter a build silently | Python: `requirements.txt` uses minimum-version floors only, no `requirements.lock`. Frontend: `frontend/package-lock.json` **is** committed (npm, not the doc's proposed pnpm, but a real lockfile). Rust: `Cargo.lock` **is** committed for all three crates (`src-tauri`, `keystore-core`, `sidecar-core`). No CI workflow of any kind exists in the repository, so none of `pip-audit`/`cargo audit`/`npm audit` is enforced anywhere. | None | **OPEN** (partial: 2 of 3 ecosystems already have committed lockfiles; Python does not, and no ecosystem has enforced auditing) |
| Regex catastrophic-backtracking review | `docs/security/report-ingestion-security-model.md`; threat-model.md UNKNOWN section | Pathological regex input causing worst-case backtracking cost | Hand-spot-checked in Part 2C-1 (no obviously pathological pattern shape found); size cap (Part 2C, closed) already bounds worst-case cost to a fixed ceiling regardless of this review's outcome | None (no automated ReDoS fuzz pass performed in any part) | **DEFERRED** (bounded by the closed size cap; not re-selected as blocking) |
| OS-level sandboxing beyond loopback bind (e.g. Windows Firewall scoping) | `docs/security/ipc-security-model.md` UNKNOWN section | Same-machine process reaching the sidecar despite loopback binding | Loopback binding alone already prevents off-machine reachability; doc explicitly frames this as a future hardening consideration, not a current gap | None | **NOT YET JUSTIFIED** |
| Reproducible builds / signed release artifacts | `docs/security/dependency-supply-chain-security-model.md` | Tampered release artifact | Explicitly scoped as a **V1** (post-initial-release) goal by the doc itself, not required pre-release | None | **NOT REQUIRED** (by the authoritative doc's own scoping) |
| Export/save-dialog Tauri capabilities in target-state table | `docs/security/tauri-capability-model.md` | N/A — feature not built | Doc explicitly states these "remain unimplemented and untested until that feature is built" | N/A | **NOT REQUIRED** (no feature exists yet to secure) |
| src-tauri / keystore-core / sidecar-core Rust test execution | Part 1B, Phase 4O, Part 2C verification requirements | N/A — tooling availability, not a code defect | No `cargo`/`rustc` in this sandbox, unchanged across every session in this entire §20 chain (2C-2 through this part) | N/A | **ENVIRONMENT BLOCKED** |

## Closed Controls (independently re-verified this pass, from the extracted checkpoint, not assumed)
- **Part 1B — Rust Keystore:** 35/35 passed (`test_architecture_no_direct_keyring.py`, `test_secret_store.py`); zero direct `keyring` imports found in production `app/` by direct search.
- **Part 2A — Capability Manifest:** 22/22 passed; committed snapshot fixture confirmed present and matched by the current manifest.
- **Part 2B — Export Path Traversal:** 18/18 passed.
- **Part 2C — Report Ingestion Size Cap:** 12/12 passed; the size check confirmed still present at its expected location in `app/extractor.py`.
- **Phase 4O — Legacy GUI Retirement:** 66 `app/gui` files present, 7 GUI test files present (`test_*.py` under `tests/gui/`, excluding `__init__.py`/`conftest.py`), 104 GUI tests passed; no `legacy_gui`/`LegacyGUI`/`app.legacy` reference found anywhere in production `app/`.

## Remaining Controls

**OPEN**
- IPC/CSP loopback wildcard (see matrix above — the documented technical blocker is now resolved; this is a genuine, evidence-based open item, not an invented one)
- Dependency/supply-chain locking + audit (Python lockfile absent; no CI-enforced audit in any ecosystem)

**DEFERRED**
- Regex catastrophic-backtracking automated review (bounded, not blocking, by the already-closed size cap)

**NOT REQUIRED**
- Reproducible builds / signed artifacts (explicitly V1-scoped by the authoritative doc)
- Export/save-dialog capability hardening (feature does not exist yet)

**ENVIRONMENT BLOCKED**
- All `cargo`-dependent verification (`keystore-core`, `sidecar-core`, `src-tauri cargo check`/`cargo test`)

**NOT YET JUSTIFIED**
- Additional OS-level sandboxing beyond loopback bind (explicitly framed by its own doc as a future consideration, not a current gap; loopback binding is already the enforced boundary)

No product-decision items (risk narrative, risk significance, bulk CSV
behavior, settings scope, Threat Intel navigation, incomplete mock
screens) were found or reopened as security work in this pass.

## Next-Control Decision

### OPTION A
```text
NEXT CONTROL:
IPC/CSP loopback wildcard reconciliation

Authority:
docs/security/ipc-security-model.md, "CSP / Loopback Wildcard
(Pre-2A Foundation Note)" section

Threat:
An overly broad connect-src (any loopback port, not just the sidecar's)
widens the blast radius available to any future webview compromise
(malicious/compromised JS dependency, XSS) -- it could reach other
loopback services on the same machine, not just the intended sidecar.

Security invariant:
The frontend's CSP permits network access to no more loopback surface
than the actual sidecar port in use (or the wildcard is formally kept
and documented as accepted defense-in-depth, with loopback binding +
Tauri capability restriction named as the actual, primary boundary --
per the doc's own explicitly offered "option (b)").

Implementation boundary:
src-tauri/tauri.conf.json (CSP string) and, only if the narrowing option
is chosen over the accept-and-document option, src-tauri's window/webview
construction code in src-tauri/src/lib.rs (Rust, requires a compiled
cargo build to verify -- ENVIRONMENT BLOCKED in this sandbox).

Tests:
If the narrow-CSP option is chosen: none of it is verifiable end-to-end
in this sandbox without a Rust toolchain. If the accept-and-document
option is chosen: no new test is generated by a documentation decision,
but the existing capability-manifest snapshot (Part 2A) and export/IPC
regression suites remain the regression guard for the invariants that
option relies on (loopback bind, capability restriction).
```

**Recommendation for Part 2D-2:** given this sandbox has no Rust
toolchain (confirmed blocked across every part of this chain), a
same-session, adversarially-verifiable implementation of the *narrow*
option is not achievable here -- there is no way to compile or test
Rust-side CSP injection in this environment. The lower-risk, fully
verifiable path is the doc's own pre-offered option (b): formally close
this item by documenting loopback binding + Tauri capability restriction
as the accepted primary boundary and the wildcard as intentional,
scoped-to-loopback defense-in-depth -- a documentation decision requiring
no unverifiable Rust change, consistent with the minimal-remediation
discipline this chain has followed throughout. Part 2D-2 should make and
record that explicit choice (or, if a real Rust-capable environment
becomes available, implement and verify the narrow-CSP option instead).

The dependency/supply-chain item (Python lockfile + CI auditing) is
real but is process/tooling work rather than an adversarially-testable
application-code control in the shape of Parts 2A/2B/2C, and this sandbox
has no CI runner to validate a workflow against. It is recorded as OPEN
in the matrix above but not selected as the Part 2D-2 target.

## Baseline Results (actual, this session, re-run from the extracted P2C-FINAL-FROZEN checkpoint)
```
Selected-control + Part 2A/2B/1B combined suite:  87 passed
Full backend (pytest tests/, excl. GUI):          850 passed
GUI suite (offscreen):                            104 passed
```
Frontend/TypeScript/build were not re-run in this audit-only pass (no
source changed since the Part 2C-4 checkpoint, where they were already
verified as: tsc 0 errors, vitest 965/965, build 193 modules); re-running
an unchanged frontend against an unchanged frontend adds no new
information and this part's scope is documentation-only per its own
change-scope rule.

## Environment Limitations
No Rust toolchain (`cargo`/`rustc`) in this sandbox -- unchanged from
every prior part in this chain. `keystore-core`, `sidecar-core`,
`src-tauri cargo check`/`cargo test`: **ENVIRONMENT BLOCKED**.

## Changes
```
Production: NONE
Tests: NONE
Documentation: docs/security/PHASE4O_SECURITY_P2D1_BACKLOG_RECONCILIATION.md (new)
Unrelated: NONE
```
