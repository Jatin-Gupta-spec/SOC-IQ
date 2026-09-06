# Frontend/Backend Responsibility Boundaries

**Status:** Documentation Foundation (Phase 4A).
**Related:** Master Plan §2 (diagram), §3, ADR-001, ADR-002,
`docs/architecture/03-frontend-architecture.md`,
`docs/architecture/02-python-backend-architecture.md`.

## CURRENT STATE

Today, there is effectively one responsibility domain — PySide6 controllers/services call
domain logic in-process (CONFIRMED, Master Plan §1.1). The boundary this document describes
does not exist yet; it is the target-state answer to "once a real process boundary exists,
who is allowed to do what."

## TARGET STATE (PROPOSED)

| Responsibility | Owner | Explicitly NOT owned by |
|---|---|---|
| UI rendering, view models, motion | React | Python, Rust |
| Client-side session/UI state | React | Python (Python holds no per-session UI state) |
| Risk scoring | Python | React, Rust |
| Threat-intelligence orchestration | Python | React, Rust |
| Persistence (SQLite) | Python | React (no direct access), Rust |
| Native filesystem writes | Rust (via Tauri capability) | React (no direct access) |
| Native OS integration (notifications, credential store) | Rust | Python, React |
| Desktop shell / packaging | Rust/Tauri | Python, React |
| Reporting (report generation) | Python | React, Rust |
| Correlation | Python | React, Rust |

This table is the responsibility-boundary counterpart to the trust-boundary table in
`docs/security/trust-boundary-model.md` — this document is about *what each layer is
supposed to do*; that one is about *what each layer is trusted to do if compromised*. The two
are related but distinct: a layer can be trusted with a capability it still shouldn't use
outside its assigned responsibility.

## MIGRATION NOTES

This boundary is what makes ADR-001 ("Python remains the domain core") and ADR-002
("React owns presentation only") enforceable in code, not just in principle — every command
handler and every React feature module is reviewed against this table during implementation.

## UNKNOWN / REQUIRES VERIFICATION

None outstanding — this table is derived directly from Master Plan §2's diagram and §3's
ownership model, already-approved decisions, not new proposals.
