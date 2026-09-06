"""
Request/response DTOs, per docs/contracts/dto-boundaries.md.

Written as frozen dataclasses with __post_init__ validation rather than
pydantic.BaseModel -- see docs/phase4/PHASE4D_API_EVENT_ARCHITECTURE.md S6
for why (pydantic is not installed and this sandbox has no network access
to install it). Field names/types are a 1:1, mechanical match for the
eventual pydantic models: swapping the base class later should not require
renaming or retyping any field.

Domain objects (app.database.models.Investigation) never cross the command
boundary directly -- every response DTO here is built by an explicit
mapping function, not by passing a domain object straight through.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from app.application.errors import INVALID_COMMAND_PAYLOAD
from app.database.models import Investigation
from app.services.correlation_models import CorrelationResult
from app.services.ioc_provenance import IOCProvenance
from app.services.risk_explanation_models import (
    IocCategoryContribution,
    RiskExplanation,
)
from app.timeline.domain import TimelineEvent


class CommandValidationError(Exception):
    """Raised by a request DTO's __post_init__ when validation fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.code = INVALID_COMMAND_PAYLOAD
        self.message = message


# ---------------------------------------------------------------------------
# Request DTOs
# ---------------------------------------------------------------------------


#: The three logical analysis-pipeline stages, per
#: docs/architecture/15-analysis-pipeline-architecture.md and the three
#: `app/gui/pages/analyze_page.py` checkboxes it documents as currently
#: UI-only (`self._chk_iocs` / `self._chk_vt` / `self._chk_risk`, all
#: `setChecked(True)` by default). This tuple is also the allow-list used
#: to reject unknown option keys -- see `AnalysisOptions.from_payload`.
ANALYSIS_OPTION_FIELDS = ("extract_iocs", "enrich_ti", "score_risk")


@dataclass(frozen=True)
class AnalysisOptions:
    """
    Per docs/contracts/command-model.md's `analyze_report` example payload
    (`"options": {"extract_iocs": true, "enrich_ti": true, "score_risk": true}`)
    and docs/architecture/15-analysis-pipeline-architecture.md's target
    state ("the three checkboxes become three boolean fields on the
    analyze_report command payload").

    Defaults are all `True` -- matching the three `analyze_page.py`
    checkboxes' own confirmed default (`setChecked(True)` for all three,
    app/gui/pages/analyze_page.py lines ~132-134) -- so a caller that sends
    no `options` at all gets the exact same full pipeline that ran before
    this field existed. Backend enforcement of these flags (skipping a
    stage when its flag is `False`) is PART 2B work; this part only
    establishes the validated, typed contract that carries them.
    """

    extract_iocs: bool = True
    enrich_ti: bool = True
    score_risk: bool = True

    def __post_init__(self) -> None:
        for field_name in ANALYSIS_OPTION_FIELDS:
            value = getattr(self, field_name)
            if not isinstance(value, bool):
                raise CommandValidationError(
                    f"options.{field_name} must be a boolean."
                )

    @classmethod
    def from_payload(cls, payload: Any) -> "AnalysisOptions":
        """
        Normalize a raw `options` value (as it arrives over JSON: `None`,
        absent, or a plain `dict`) into a validated `AnalysisOptions`.

        Already-constructed `AnalysisOptions` instances pass through
        unchanged, so callers inside Python (tests, other handlers) can
        build one directly instead of round-tripping through a dict.
        """

        if payload is None:
            return cls()
        if isinstance(payload, AnalysisOptions):
            return payload
        if not isinstance(payload, dict):
            raise CommandValidationError(
                "options must be an object with boolean "
                f"{ANALYSIS_OPTION_FIELDS} fields."
            )

        unknown = set(payload) - set(ANALYSIS_OPTION_FIELDS)
        if unknown:
            raise CommandValidationError(
                f"Unknown option(s): {sorted(unknown)}. "
                f"Valid options are {ANALYSIS_OPTION_FIELDS}."
            )

        try:
            return cls(**payload)
        except TypeError as error:
            # Only reachable for a duplicate/malformed dict shape that
            # __post_init__'s per-field type check wouldn't otherwise
            # catch (dataclass __init__ itself rejects it first).
            raise CommandValidationError(str(error)) from error

    def to_dict(self) -> dict[str, bool]:
        return {name: getattr(self, name) for name in ANALYSIS_OPTION_FIELDS}


@dataclass(frozen=True)
class AnalyzeReportRequest:
    """
    Per docs/contracts/command-model.md `analyze_report`: carries the
    report to analyze plus the pipeline-option gating described in
    docs/architecture/15-analysis-pipeline-architecture.md.

    `options` accepts `None`/absent (-> all-True defaults, see
    `AnalysisOptions`), a raw `dict` (as it arrives over JSON from the
    frontend/API boundary), or an already-constructed `AnalysisOptions`.
    Whatever is passed in is normalized to a real `AnalysisOptions`
    instance in `__post_init__`, so every downstream reader
    (`AnalyzeReportCommandHandler` included) can rely on
    `request.options` always being that type -- never a bare dict.
    """

    report_path: str
    options: AnalysisOptions | dict[str, Any] | None = field(
        default_factory=AnalysisOptions
    )

    def __post_init__(self) -> None:
        if not isinstance(self.report_path, str) or not self.report_path.strip():
            raise CommandValidationError(
                "report_path must be a non-empty string."
            )
        if not isinstance(self.options, AnalysisOptions):
            # frozen dataclass: __setattr__ is blocked outside __init__,
            # so normalization uses object.__setattr__ deliberately here
            # -- this is the one sanctioned exception the whole file's
            # frozen-dataclass pattern relies on (mirrors no other DTO
            # needing it, since no other DTO has a nested object field).
            object.__setattr__(self, "options", AnalysisOptions.from_payload(self.options))


@dataclass(frozen=True)
class GetInvestigationRequest:
    investigation_id: int

    def __post_init__(self) -> None:
        if not isinstance(self.investigation_id, int) or isinstance(
            self.investigation_id, bool
        ):
            raise CommandValidationError("investigation_id must be an integer.")
        if self.investigation_id <= 0:
            raise CommandValidationError("investigation_id must be positive.")


