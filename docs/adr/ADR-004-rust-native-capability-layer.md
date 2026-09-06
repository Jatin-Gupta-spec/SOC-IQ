# ADR-004: Rust Owns Native Capabilities Only, Never Domain Logic

**Status:** Proposed
**Related:** Master Plan §28, §8, baseline problems #14, #17.

## Context

Tauri's native layer is implemented in Rust. Rust has legitimate future value for
security-native functionality (e.g. YARA scanning, file hashing) that benefits from a
memory-safe, high-performance native language (Master Plan baseline problem #17). There is a
risk that, once Rust is in the stack, it accretes responsibilities beyond what's justified.

## Problem

Without an explicit boundary, Rust could become a second, informally-scoped backend —
duplicating logic that already exists in Python, or accumulating "while we're in here"
features that were never justified by evidence (mirroring baseline problem #14's caution
about unjustified Rust rewrites of Python logic).

## Decision

Rust's responsibilities are explicitly scoped and timed (Master Plan §8):

| Responsibility | Timing |
|---|---|
| Tauri shell, window lifecycle, packaging | NOW |
| Python sidecar process supervision | NOW |
| Capability-scoped native filesystem ops | NOW |
| OS notifications | NOW |
| OS credential-store read/write | NOW |
| File hashing | LATER |
| YARA scanning | LATER |
| PE metadata/malware artifact inspection | OPTIONAL / Research |
| Risk scoring, TI orchestration, investigation logic | **NEVER** |

## Alternatives Considered

- **Let Rust grow responsibilities organically during implementation, without a fixed list.**
  Rejected — this is exactly the failure mode Master Plan §30.H warns against ("do not let
  Rust or TypeScript implement scoring, TI orchestration, or persistence") and the top
  architectural risk #10 in the Master Plan's final risk list ("scope creep: Rust/YARA work
  starting before the MVP native-capability layer is solid").

## Rejected Alternatives (explicit)

Using Rust for a full second backend behind Tauri (bypassing Python entirely for some
features) — rejected; contradicts ADR-001.

## Consequences

- Positive: Rust's inclusion in the technology stack is defensible under interview
  questioning specifically because its scope is narrow and evidence-based, not padded
  (Master Plan §29, recruiter-impact table).
- Negative: some capabilities that *could* be done faster in Rust (e.g. IOC regex matching)
  stay in Python unless a measured need is demonstrated — an intentional, revisitable
  tradeoff.

## Security Implications

Because Rust never touches domain data beyond what's needed for its native-capability duties
(e.g. a file path for a save dialog), a compromised or buggy Rust command handler has a much
smaller blast radius than it would if it also held business logic.

## Migration Implications

Any future request to add a new Rust responsibility should be checked against this table
first; anything not listed as NOW/LATER/OPTIONAL requires a new or amended ADR, not an
ad-hoc addition during implementation.
