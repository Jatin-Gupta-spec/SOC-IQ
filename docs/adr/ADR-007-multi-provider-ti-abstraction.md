# ADR-007: Multi-Provider Threat-Intelligence Abstraction

**Status:** Proposed
**Related:** Master Plan §28, §5, §1.5, and `docs/architecture/08-threat-intelligence-architecture.md`.

## Context

`ThreatIntelService` currently takes an optional `VirusTotalClient` as its only injectable
dependency, with no `ThreatIntelProvider` protocol and no normalized cross-provider verdict
type (CONFIRMED). Verdict computation is derived directly from VirusTotal's specific response
shape. The target architecture calls for supporting additional providers (AbuseIPDB, OTX)
without rewriting the application (Master Plan baseline problems #6, #7).

## Problem

Adding a second provider to the current architecture would require writing
provider-shape-specific logic inside or beside `ThreatIntelService`, and there is currently no
way to distinguish "provider has no record for this IOC" from "provider checked and found it
clean" — a materially different, and currently unrepresented, distinction for a SOC analyst.

## Decision

Introduce a `ThreatIntelProvider` protocol and a canonical, provider-neutral `Verdict` enum
that explicitly separates `NOT_FOUND` from `CLEAN` (full model:
`docs/architecture/08-threat-intelligence-architecture.md`). `ThreatIntelService` is
refactored into an orchestrator holding `list[ThreatIntelProvider]` instead of one concrete
client. VirusTotal's existing HTTP/parsing logic is preserved as the implementation of a
`VirusTotalProvider` adapter conforming to the new protocol.

## Alternatives Considered

- **Add a second provider directly, without first building the abstraction.** Rejected —
  explicitly called out in Master Plan §30.F ("do not add a second TI provider before the
  abstraction exists") and in the migration plan's phase ordering (Phase 4C builds the
  abstraction with VirusTotal as the only provider; a second provider is future work).
- **A looser "verdict string" model instead of an explicit enum.** Rejected — a free-form
  string would allow `"not_found"` and `"clean"` to be conflated by accident in a way an enum
  with distinct members structurally prevents.

## Rejected Alternatives (explicit)

Treating VirusTotal's specific response shape as the de facto standard other providers must
conform to at the wire level — rejected; the whole point of the canonical `Verdict` model is
that each provider adapter normalizes its own shape into the shared model, not the reverse.

## Consequences

- Positive: a second provider becomes an additive change (a new adapter implementing the
  protocol), not a modification to shared orchestration logic.
- Negative: requires an aggregation policy (Master Plan §5.3) for when multiple providers
  disagree on a verdict — this policy is new complexity that doesn't exist today with a
  single provider, and must be independently unit-tested.

## Security Implications

The explicit `NOT_FOUND != CLEAN` distinction is itself a security-relevant decision: without
it, a SOC analyst could mistake "we don't have data on this IOC" for "this IOC was checked
and is safe" — a false sense of assurance. This invariant is referenced from
`docs/security/threat-model.md` for that reason, not only as a data-modeling concern.

## Migration Implications

Phase 4C (Master Plan §26) delivers this abstraction with VirusTotal as the sole working
provider; exit criterion: "VT still works end-to-end via new interface; new unit tests for
verdict policy."
