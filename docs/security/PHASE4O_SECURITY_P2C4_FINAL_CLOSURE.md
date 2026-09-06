# §20 Report Ingestion Size Cap — Final Closure (Part 2C-4)

## Control closed
```
Control: Report ingestion size cap (app/extractor.py::read_report())
Authoritative requirement: docs/security/report-ingestion-security-model.md
        TARGET STATE ("Explicit input size limits are enforced ... before
        a report reaches the extraction pipeline"); threat-model.md's
        "Oversized report / regex DoS" row.
Threat: An oversized report read fully into memory before regex
        IOC-extraction passes -- an uncapped local resource-exhaustion
        vector, reachable via analyze_report (HTTP/IPC) and the CLI.
Security invariant: A report above MAX_REPORT_SIZE_BYTES (10 MB) is
        rejected via ReportReadError, based on a stat()-only size check
        performed before the file is ever opened.
Production enforcement: app/extractor.py::read_report(), the single
        production reader for report content, called by every current
        entrypoint (analyze_report over HTTP/IPC, and the CLI path in
        app/main.py, both of which resolve to the same
        app.analyzer.analyze_report() function).
Adversarial verification: PASS
```

Independently re-confirmed in this closure pass, against the source
extracted fresh from `SOC-IQ-Phase4O-SECURITY-P2C3-ADVERSARIAL-VERIFIED.zip`
(not assumed from the Part 2C-3 report):
- the size-check line is present in `app/extractor.py` at the expected
  location, ahead of the only `Path.open()` call in the function;
- an oversized report is rejected through the real FastAPI HTTP transport
  (`POST /commands/analyze_report`), through the direct handler entrypoint,
  and via a mutation-kill re-check (neutralizing the check locally fails
  5 of the 12 dedicated tests; the file was restored immediately after);
- a normal sample report and an exactly-at-cap report both still succeed;
- no alternate reader, environment-variable override, or duplicate
  `MAX_REPORT_SIZE_BYTES`-equivalent constant exists anywhere else in the
  repository.

No production change was required in this part -- the control was already
sound going in, and no new defect was found.

## §20 Status Matrix
```
Part 1B — Rust Keystore                         CLOSED
Part 2A — Capability Manifest                    CLOSED
Part 2B — Export Path Traversal                  CLOSED
Part 2C — Report Ingestion Size Cap              CLOSED (this checkpoint)
IPC / CSP loopback wildcard                      DEFERRED (docs/security/
        ipc-security-model.md; explicit pending product decision between
        binding the actual runtime port vs. documenting loopback +
        capability restriction as the boundary -- unrelated to Part 2C,
        untouched here, per hard scope boundary)
Regex catastrophic-backtracking review           DEFERRED (spot-checked by
        hand in Part 2C-1, not re-verified with an automated ReDoS fuzz
        pass in any part; the size cap bounds worst-case cost to a fixed
        ceiling regardless -- that is the property Part 2C is responsible
        for, not a full ReDoS audit)
```

This matrix reflects only the §20 controls with authoritative requirement
documents identified across Parts 2C-1 through 2C-4. It does not claim §20
in its entirety is closed -- the two DEFERRED items above remain open
product/engineering decisions outside this control's scope.

## Final Verification Matrix
```
Selected security control          PASS
Adversarial verification           PASS
Positive/legitimate behavior       PASS
Regression test quality            PASS (mutation-kill re-confirmed)
Bypass audit                       PASS
Documentation accuracy             PASS

Part 2A                             PASS  (22/22)
Part 2B                             PASS  (18/18)
Part 1B                             PASS  (35/35; 0 direct keyring imports
                                            in production app/)
Phase 4O                            PASS  (66/66 app/gui files retained,
                                            7/7 GUI test suites, no legacy
                                            production dependency found)

Backend                             PASS  (850 passed)
GUI                                 PASS  (104 passed)
Frontend                            PASS  (965 passed, 70 files)
TypeScript                          PASS  (0 errors)
Frontend build                      PASS  (193 modules)

keystore-core                       BLOCKED
sidecar-core                        BLOCKED
src-tauri cargo check                BLOCKED
src-tauri cargo test                 BLOCKED

Archive integrity                   PASS
Fresh extraction                    PASS
Extracted-copy verification        PASS
```

## Environment Limitations
No Rust toolchain (`cargo`/`rustc`) is available in this sandbox. This has
been true and reported identically across every session in this chain
(Part 2C-2, Part 2C-3, and this closure). No Rust source file was touched
by the report-ingestion-size-cap control at any point, so this limitation
does not bear on the control being closed here -- it is reported per the
brief's standing requirement to always state it.

## Changes (this part)
```
Production files changed: NONE
Test files changed: NONE
Documentation files changed:
  docs/security/PHASE4O_SECURITY_P2C4_FINAL_CLOSURE.md (this file, new)
Unrelated changes: NONE
```

## Final Verdict: PASS WITH CONDITIONS

The report-ingestion size-cap control is genuinely enforced, adversarially
verified, and regression-tested with no bypass found. Part 2A, Part 2B,
Part 1B, and Phase 4O all remain intact and independently re-verified from
the frozen source. The sole condition is the Rust toolchain being
unavailable in this sandbox (`keystore-core`, `sidecar-core`,
`src-tauri cargo check`/`cargo test` all BLOCKED) -- an environment
limitation, not a defect, and unchanged from every prior session in this
chain since no Rust file is implicated in this control.

```
§20 Part 2C Security Control: CLOSED

Part 2A Capability Control: PRESERVED

Part 2B Export Path-Traversal Control: PRESERVED

Part 1B Rust Keystore Control: PRESERVED

Phase 4O Migration State: PRESERVED

Authoritative checkpoint:
SOC-IQ-Phase4O-SECURITY-P2C-FINAL-FROZEN.zip
```

§20 as a whole is **not** claimed complete: the IPC/CSP loopback wildcard
item and the automated ReDoS fuzz pass remain explicitly DEFERRED, as
documented above and in Part 2C-1's own backlog audit.