@dataclass(frozen=True)
class ListInvestigationsRequest:
    """No parameters today. Kept as an explicit type (rather than `None`)
    so a future `limit`/`offset`/`severity` filter is an additive field,
    not a payload-shape change."""


@dataclass(frozen=True)
class GetDashboardSummaryRequest:
    """Per Phase 4H Part 1 (docs/phase4/PHASE4H_PART1_BACKEND_API_CONTRACT.md).

    No parameters today -- the Dashboard needs one aggregate snapshot,
    not a filtered/paginated query. Kept as an explicit type (rather
    than `None`), mirroring `ListInvestigationsRequest`'s own reasoning,
    so a future `recent_limit`-style parameter is an additive field,
    not a payload-shape change.
    """


@dataclass(frozen=True)
class GetInvestigationAggregateSummaryRequest:
    """Per PD-04 (docs/phase4/PD04_CROSS_INVESTIGATION_AGGREGATE_COMMANDS.md):
    cross-investigation aggregate backend commands.

    No parameters today -- like `GetDashboardSummaryRequest`, this is
    one aggregate snapshot across every stored investigation, not a
    filtered/paginated query. Kept as an explicit type (rather than
    `None`) for the same reason `GetDashboardSummaryRequest` and
    `ListInvestigationsRequest` are: a future filter (e.g. a date
    range) is then an additive field, not a payload-shape change.
    PD-04's own scope note is deliberate about not inventing a
    filtering system ahead of an actual product requirement for one.
    """


@dataclass(frozen=True)
class SearchInvestigationsRequest:
    """Per docs/contracts/command-model.md `search_investigations` and the
    source-verified query behind it: `InvestigationService.find_by_report_name`
    (docs/contracts/PHASE4B_QUERY_INVENTORY.md "Find by report name"),
    fronted in the current GUI by
    `app.gui.controllers.HistoryController.search_by_report_name`.

    `report_name` may be blank -- unlike `GetInvestigationRequest` /
    `DeleteInvestigationRequest`, blank is not rejected here. It is a
    legitimate "no search term" input, not a malformed one; the command
    handler mirrors `HistoryController.search_by_report_name`'s own
    short-circuit (blank -> `[]`, no repository call) rather than this DTO
    treating it as a validation failure.
    """

    report_name: str

    def __post_init__(self) -> None:
        if not isinstance(self.report_name, str):
            raise CommandValidationError("report_name must be a string.")


@dataclass(frozen=True)
class GetIocsRequest:
    """Per docs/contracts/command-model.md `get_iocs` ("Fetch IOCs for an
    investigation") and `InvestigationSummaryDTO`'s own docstring, which
    deliberately omits `iocs` from the summary shape precisely so this
    command can own it.

    Validation mirrors GetInvestigationRequest deliberately -- both
    commands take the same investigation_id shape and the same
    positive-int constraint used to look up the same Investigation row,
    and there is no reason for the two validation rules to drift.
    """

    investigation_id: int

    def __post_init__(self) -> None:
        if not isinstance(self.investigation_id, int) or isinstance(
            self.investigation_id, bool
        ):
            raise CommandValidationError("investigation_id must be an integer.")
        if self.investigation_id <= 0:
            raise CommandValidationError("investigation_id must be positive.")


@dataclass(frozen=True)
class GetInvestigationIntegrityRequest:
    """Per docs/architecture/PROVENANCE.md's "Investigation Integrity
    Summary" and A4-P1's evidence-provenance model.

    Validation mirrors `GetIocsRequest`/`GetThreatIntelligenceRequest`
    deliberately -- all three commands take the same
    `investigation_id` shape and the same positive-int constraint used
    to look up the same `Investigation` row.

    Kept as its own command (rather than added fields on
    `InvestigationSummaryDTO`) for the same reason `get_iocs` and
    `get_threat_intelligence` are their own commands: so computing it
    is never unavoidable overhead on `list_investigations` /
    `search_investigations` / the Dashboard's `recent_investigations`,
    which all reuse `InvestigationSummaryDTO` unchanged.
    """

    investigation_id: int

    def __post_init__(self) -> None:
        if not isinstance(self.investigation_id, int) or isinstance(
            self.investigation_id, bool
        ):
            raise CommandValidationError("investigation_id must be an integer.")
        if self.investigation_id <= 0:
            raise CommandValidationError("investigation_id must be positive.")


@dataclass(frozen=True)
class GetInvestigationProvenanceRequest:
    """Per A4-P2 Part 2 (docs/architecture/PROVENANCE.md): the per-IOC
    provenance read model built on top of A4-P2.1's
    `app.services.ioc_provenance` domain model.

    Kept as its own command, exactly like `get_investigation_integrity`
    (whose docstring gives the same reasoning): computing per-IOC
    provenance is never unavoidable overhead on `list_investigations` /
    `search_investigations` / the Dashboard's `recent_investigations`,
    and it stays a separate concern from the aggregate integrity/
    evidence-tier counts `get_investigation_integrity` already answers
    -- this command answers "where did each IOC come from", not "was
    the pipeline run for this investigation".

    Validation mirrors `GetInvestigationIntegrityRequest`/`GetIocsRequest`
    deliberately -- all three commands take the same `investigation_id`
    shape and the same positive-int constraint used to look up the same
    `Investigation` row.
    """

    investigation_id: int

    def __post_init__(self) -> None:
        if not isinstance(self.investigation_id, int) or isinstance(
            self.investigation_id, bool
        ):
            raise CommandValidationError("investigation_id must be an integer.")
        if self.investigation_id <= 0:
            raise CommandValidationError("investigation_id must be positive.")


