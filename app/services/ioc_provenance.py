"""
IOC-level provenance domain model (A4-P2.1).

Phase A4-P1 (docs/architecture/PROVENANCE.md) established
*investigation*-level evidence provenance: aggregate OBSERVED /
ENRICHED / DERIVED / UNAVAILABLE counts for a whole investigation
(`app.services.evidence_provenance.build_evidence_provenance_summary`).

A4-P2.1 goes one level deeper and answers, per individual IOC value:

    Where did THIS indicator come from, and how was it produced?

This module defines that domain vocabulary only -- no SQLite table, no
repository, no API/DTO surface, and no UI wiring. It is deliberately
plain Python with no Qt/DB/network dependency of any kind (mirrors the
existing `app.services.evidence_provenance` /
`app.services.investigation_integrity` pattern), so it can be reused
unchanged by persistence (A4-P2.2), the API layer (A4-P2.3), and the
UI (A4-P2.4) without being coupled to any one of them.

Deliberately does NOT introduce a second IOC data model. The one
authoritative IOC container in this codebase remains
`Investigation.iocs` (`dict[ioc_type, list[value]]`), populated by
`app.extractor.extract_iocs`. An `IOCProvenance` record *explains* an
existing IOC value -- it does not replace, duplicate, or compete with
that storage.

## What this codebase's architecture actually supports

`app.extractor.extract_iocs` is this codebase's only extraction path:
a single regex pass per IOC type
(`app.extractor.COMPILED_PATTERNS`), over the exact decoded text of
one source report, with no intermediate transformation step. That
constrains this domain model's honest scope:

* Every value the extractor produces was, by construction, literally
  present in the source report -- OBSERVED, not DERIVED (see
  `ObservationState`).
* The extractor records no match position (no line/column/offset/
  page). `SourceReference` does not invent one -- see its docstring
  and docs/architecture/PROVENANCE.md's "IOC provenance" section,
  which already documents this as a deliberate, not accidental, gap.
* `ioc_type` (`app.extractor.IOC_PATTERNS`'s existing keys) already
  identifies which single regex produced a given value, so
  `ExtractionMethod` reuses that vocabulary instead of inventing a
  second, parallel extractor-identity taxonomy.
* Threat-intelligence enrichment (VirusTotal) is a separate ENRICHED
  tier, not an IOC's provenance -- this module never treats a TI
  provider as the source of an IOC that was actually extracted from a
  report. See `app.services.evidence_provenance` for that tier.
* This module also does not implement analyst/system audit logging
  ("what did the application/user do") or make any chain-of-custody /
  legal-admissibility / tamper-proof claim. It only records what
  `app.extractor.extract_iocs` did with a given input, exactly as
  narrowly as docs/architecture/PROVENANCE.md's existing scope note
  already commits to.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.database.models import Investigation
from app.exceptions import ValidationError
from app.extractor import IOC_PATTERNS


# ==========================================================
# Observation State
# ==========================================================


class ObservationState(str, Enum):
    """
    How SOC-IQ came to know a given IOC value.

    OBSERVED:
        The value was directly present in the analyzed source
        report's decoded text. This codebase's only extraction path
        (`app.extractor.extract_iocs`) never transforms, computes, or
        infers a value -- it only locates and deduplicates ones that
        were already there. Every IOC currently produced by this
        codebase is OBSERVED.

    DERIVED:
        SOC-IQ generated the value itself, via a documented
        transformation (e.g. a future defanged-indicator refanger, or
        a decoded/decompressed payload scan). No such transformation
        exists anywhere in this codebase today, so
        `build_ioc_provenance()` below never produces a DERIVED
        record. The member exists so this vocabulary does not need to
        be re-invented the day a real derivation path is added --
        matching the OBSERVED/DERIVED distinction
        docs/architecture/PROVENANCE.md already defines at the
        investigation level.
    """

    OBSERVED = "OBSERVED"
    DERIVED = "DERIVED"


# ==========================================================
# Source Reference
# ==========================================================


@dataclass(frozen=True, slots=True)
class SourceReference:
    """
    Identifies the report an IOC observation came from.

    report_name:
        The same identity `Investigation.report_name` /
        `InvestigationRepository.exists_by_report_name` already use
        -- not a new identifier space.

    source_sha256:
        The A4-P1 integrity hash (`Investigation.source_sha256`) when
        available. `None` means one specific, honest thing: a legacy
        investigation persisted before A4-P1, so the hash was never
        calculated (see docs/architecture/PROVENANCE.md) -- never a
        fabricated or backfilled digest.

    No line/column/offset/page field is defined here. This codebase's
    single regex-based extractor never records match position, so a
    `SourceReference` represents "source = this report" without
    pretending to know where in it -- per A4-P2.1's "do not fabricate
    precision" requirement.
    """

    report_name: str
    source_sha256: str | None = None

    def __post_init__(self) -> None:

        if not self.report_name or not self.report_name.strip():

            raise ValidationError(
                "SourceReference.report_name cannot be empty."
            )


# ==========================================================
# Extraction Method
# ==========================================================


@dataclass(frozen=True, slots=True)
class ExtractionMethod:
    """
    Identifies how an IOC value was produced.

    Reuses `app.extractor.IOC_PATTERNS`'s existing type vocabulary
    (`ioc_type`) as the authoritative extractor identity, rather than
    inventing a second, parallel extractor-name taxonomy. This
    codebase has exactly one extractor per IOC type -- a single
    precompiled regex in `app.extractor.COMPILED_PATTERNS` -- so
    `ioc_type` alone already identifies, unambiguously, which pattern
    produced a given value.
    """

    ioc_type: str

    def __post_init__(self) -> None:

        if self.ioc_type not in IOC_PATTERNS:

            raise ValidationError(
                "ExtractionMethod.ioc_type must be one of "
                f"{sorted(IOC_PATTERNS)!r}, got {self.ioc_type!r}."
            )

    @property
    def description(self) -> str:
        """
        Short, human-readable label for this extraction method, e.g.
        "regex:ipv4". Always derived from `ioc_type`, never stored or
        set independently of it.
        """

        return f"regex:{self.ioc_type}"


# ==========================================================
# IOC Provenance
# ==========================================================


@dataclass(frozen=True, slots=True)
class IOCProvenance:
    """
    A single, immutable historical fact: "this IOC value was, in this
    observation state, produced from this source via this extraction
    method."

    Deliberately does not compete with `Investigation.iocs` (the one
    authoritative IOC container in this codebase) -- a record here
    explains an existing IOC value, it does not replace or duplicate
    its storage.

    Immutability: a frozen dataclass with no setters or mutation
    methods. Representing a historical fact ("report X contained
    value Y, extracted by method Z") as an immutable value type keeps
    it from silently changing later -- e.g. if `ExtractionMethod`'s
    underlying regex is refactored, already-built `IOCProvenance`
    records for prior analyses are unaffected. Database-level
    immutability (append-only storage, etc.) is out of scope for
    A4-P2.1; this is domain-level immutability only.

    A single IOC value can legitimately have more than one
    `IOCProvenance` record -- e.g. the same value observed in two
    different reports produces two records, one per
    `SourceReference`. Nothing in this model assumes "one IOC = one
    source forever."
    """

    ioc_value: str
    source: SourceReference
    extraction: ExtractionMethod
    state: ObservationState = ObservationState.OBSERVED

    def __post_init__(self) -> None:

        if not self.ioc_value or not self.ioc_value.strip():

            raise ValidationError(
                "IOCProvenance.ioc_value cannot be empty."
            )

    @property
    def ioc_type(self) -> str:
        """
        Convenience accessor -- always equal to
        `self.extraction.ioc_type`, never stored separately (so the
        two can never disagree).
        """

        return self.extraction.ioc_type

    def to_dict(self) -> dict[str, Any]:
        """
        Plain-dict representation for logging/debugging and for a
        future DTO layer (A4-P2.3) to build on. Not itself an API
        contract.
        """

        return {
            "ioc_value": self.ioc_value,
            "ioc_type": self.ioc_type,
            "state": self.state.value,
            "source": {
                "report_name": self.source.report_name,
                "source_sha256": self.source.source_sha256,
            },
            "extraction": {
                "ioc_type": self.extraction.ioc_type,
                "method": self.extraction.description,
            },
        }


# ==========================================================
# Factory
# ==========================================================


def build_ioc_provenance(
    investigation: Investigation,
) -> list[IOCProvenance]:
    """
    Derive the full list of `IOCProvenance` records for an
    already-loaded `Investigation`.

    Pure function: no database access, no filesystem access, no
    network call, no mutation of `investigation` -- mirrors
    `build_evidence_provenance_summary` /
    `build_integrity_summary`'s existing pattern for this codebase's
    plain-Python domain services.

    One record per (ioc_type, value) pair present in
    `investigation.iocs`, every one OBSERVED -- this codebase's
    single-extractor architecture (see module docstring) never
    produces a DERIVED value today.

    An `ioc_type` key in `investigation.iocs` that is not one of
    `app.extractor.IOC_PATTERNS`'s known types is skipped rather than
    raised: `investigation.iocs` is `dict[str, list[str]]` with no
    schema enforcement, so a legacy or defensively malformed record
    could in principle contain an unrecognized key. Deriving
    provenance for an already-persisted investigation must not itself
    become a new failure mode; empty/blank values are skipped for the
    same reason.
    """

    source = SourceReference(
        report_name=investigation.report_name,
        source_sha256=investigation.source_sha256,
    )

    iocs = investigation.iocs or {}

    records: list[IOCProvenance] = []

    for ioc_type, values in iocs.items():

        if ioc_type not in IOC_PATTERNS:
            continue

        extraction = ExtractionMethod(ioc_type=ioc_type)

        for value in values:

            if not value or not value.strip():
                continue

            records.append(
                IOCProvenance(
                    ioc_value=value,
                    source=source,
                    extraction=extraction,
                    state=ObservationState.OBSERVED,
                )
            )

    return records
