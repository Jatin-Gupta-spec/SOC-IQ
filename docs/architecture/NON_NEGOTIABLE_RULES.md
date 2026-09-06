# SOC-IQ — Non-Negotiable Rules

Authority: #2 in the hierarchy (`PROJECT_CONSTITUTION.md` §12). If any other document seems
to permit something on this list, this list wins. If uncertain whether a proposed change
violates one of these, STOP and ask, or document the uncertainty in
`UNKNOWN_AND_ASSUMPTIONS.md` — do not guess.

1. Do not rewrite proven domain logic (`extractor.py`, `analyzer.py`, `scoring/`, the
   database repository layer) without direct source evidence that it's wrong. "Cleaner" is
   not evidence.
2. Do not let Rust contain business logic. Rust supervises the sidecar process and owns
   native OS capabilities only.
3. Do not let React contain business logic (scoring, TI verdict computation, correlation).
4. Do not let the frontend access SQLite directly.
5. Do not let the frontend call external TI provider APIs directly.
6. Do not let the Python domain depend on Qt (already true; keep it true as GUI code is
   retired — don't let a "temporary" import creep back in).
7. Do not create a second event system. One event model, one publisher — see
   `docs/contracts/event-model.md`. The two existing Qt event buses are being **replaced**,
   not merged by renaming.
8. Do not create a second state source of truth.
9. Do not treat `NOT_FOUND` as `CLEAN` anywhere in TI verdict handling — this distinction is
   the core of the threat-intel architecture (master plan §5.2,
   `docs/phase4/PHASE4C_THREAT_INTEL_ARCHITECTURE.md`).
10. Do not store API keys in plaintext in production. (Current dev-era plaintext-on-disk
    storage in `app/settings/repository.py` is a known, documented gap — see
    `docs/security/secret-management-model.md` — not a target-state exception.)
11. Do not give Tauri unrestricted `shell:*` capability.
12. Do not give Tauri unrestricted `fs:*` capability.
13. Do not bind the backend sidecar to `0.0.0.0`. Loopback (`127.0.0.1`) only.
14. Do not skip database migrations once the migration runner exists (master plan §17, §26
    row 4B/4D). Note: as of this snapshot no migration/versioning table exists yet in
    `app/database/connection.py` — introducing it is planned work, not yet done.
15. Do not prematurely implement YARA/Sigma/sandbox integration (master plan §19, §30.F).
16. Do not implement a second TI provider before the `ThreatIntelProvider` abstraction is
    actually implemented in source and stable (master plan §30.F). The abstraction **is**
    implemented in source as of this snapshot (`app/threat_intel/provider.py`,
    `app/threat_intel/virustotal_provider.py`; `ThreatIntelService` migrated onto it) — see
    `docs/phase4/PHASE4C_FREEZE.md` and `PROJECT_CONSTITUTION.md` §4. The rule itself is
    unchanged: still no second provider until this one is confirmed stable across a full
    phase without regressions.
17. Do not retire PySide6 before the React frontend reaches feature parity (Phase 4O, not
    earlier — ADR-009).
18. Do not redesign the frontend into a generic dashboard — preserve the SOC-analyst,
    investigation-centric information architecture (master plan §12–§13,
    `docs/architecture/13-frontend-information-architecture.md`).
19. Do not add unnecessary scrolling to solve layout problems — target 1440×900 without
    page-level scroll (master plan §12).
20. Do not add unnecessary animation. Motion communicates state change, not decoration
    (`docs/architecture/12-motion-animation-architecture.md`).
21. Do not silently change report output content during the HTML exporter refactor —
    template-driven internals, same output (master plan §18, §27).
22. Do not weaken existing tests to make migration easier. Every phase must leave the
    previous test baseline green.
23. Do not introduce duplicate sources of truth for any concern.
24. Do not make architectural decisions merely for convenience or to save time under
    deadline pressure — see master plan §30.H and the security risk list (§7 of Final
    Summary Outputs) for concrete examples of what this has caused elsewhere (over-scoped
    Tauri capabilities, sidecar bound to `0.0.0.0`, etc.).
25. If uncertain, STOP and document the uncertainty instead of guessing. Use the
    CONFIRMED / PROPOSED / LIKELY / UNKNOWN / DEPRECATED classification already established
    by this project's own documentation practice.
26. Do not perform unapproved source migration during a documentation-only task. Phase 4B
    set the precedent: zero files under `app/` or `tests/` were touched during a phase whose
    scope was documentation — only `docs/` changed.
27. Do not claim a test suite result you did not actually run in this session. If you cannot
    run part of the suite (e.g., missing `PySide6` in a sandbox), say so explicitly rather
    than repeating an old passing number as if newly confirmed.