@dataclass(frozen=True)
class GetInvestigationRiskExplanationRequest:
    """Per PD-08-P1 (docs/phase4/PD08_P1_RISK_EXPLANATION_BACKEND.md):
    the modern read contract for the KEEP "Why this risk?" behavior
    PD-08 confirmed, built on the existing
    `app.services.risk_explanation_service.RiskExplanationService`
    (PHASE3C-1).

    Kept as its own command, exactly like `get_investigation_integrity`
    and `get_investigation_provenance` (whose docstrings give the same
    reasoning): computing a risk explanation is never unavoidable
    overhead on `list_investigations` / `search_investigations` / the
    Dashboard's `recent_investigations`, all of which reuse
    `InvestigationSummaryDTO` unchanged and already expose
    score/severity/confidence on their own.

    Validation mirrors `GetInvestigationProvenanceRequest`/
    `GetInvestigationIntegrityRequest` deliberately -- all three
    commands take the same `investigation_id` shape and the same
    positive-int constraint used to look up the same `Investigation`
    row.
    """

    investigation_id: int

    def __post_init__(self) -> None:
        if not isinstance(self.investigation_id, int) or isinstance(
            self.investigation_id, bool
        ):
            raise CommandValidationError("investigation_id must be an integer.")
        if self.investigation_id <= 0:
            raise CommandValidationError("investigation_id must be positive.")


@dataclass(frozen=True)
class GetTimelineRequest:
    """A4-P2-P3 Part 3: `get_timeline` -- exposes
    `app.timeline.repository.TimelineRepository.list_for_investigation`
    through the application/API boundary.

    Validation mirrors `GetIocsRequest`/`GetInvestigationProvenanceRequest`
    deliberately -- all of these commands take the same
    `investigation_id` shape and the same positive-int constraint used
    to look up (or scope a query to) the same `Investigation` row.
    There is no reason for this command's identity validation to drift
    from every other `investigation_id`-keyed command already in this
    file.
    """

    investigation_id: int

    def __post_init__(self) -> None:
        if not isinstance(self.investigation_id, int) or isinstance(
            self.investigation_id, bool
        ):
            raise CommandValidationError("investigation_id must be an integer.")
        if self.investigation_id <= 0:
            raise CommandValidationError("investigation_id must be positive.")


@dataclass(frozen=True)
class GetThreatIntelligenceRequest:
    """Per docs/contracts/command-model.md `get_threat_intelligence`
    ("Fetch TI results for an investigation/IOC") and
    `InvestigationSummaryDTO`'s own docstring, which deliberately
    omits `threat_intelligence` from the summary shape precisely so
    this command can own it -- the exact same reservation that
    docstring already made for `get_iocs` and `iocs`.

    The richer, GUI-computed message/short_label overview
    (`app.services.ioc_detail_context.build_investigation_threat_intel_overview`)
    is NOT what this command exposes: wrapping it would mean
    importing `app.gui` into `app.application`, an architectural
    coupling this file already deliberately avoids elsewhere (see
    `SearchInvestigationsCommandHandler`'s docstring: "app.application
    never depends on app.gui"). Instead this mirrors `GetIocsRequest`:
    the raw `Investigation.threat_intelligence` field -- the same
    nested dict `ThreatIntelService.enrich_results()` already produced
    and `analyze_report` already persisted -- is exposed unchanged,
    with no interpretation layer invented on top.

    Phase 4J-2 adds one additive field alongside that raw payload:
    `states`, a `{ioc_type: {value: TI_STATE_*}}` projection built by
    `app.services.threat_intel_state.build_investigation_indicator_states`
    (the framework-independent module Phase 4J-1 introduced precisely
    so this command could reuse the same TI_STATE_* classification the
    GUI's IOC detail dialog uses, without importing `app.gui`). This is
    a classification of the existing raw payload, not a second source
    of truth -- the raw `threat_intelligence` field is unchanged and
    still present for existing consumers.

    Phase 4K-1 additionally adds `typed_verdicts`, a per-indicator
    typed `Verdict` classification (`"clean"` / `"not_found"` /
    `"malicious"` / `"suspicious"`, or `None` where the persisted raw
    data is insufficient to classify honestly) derived from the same
    already-persisted `threat_intelligence` payload -- see
    `app.threat_intel.verdict_from_persisted.build_investigation_typed_verdicts`.
    No provider is called and the legacy `verdict` display string is
    never parsed to produce it.

    Response shape:
        {
            "investigation_id": <int>,
            "threat_intelligence": <existing raw payload, unchanged>,
            "states": {
                "<ioc_type>": {"<value>": "<TI_STATE_*>", ...},
                ...
            },
            "typed_verdicts": {
                "<ioc_type>": {"<value>": "<Verdict.value>" | None, ...},
                ...
            },
        }

    Validation mirrors GetInvestigationRequest/GetIocsRequest
    deliberately -- all three commands take the same investigation_id
    shape and the same positive-int constraint used to look up the
    same Investigation row.
    """

    investigation_id: int

    def __post_init__(self) -> None:
        if not isinstance(self.investigation_id, int) or isinstance(
            self.investigation_id, bool
        ):
            raise CommandValidationError("investigation_id must be an integer.")
        if self.investigation_id <= 0:
            raise CommandValidationError("investigation_id must be positive.")


@dataclass(frozen=True)
class GetSettingsRequest:
    """Per SOC-IQ Part 2A (Settings backend read contract).

    No parameters today -- the modern frontend needs one snapshot of
    the currently persisted settings, not a filtered/paginated query.
    Kept as an explicit type (rather than `None`), mirroring
    `ListInvestigationsRequest` / `GetDashboardSummaryRequest`'s own
    reasoning, so a future parameter is an additive field, not a
    payload-shape change.
    """


