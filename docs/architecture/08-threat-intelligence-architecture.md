# Threat Intelligence Architecture

**Status:** Documentation Foundation (Phase 4A). Priority subsystem per Master Plan.
**Related:** Master Plan §5 (full design), §1.5 (current-state defect), ADR-007.

**Phase 4C update:** the CURRENT STATE section below describes the pre-Phase-4C
implementation and is preserved as a historical record — it is no longer an accurate
description of `app/threat_intel/`. The TARGET STATE section below (the `ThreatIntelProvider`
protocol and `Verdict` model) is now implemented as specified. See
`docs/phase4/PHASE4C_THREAT_INTEL_ARCHITECTURE.md` for the full authoritative design and
`docs/migration/PHASE4C_EXIT_CRITERIA.md` for the implementation/verification record.

## CURRENT STATE (CONFIRMED from source)

`ThreatIntelService.__init__` (`app/threat_intel/service.py`) takes an **optional
`VirusTotalClient`** as its only injectable dependency. There is no `ThreatIntelProvider`
protocol, no provider registry, and no normalized cross-provider verdict type.
`_format_verdict` computes verdict and detection-ratio fields directly from VirusTotal's raw
response shape (`malicious`/`suspicious`/`harmless`/`undetected` counts) — the service is
provider-abstracted in name only; it is effectively VirusTotal-specific (CONFIRMED, matching
baseline problems #6 and #7).

## TARGET STATE (PROPOSED)

**Provider interface:**

```python
class ThreatIntelProvider(Protocol):
    name: str  # "virustotal", "abuseipdb", "otx"
    supported_ioc_types: set[IOCType]

    async def lookup(self, ioc: IOC) -> ProviderResult: ...
    def is_configured(self) -> bool: ...
```

**Canonical verdict model** — the load-bearing design decision of this subsystem:

```python
class Verdict(str, Enum):
    MALICIOUS = "malicious"
    SUSPICIOUS = "suspicious"
    CLEAN = "clean"
    NOT_FOUND = "not_found"        # provider has no record — explicitly NOT "clean"
    UNSUPPORTED = "unsupported"
    NO_API_KEY = "no_api_key"
    UNAVAILABLE = "unavailable"    # timeout / connection error
    RATE_LIMITED = "rate_limited"
    ERROR = "error"
```

**`NOT_FOUND != CLEAN` is enforced by construction**, not by convention: a provider adapter
that finds no record must return `Verdict.NOT_FOUND`; `Verdict.CLEAN` is reserved for a
provider explicitly asserting "checked, zero detections." This distinction is preserved
end-to-end — see `docs/security/threat-model.md` and the semantic-color mapping in
`11-design-system-architecture.md`, where the two verdicts must remain visually distinct, not
just data-distinct.

Aggregation across providers is an explicit, independently-testable policy function (not
inline in any one provider), e.g.: malicious if any provider says malicious; else suspicious
if any says suspicious; else clean only if at least one provider explicitly returned clean;
else not_found/unavailable. Full detail: Master Plan §5.3.

`virustotal.py`'s existing HTTP/parsing logic is **preserved almost entirely** — it becomes
the body of `VirusTotalProvider.lookup()`, translating VT's raw response into a
`ProviderResult`. Nothing about VT's actual API interaction is rewritten; only its output
shape changes to conform to the new interface.

## MIGRATION NOTES

Phase 4C (Master Plan §26) builds the provider protocol + VT adapter + verdict model with VT
still working end-to-end through the new interface, plus new unit tests for the aggregation
policy. A second provider (AbuseIPDB or OTX) is explicitly **not** built until the
abstraction is proven with one provider first (Master Plan §30.F, "do not add a second TI
provider before the abstraction exists").

## UNKNOWN / REQUIRES VERIFICATION

None outstanding for this subsystem specifically — the current-state facts above were
confirmed by direct source read during the Phase 4A audit.