@dataclass(frozen=True)
class SaveSettingsRequest:
    """Per docs/contracts/PHASE4B_COMMAND_INVENTORY.md `save_settings`
    (name "inferred" there, now confirmed by direct read of
    `app/settings/service.py` and the three emit sites in
    `app/gui/pages/settings_page.py`) and
    `app/settings/service.py`'s `SettingsService.update_api_key` /
    `.update_export_directory` / `.update_theme` -- three distinct
    single-field operations, never one combined write.

    Mirrors the confirmed discriminated-payload shape exactly: exactly
    one of `export_directory`, `theme` may be set per call, matching
    every observed `events.settings_changed.emit(...)` call site (each
    emits exactly one key, never more than one). Bundling multiple
    fields into one request is deliberately rejected here rather than
    guessed at, since no existing call site does that and
    `SettingsService` has no single method that would accept it.

    `virustotal_api_key` (MAX19A-F-01) is accepted as a constructor
    argument but always rejected in `__post_init__` -- it is *not* one
    of the two live fields above. Under ADR-008, Rust is the sole owner
    of credential writes (`keystore_set_secret`, direct Tauri IPC,
    never through this HTTP-reachable command); the production
    `SettingsRepository`'s secret store (`RustKeystoreHandoffSecretStore`)
    is read-only and its `set_secret()` is hard-coded to always raise.
    Before this fix, a structurally-valid `save_settings` call with this
    field was fully wired end-to-end (DTO -> handler -> service ->
    repository -> real store call) and reachable over the same
    HTTP endpoint the frontend uses for Theme/Export Directory, yet
    guaranteed to fail every time in production -- reachable dead
    capability, not a gap this DTO should keep leaving open. Rejecting
    it here, at construction, means `SaveSettingsCommandHandler` never
    sees a request with this field set, closing that surface without
    touching `SettingsService.update_api_key` / `SettingsRepository
    .save_api_key` -- the legacy PySide6 GUI (`app/gui/pages
    /settings_page.py`) calls those directly, in-process, never through
    this DTO, so it is unaffected by this change and keeps its existing
    (already-failing, already-user-visible-error) save behavior.
    """

    virustotal_api_key: str | None = None
    export_directory: str | None = None
    theme: str | None = None

    def __post_init__(self) -> None:
        if self.virustotal_api_key is not None:
            raise CommandValidationError(
                "save_settings no longer accepts virustotal_api_key. "
                "Rust is the sole owner of credential writes (ADR-008) -- "
                "use the keystore_set_secret Tauri command instead."
            )

        provided = [
            field_name
            for field_name, value in (
                ("export_directory", self.export_directory),
                ("theme", self.theme),
            )
            if value is not None
        ]

        if len(provided) != 1:
            raise CommandValidationError(
                "save_settings requires exactly one of export_directory, theme."
            )

        field_name = provided[0]
        value = getattr(self, field_name)

        if not isinstance(value, str):
            raise CommandValidationError(f"{field_name} must be a string.")


VALID_EXPORT_FORMATS = ("html", "pdf", "json", "markdown")


@dataclass(frozen=True)
class ExportReportRequest:
    """Per docs/contracts/command-model.md `export_report` ("Trigger a
    report export") and docs/architecture/16-reporting-architecture.md
    ("each sits behind the same export_report command regardless of
    which frontend technology calls it"), fronted in the current GUI by
    `MainWindow._export_report`'s own format-dispatch
    (app/gui/main_window.py), which calls one of
    `app.reporting.service.ReportingService`'s four confirmed per-format
    methods (`export_html`/`export_pdf`/`export_json`/`export_markdown`)
    with an already-resolved `(investigation, output_path)` pair.

    `export_format` is restricted to the four formats
    `ReportingService` actually implements. `docs/architecture/
    16-reporting-architecture.md` also lists a csv exporter, but that
    exporter (`app.gui.utils.csv_exporter.export_investigations_to_csv`)
    takes a *list* of investigations, not one, and has no confirmed
    single-investigation call site -- wrapping it here would be
    inventing behavior, not extracting an existing one, so it is
    deliberately excluded (see the Part 6 implementation doc's Known
    limitations).
    """

    investigation_id: int
    export_format: str
    output_path: str

    def __post_init__(self) -> None:
        if not isinstance(self.investigation_id, int) or isinstance(
            self.investigation_id, bool
        ):
            raise CommandValidationError("investigation_id must be an integer.")
        if self.investigation_id <= 0:
            raise CommandValidationError("investigation_id must be positive.")

        if (
            not isinstance(self.export_format, str)
            or self.export_format not in VALID_EXPORT_FORMATS
        ):
            raise CommandValidationError(
                f"export_format must be one of {VALID_EXPORT_FORMATS}."
            )

        if not isinstance(self.output_path, str) or not self.output_path.strip():
            raise CommandValidationError("output_path must be a non-empty string.")

        # Security boundary (docs/security/filesystem-security-model.md
        # TARGET STATE): the only legitimate source of `output_path` is
        # the native OS save dialog (`reportExportPath.ts::pickReportSavePath`),
        # which always resolves to a real, absolute, already-user-chosen
        # destination -- never a bare filename or a relative fragment
        # meant to be joined onto some base directory. There is no
        # "export root" this command confines writes to (the whole
        # point of the native dialog is letting the user pick anywhere
        # they have OS permission to write), so the applicable control
        # here is not directory confinement but rejecting exactly the
        # shape a legitimate caller never produces: any relative
        # `output_path` (e.g. `../report.csv`, `..\\report.csv`,
        # `reports/../../report.csv`, or a bare `report.csv`). Every
        # exporter (`app/reporting/*_exporter.py`) does
        # `output_path.parent.mkdir(parents=True, exist_ok=True)` and
        # then writes `output_path` directly with no validation of its
        # own, so without this check a request bypassing the dialog
        # (e.g. hitting the sidecar's local HTTP command endpoint
        # directly) could make the backend create directories and
        # write files at an attacker-chosen location relative to the
        # sidecar process's working directory.
        if not Path(self.output_path).is_absolute():
            raise CommandValidationError(
                "output_path must be an absolute path."
            )


@dataclass(frozen=True)
class ExportInvestigationsCsvRequest:
    """PD-08-P5.1: bulk investigation-history CSV export.

    Per docs/phase4/PD08_P5_1_BULK_CSV_EXPORT_BACKEND_CONTRACT.md. This
    is a distinct command from `export_report` (`ExportReportRequest`)
    -- that command exports one investigation's full report in one of
    four rich formats; this one exports every (optionally filtered)
    investigation's *summary* row as a single CSV, the bulk-history
    capability `app.gui.utils.csv_exporter.export_investigations_to_csv`
    provided in the legacy GUI (see that module and
    `app.gui.pages.history_page.HistoryPage._export_csv`) and that
    `ExportReportRequest`'s own docstring explicitly declined to fold
    in for exactly that reason.

    `output_path` follows the identical absolute-path validation rule
    `ExportReportRequest.output_path` already established, for the
    identical reason: the only legitimate source of this value is a
    native OS save dialog (the future `pages/history` frontend
    counterpart to `reportExportPath.ts::pickReportSavePath`), which
    always resolves to a real, absolute, user-chosen destination -- so
    a relative/bare path is rejected as a shape a legitimate caller
    never produces, not merely as "invalid input" in the abstract.

    `search`, when provided, mirrors the exact multi-field substring
    filter `InvestigationTableModel.filter` applies client-side in the
    legacy GUI (case-insensitive substring match against report name,
    severity, OR status) -- reconstructed here as an application-layer
    filter over `InvestigationService.list_all()`'s result rather than
    a new repository query, since no existing repository method
    supports an OR-across-three-fields search. `None`/absent means
    "no filter" (export every investigation), matching the legacy
    behavior of an empty search box.
    """

    output_path: str
    search: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.output_path, str) or not self.output_path.strip():
            raise CommandValidationError("output_path must be a non-empty string.")

        # Same rationale/threat-model as ExportReportRequest.__post_init__
        # above -- see that docstring for the full explanation. Kept as
        # an independent check (not a shared helper) because the two
        # request types are deliberately not coupled to each other.
        if not Path(self.output_path).is_absolute():
            raise CommandValidationError("output_path must be an absolute path.")

        if self.search is not None and not isinstance(self.search, str):
            raise CommandValidationError("search must be a string or null.")


#: The four categories `ThreatIntelService.lookup_indicator` /
#: its internal `_QUERY_TYPE_TO_IOC_TYPE` actually support -- the
#: same four categories `enrich_results` enriches.
VALID_IOC_TYPES = ("sha256", "ipv4", "domain", "url")


@dataclass(frozen=True)
class EnrichIocRequest:
    """Per docs/contracts/command-model.md `enrich_ioc` and the
    confirmed existing operation behind it:
    `ThreatIntelService.lookup_indicator` (Phase 4C, Stage 2),
    fronted in the current GUI by
    `app.gui.pages.threat_intel_page._VirusTotalLookupWorker.run`,
    which dispatches an interactive single-IOC lookup on a
    background thread.

    `ioc_type` is restricted to `VALID_IOC_TYPES`, mirroring
    `ExportReportRequest.export_format`'s validate-at-the-DTO
    pattern: `lookup_indicator` itself raises a bare `ValueError`
    for an unsupported type, which this DTO catches at the boundary
    instead so the failure surfaces as the same
    `INVALID_COMMAND_PAYLOAD` shape every other malformed-input
    rejection uses.

    `value` is only checked for being a non-empty string here --
    per-type format validation (hash shape, IP shape, etc.) is not
    duplicated from `app.gui.pages.threat_intel_page`'s regexes;
    that validation already exists once, inside the provider
    (`InvalidHashError`/`InvalidIPError`/`InvalidDomainError`/
    `InvalidURLError`), and `errors.py` already maps it to
    `TI_INVALID_IOC`.
    """

    ioc_type: str
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.ioc_type, str) or self.ioc_type not in VALID_IOC_TYPES:
            raise CommandValidationError(
                f"ioc_type must be one of {VALID_IOC_TYPES}."
            )
        if not isinstance(self.value, str) or not self.value.strip():
            raise CommandValidationError("value must be a non-empty string.")


@dataclass(frozen=True)
class DeleteInvestigationRequest:
    """Per docs/contracts/PHASE4B_COMMAND_INVENTORY.md `delete_investigation`.

    Validation mirrors GetInvestigationRequest deliberately -- both commands
    take the same investigation_id shape and the same positive-int
    constraint, and there is no reason for the two validation rules to
    drift.
    """

    investigation_id: int

    def __post_init__(self) -> None:
        if not isinstance(self.investigation_id, int) or isinstance(
            self.investigation_id, bool
        ):
            raise CommandValidationError("investigation_id must be an integer.")
        if self.investigation_id <= 0:
            raise CommandValidationError("investigation_id must be positive.")


# ---------------------------------------------------------------------------
# Response DTOs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InvestigationSummaryDTO:
    """The `data` shape for get_investigation / list_investigations.

    Deliberately omits `iocs` / `threat_intelligence` (the two largest,
    nested fields on the domain model) -- a summary DTO exists precisely
    so that a change to those nested domain shapes doesn't silently
    balloon or break this response. Full IOC/TI detail belongs to the
    not-yet-implemented `get_iocs` / `get_threat_intelligence` commands
    (docs/contracts/command-model.md).
    """

    investigation_id: int | None
    report_name: str
    risk_score: int
    severity: str
    confidence: float
    status: str
    analyzed_at: str

    #: A4-P1 evidence provenance. Included on the summary DTO itself
    #: (unlike `iocs`/`threat_intelligence`, deliberately reserved for
    #: `get_iocs`/`get_threat_intelligence`) because these are small
    #: scalar fields, not a large nested payload -- computing them
    #: imposes no meaningful extra cost on `list_investigations` /
    #: `search_investigations` / the Dashboard's
    #: `recent_investigations`. `None` means the same honest "never
    #: calculated" state `Investigation.source_sha256` itself
    #: documents (a legacy, pre-A4-P1 investigation).
    source_sha256: str | None
    source_size_bytes: int | None

    @classmethod
    def from_domain(cls, investigation: Investigation) -> "InvestigationSummaryDTO":
        analyzed_at = investigation.analyzed_at
        analyzed_at_str = (
            analyzed_at.isoformat()
            if isinstance(analyzed_at, datetime)
            else str(analyzed_at)
        )
        return cls(
            investigation_id=investigation.investigation_id,
            report_name=investigation.report_name,
            risk_score=investigation.risk_score,
            severity=investigation.severity,
            confidence=investigation.confidence,
            status=investigation.status,
            analyzed_at=analyzed_at_str,
            source_sha256=investigation.source_sha256,
            source_size_bytes=investigation.source_size_bytes,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "investigation_id": self.investigation_id,
            "report_name": self.report_name,
            "risk_score": self.risk_score,
            "severity": self.severity,
            "confidence": self.confidence,
            "status": self.status,
            "analyzed_at": self.analyzed_at,
            "source_sha256": self.source_sha256,
            "source_size_bytes": self.source_size_bytes,
        }


@dataclass(frozen=True)
class InvestigationCorrelationDTO:
    """The wire shape for one item in `get_investigation`'s additive
    `correlations` field (Phase 4J-6 correlations wiring).

    Deliberately scoped to `get_investigation` only -- kept as its own
    DTO here rather than as a field on `InvestigationSummaryDTO`,
    which is reused unchanged by `list_investigations`,
    `search_investigations`, and the Dashboard's
    `recent_investigations` (see that DTO's own docstring). Adding a
    field there would mean computing a correlation report for every
    investigation in every list/dashboard response, not just the one
    being viewed -- unnecessary work with no consumer, and a
    change to a response shape the Dashboard phase is frozen against.

    Maps `app.services.correlation_service.CorrelationService`'s
    already-computed, already-deterministic
    `CorrelationResult` (`app/services/correlation_models.py`, both
    left unmodified by this DTO) onto exactly the four fields
    `investigationCorrelationsModel.ts`'s `InvestigationCorrelation`
    actually consumes today:

        relationship_type <- CorrelationResult.relationship_type
        source            <- CorrelationResult.primary.value
        target            <- CorrelationResult.related.value
        context           <- CorrelationResult.reason

    `primary.ioc_type`, `primary.normalized_value`,
    `related.ioc_type`, `related.normalized_value` (comparison-only
    fields -- see `CorrelatedEvidence`'s own docstring) and
    `CorrelationSummary`'s aggregate counts are not exposed here:
    no current frontend code reads any of them, and adding unread
    fields to a response is exactly the kind of unrequested surface
    this phase's brief asks not to introduce.
    """

    relationship_type: str
    source: str
    target: str
    context: str

    @classmethod
    def from_domain(cls, result: CorrelationResult) -> "InvestigationCorrelationDTO":
        return cls(
            relationship_type=result.relationship_type,
            source=result.primary.value,
            target=result.related.value,
            context=result.reason,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "relationship_type": self.relationship_type,
            "source": self.source,
            "target": self.target,
            "context": self.context,
        }


@dataclass(frozen=True)
class SourceIntegrityDTO:
    """The `source_integrity` section of `get_investigation_provenance`
    (A4-P2 Part 2).

    Wraps `Investigation.source_sha256` / `source_size_bytes` -- the
    same A4-P1 fields `InvestigationSummaryDTO` already exposes --
    with an explicit `status` so a caller does not have to infer
    "hash missing" by checking a bare `None` itself. `status` is
    `"UNAVAILABLE"` only for the one honest reason
    `Investigation.source_sha256`'s own docstring documents: a legacy
    investigation persisted before A4-P1, whose hash was never
    calculated -- never fabricated or backfilled here.

    `algorithm` is `"sha256"` (the only algorithm
    `app.extractor.compute_source_provenance` has ever used) when a
    hash is present, `None` when it is not -- never a hardcoded
    `"sha256"` alongside a `None` hash, which would misleadingly imply
    an algorithm was used to produce no result.
    """

    report_name: str
    algorithm: str | None
    sha256: str | None
    size_bytes: int | None
    status: str
    reason: str | None

    @classmethod
    def from_domain(cls, investigation: Investigation) -> "SourceIntegrityDTO":
        hash_available = investigation.source_sha256 is not None
        return cls(
            report_name=investigation.report_name,
            algorithm="sha256" if hash_available else None,
            sha256=investigation.source_sha256,
            size_bytes=investigation.source_size_bytes,
            status="AVAILABLE" if hash_available else "UNAVAILABLE",
            reason=None if hash_available else "legacy_investigation_predates_source_hashing",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_name": self.report_name,
            "algorithm": self.algorithm,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "status": self.status,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class IOCProvenanceDTO:
    """One item of `get_investigation_provenance`'s `ioc_provenance`
    list (A4-P2 Part 2).

    Wraps `app.services.ioc_provenance.IOCProvenance` (A4-P2.1)
    unchanged -- no second, competing provenance data model is
    introduced at the DTO boundary. Field-for-field flattening of
    that frozen dataclass's nested `source`/`extraction` value
    objects, matching this module's own stated rule that domain
    objects never cross the command boundary directly.
    """

    ioc_value: str
    ioc_type: str
    state: str
    report_name: str
    source_sha256: str | None
    extraction_method: str

    @classmethod
    def from_domain(cls, record: IOCProvenance) -> "IOCProvenanceDTO":
        return cls(
            ioc_value=record.ioc_value,
            ioc_type=record.ioc_type,
            state=record.state.value,
            report_name=record.source.report_name,
            source_sha256=record.source.source_sha256,
            extraction_method=record.extraction.description,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "ioc_value": self.ioc_value,
            "ioc_type": self.ioc_type,
            "state": self.state,
            "report_name": self.report_name,
            "source_sha256": self.source_sha256,
            "extraction_method": self.extraction_method,
        }


@dataclass(frozen=True)
class IocCategoryContributionDTO:
    """One item of `RiskExplanationDTO.ioc_categories` (PD-08-P1).

    Field-for-field flattening of
    `app.services.risk_explanation_models.IocCategoryContribution` --
    matching this module's own stated rule that domain objects never
    cross the command boundary directly, the same pattern
    `IOCProvenanceDTO`/`TimelineEventDTO` already establish for other
    read-only domain wrappers.
    """

    ioc_type: str
    ioc_type_title: str
    count: int
    weight: int
    significance: str
    points: int

    @classmethod
    def from_domain(
        cls, contribution: IocCategoryContribution
    ) -> "IocCategoryContributionDTO":
        return cls(
            ioc_type=contribution.ioc_type,
            ioc_type_title=contribution.ioc_type_title,
            count=contribution.count,
            weight=contribution.weight,
            significance=contribution.significance,
            points=contribution.points,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "ioc_type": self.ioc_type,
            "ioc_type_title": self.ioc_type_title,
            "count": self.count,
            "weight": self.weight,
            "significance": self.significance,
            "points": self.points,
        }


@dataclass(frozen=True)
class RiskExplanationDTO:
    """`get_investigation_risk_explanation`'s response shape
    (PD-08-P1: docs/phase4/PD08_P1_RISK_EXPLANATION_BACKEND.md).

    Field-for-field flattening of
    `app.services.risk_explanation_models.RiskExplanation` -- the
    existing, already-tested (PHASE3C-1) deterministic explanation
    domain object `app.services.risk_explanation_service.
    RiskExplanationService.explain()` produces. This DTO adapts that
    existing capability onto the modern command boundary; it does not
    recompute, reinterpret, or duplicate any of the risk-explanation
    or risk-scoring logic -- matching `IOCProvenanceDTO`/
    `TimelineEventDTO`'s own stated rule that domain objects never
    cross the command boundary directly.

    `ioc_categories` is a plain list of `IocCategoryContributionDTO`,
    matching `RiskExplanation.ioc_categories`'s own deterministic
    ordering (highest point contribution first, tie-broken by
    category key) unchanged.
    """

    investigation_id: int | None
    report_name: str

    score: int
    severity: str
    confidence: float

    ioc_score: int
    threat_intel_score: int
    cve_score: int

    ioc_categories: list[IocCategoryContributionDTO]
    ioc_breakdown_verified: bool

    threat_intel_state: str
    threat_intel_message: str
    threat_intel_short_label: str
    threat_intel_requested: int
    threat_intel_succeeded: int
    threat_intel_malicious_hash_count: int
    threat_intel_suspicious_hash_count: int

    correlation_evaluated: bool
    correlation_relationship_count: int
    correlation_summary: str

    engine_reasons: list[str]

    narrative: list[str]
    warnings: list[str]

    @classmethod
    def from_domain(cls, explanation: RiskExplanation) -> "RiskExplanationDTO":
        return cls(
            investigation_id=explanation.investigation_id,
            report_name=explanation.report_name,
            score=explanation.score,
            severity=explanation.severity,
            confidence=explanation.confidence,
            ioc_score=explanation.ioc_score,
            threat_intel_score=explanation.threat_intel_score,
            cve_score=explanation.cve_score,
            ioc_categories=[
                IocCategoryContributionDTO.from_domain(category)
                for category in explanation.ioc_categories
            ],
            ioc_breakdown_verified=explanation.ioc_breakdown_verified,
            threat_intel_state=explanation.threat_intel_state,
            threat_intel_message=explanation.threat_intel_message,
            threat_intel_short_label=explanation.threat_intel_short_label,
            threat_intel_requested=explanation.threat_intel_requested,
            threat_intel_succeeded=explanation.threat_intel_succeeded,
            threat_intel_malicious_hash_count=(
                explanation.threat_intel_malicious_hash_count
            ),
            threat_intel_suspicious_hash_count=(
                explanation.threat_intel_suspicious_hash_count
            ),
            correlation_evaluated=explanation.correlation_evaluated,
            correlation_relationship_count=(
                explanation.correlation_relationship_count
            ),
            correlation_summary=explanation.correlation_summary,
            engine_reasons=list(explanation.engine_reasons),
            narrative=list(explanation.narrative),
            warnings=list(explanation.warnings),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "investigation_id": self.investigation_id,
            "report_name": self.report_name,
            "score": self.score,
            "severity": self.severity,
            "confidence": self.confidence,
            "ioc_score": self.ioc_score,
            "threat_intel_score": self.threat_intel_score,
            "cve_score": self.cve_score,
            "ioc_categories": [
                category.to_dict() for category in self.ioc_categories
            ],
            "ioc_breakdown_verified": self.ioc_breakdown_verified,
            "threat_intel_state": self.threat_intel_state,
            "threat_intel_message": self.threat_intel_message,
            "threat_intel_short_label": self.threat_intel_short_label,
            "threat_intel_requested": self.threat_intel_requested,
            "threat_intel_succeeded": self.threat_intel_succeeded,
            "threat_intel_malicious_hash_count": (
                self.threat_intel_malicious_hash_count
            ),
            "threat_intel_suspicious_hash_count": (
                self.threat_intel_suspicious_hash_count
            ),
            "correlation_evaluated": self.correlation_evaluated,
            "correlation_relationship_count": (
                self.correlation_relationship_count
            ),
            "correlation_summary": self.correlation_summary,
            "engine_reasons": self.engine_reasons,
            "narrative": self.narrative,
            "warnings": self.warnings,
        }


@dataclass(frozen=True)
class TimelineEventDTO:
    """One item of `get_timeline`'s `events` list (A4-P2-P3 Part 3).

    Field-for-field flattening of `app.timeline.domain.TimelineEvent`
    (the Part 1 domain object) -- matching this module's own stated
    rule that domain objects never cross the command boundary
    directly, the same pattern `IOCProvenanceDTO`/`SourceIntegrityDTO`
    already establish for other read-only domain wrappers.

    `event_type` is the plain `str` value (`event_type.value`, e.g.
    `"analysis.completed"`), not the `TimelineEventType` enum member
    itself -- enums are not JSON-serializable and the wire contract is
    the same stable vocabulary string
    `docs/architecture/20-investigation-timeline-architecture.md`
    already documents. `timestamp` is the ISO-8601 string form
    (`datetime.isoformat()`), matching every other timestamp already
    on the wire (see `InvestigationSummaryDTO.analyzed_at`).

    `semantics` (what the event type actually asserts, e.g. "SOC-IQ's
    analysis pipeline completed successfully...") is included so a
    frontend consumer never needs to duplicate
    `TIMELINE_EVENT_SEMANTICS` as a second, drift-prone copy of the
    same controlled vocabulary's meaning.

    `investigation_id` is included per-event (even though every event
    in one response necessarily shares the same id as the request)
    for the same reason `IOCProvenanceDTO` includes its own
    `report_name`/`source_sha256` per-item: a caller consuming one
    event in isolation (e.g. a future export) does not need to also
    thread the parent id through separately.
    """

    event_id: str
    investigation_id: int
    event_type: str
    timestamp: str
    source: str
    summary: str
    metadata: dict[str, Any]
    semantics: str

    @classmethod
    def from_domain(cls, event: TimelineEvent) -> "TimelineEventDTO":
        return cls(
            event_id=event.event_id,
            investigation_id=event.investigation_id,
            event_type=event.event_type.value,
            timestamp=event.timestamp.isoformat(),
            source=event.source,
            summary=event.summary,
            metadata=event.metadata,
            semantics=event.semantics,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "investigation_id": self.investigation_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "source": self.source,
            "summary": self.summary,
            "metadata": self.metadata,
            "semantics": self.semantics,
        }


@dataclass(frozen=True)
class DashboardMetricsDTO:
    """The `metrics` sub-shape of `DashboardSummaryDTO` (Phase 4H
    Part 1) -- the Dashboard's KPI row, as real typed values.

    Wraps `app.services.dashboard_aggregation.compute_dashboard_metrics`
    (report/IOC/high-risk counts) and
    `compute_threat_intel_coverage_percent` (see that function's own
    docstring for why this is a genuine, non-fabricated calculation
    derived from already-persisted `threat_intelligence["coverage"]`
    data, and why it is `None` rather than `0.0` when no coverage data
    exists at all). This is deliberately NOT
    `DashboardStatisticsService.get_summary()`'s stringly-typed dict
    (`{"reports": "3", ...}`) -- that shape exists for its own GUI
    caller and is reused unchanged for that purpose; this DTO exposes
    the same underlying counts as real JSON numbers, and never
    includes that service's static `"database": "Connected"` field,
    which is presentation-layer flavor text unconditionally hardcoded
    to `"Connected"` rather than a genuine measurement -- carrying it
    into an API contract would be exactly the "fabricated value" this
    phase's brief prohibits.
    """

    total_reports: int
    total_iocs: int
    high_risk_count: int
    threat_intel_coverage_percent: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_reports": self.total_reports,
            "total_iocs": self.total_iocs,
            "high_risk_count": self.high_risk_count,
            "threat_intel_coverage_percent": self.threat_intel_coverage_percent,
        }


@dataclass(frozen=True)
class DashboardSummaryDTO:
    """The `data` shape for `get_dashboard_summary` (Phase 4H Part 1,
    docs/phase4/PHASE4H_PART1_BACKEND_API_CONTRACT.md).

    Built once, server-side, from a single `InvestigationService
    .list_all()` call plus one `find_recent()` call for
    `recent_investigations` -- never per-investigation follow-up
    queries (no N+1). Every field is genuinely derivable from already-
    persisted data; nothing here is invented:

      - `metrics`: KPI row (`DashboardMetricsDTO`).
      - `investigation_status_counts`: investigations grouped by the
        REAL, persisted `Investigation.status` field (see
        `app.services.dashboard_aggregation.compute_status_counts`'s
        docstring for why this is deliberately not the frontend
        mock's `open`/`in_progress`/`closed` vocabulary -- that
        concept does not exist in persisted data today).
      - `risk_distribution`: investigations grouped by `severity`.
      - `ioc_distribution`: IOC counts grouped by `ioc_type`, the
        same calculation `DashboardIOCDistributionService` already
        performed (now shared via `dashboard_aggregation`).
      - `recent_investigations`: reuses `InvestigationSummaryDTO`
        unchanged (the same wire shape `get_investigation` /
        `list_investigations` already return) rather than inventing
        a second investigation-summary shape for the Dashboard alone.

    Timeline data is deliberately NOT included -- Phase 4H's own
    readiness review flagged Timeline as an unresolved product
    decision, and including it here would lock the UI into a shape
    before that decision is made. Operational status is also
    deliberately NOT included -- the frontend already gets it from a
    live, real-time source (`useSidecarStatus()` /
    `projectSidecarStatusView()`, per `dashboardViewModel.ts`'s own
    doc comment), so duplicating a point-in-time copy of it into this
    aggregate snapshot would just be a second, potentially-stale
    source of truth for the same fact.
    """

    metrics: DashboardMetricsDTO
    investigation_status_counts: dict[str, int]
    risk_distribution: dict[str, int]
    ioc_distribution: dict[str, int]
    recent_investigations: list[InvestigationSummaryDTO]

    def to_dict(self) -> dict[str, Any]:
        return {
            "metrics": self.metrics.to_dict(),
            "investigation_status_counts": self.investigation_status_counts,
            "risk_distribution": self.risk_distribution,
            "ioc_distribution": self.ioc_distribution,
            "recent_investigations": [
                investigation.to_dict()
                for investigation in self.recent_investigations
            ],
        }


@dataclass(frozen=True)
class InvestigationAggregateSummaryDTO:
    """The `data` shape for `get_investigation_aggregate_summary`
    (PD-04, docs/phase4/PD04_CROSS_INVESTIGATION_AGGREGATE_COMMANDS.md).

    Deliberately reuses the exact same pure aggregation functions
    (`app.services.dashboard_aggregation`) that
    `GetDashboardSummaryCommandHandler` already uses for
    `investigation_status_counts` / `risk_distribution` /
    `ioc_distribution` / `threat_intel_coverage_percent` -- this is a
    second *consumer* of that one existing calculation, not a second,
    independently-maintained copy of it. This is a standalone,
    Dashboard-independent command (unlike `DashboardSummaryDTO`, it
    carries no `recent_investigations` list and no page-specific KPI
    shape) so a future non-Dashboard consumer of cross-investigation
    aggregates is not forced to depend on Dashboard's response
    contract.

    `investigations_by_date` is the one genuinely new aggregate PD-04
    adds beyond what `get_dashboard_summary` already returns -- see
    `compute_investigation_activity_by_date`'s own docstring for why
    this is deliberately not the Dashboard's still-undecided Timeline
    feature.
    """

    total_investigations: int
    status_counts: dict[str, int]
    severity_distribution: dict[str, int]
    ioc_distribution: dict[str, int]
    threat_intel_coverage_percent: float | None
    investigations_by_date: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_investigations": self.total_investigations,
            "status_counts": self.status_counts,
            "severity_distribution": self.severity_distribution,
            "ioc_distribution": self.ioc_distribution,
            "threat_intel_coverage_percent": self.threat_intel_coverage_percent,
            "investigations_by_date": self.investigations_by_date,
        }
