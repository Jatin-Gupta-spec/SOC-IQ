# SOC-IQ — Post-Freeze Implementation, Part 1 of 4: Product-Decision Gate

## Entry checkpoint

`SOC-IQ-POST-SECURITY-FREEZE-FINAL-AUDIT.zip` (the prior independent final audit).

## Outcome

**NO IMPLEMENTATION PERFORMED.** Per that audit's own §1 escape hatch
("if the audit says no implementation should begin because product
decisions are unresolved, stop"), this pass re-audited the named next-phase
item against current source *before* writing any code, found the item as
scoped does not hold up, and is stopping rather than inventing scope or
guessing at a product decision.

## Re-audit findings (source-verified this session, no code changed)

### 1. `AnalyzePage.tsx` — audit's mock characterization is stale

The prior audit's evidence quote — *"file input, parsing, and analysis
execution are not implemented in this checkpoint"* — is still literally
present in the file, but only as one branch of a conditional `InfoNote`.
Current source already:

- imports and calls `useAnalysisExecution`
- drives a real `ready → analyzing → completed/failed` workflow against
  the real `analyze_report` command
- offers real retry on failure

The only remaining mock is a static `mockRecentAnalysisRuns` list rendered
below the real workflow. This is a small, well-scoped, non-ambiguous fix —
no product decision blocks it.

### 2. `IocExplorerPage.tsx` / `ThreatIntelPage.tsx` — not a drop-in wiring change

`GetIocsPayload` and `GetThreatIntelligencePayload` both require an
`investigation_id: number`. There is no aggregate/cross-investigation
variant of either command. But `IocExplorerPage` and `ThreatIntelPage` are
registered as top-level nav routes (`/ioc-explorer`, `/threat-intel`), not
investigation-scoped ones.

A separate, already-real pair — `InvestigationIocWorkspace` and
`InvestigationThreatIntel` — already calls these same two commands
correctly, because it has a real `investigation_id` from its investigation-
scoped route context. The top-level pages have no such context to pass.

Making the top-level pages real therefore requires one of:

- **(a)** adding an investigation-picker to these pages (a UX decision:
  which investigation does a cross-cutting "IOC Explorer" default to,
  and how does a user change it), or
- **(b)** adding new aggregate backend commands
  (`get_all_iocs` / `get_all_threat_intelligence`) that don't exist today.

Both are new scope beyond "smallest complete implementation using the
existing architecture" (§5 of the implementation prompt) and were not
identified as open items by the prior audit — they are a genuine gap this
re-audit surfaced, not a documentation staleness issue.

### 3. `InvestigationOverviewThreatIntel.tsx` sub-panel

Not re-examined in detail this pass, since it was lower priority than the
two findings above and the pass stopped at the decision gate before
reaching it.

## Change scope

```
Production code: NONE
Test code:       NONE
Documentation:   THIS FILE ONLY (new; nothing existing was rewritten)
```

## Security

Not applicable — no code changed. §20 freeze, keystore ownership,
capability protection, and export protection are all untouched.

## Phase 4O

Not applicable — no code changed. Legacy GUI isolation (66 retained
`app/gui` files, 7 GUI test suites, zero outside imports) is untouched.

## Product-Decision Register

| ID | Decision | Status |
|---|---|---|
| PD-01 | AnalyzePage completion (remove leftover mock recent-runs list) | DEFERRED |
| PD-02 | IOC Explorer investigation context/picker | DEFERRED |
| PD-03 | Threat Intel investigation context/picker | DEFERRED |
| PD-04 | Aggregate cross-investigation backend commands | DEFERRED |

See `docs/phase4/POST_FREEZE_IMPLEMENTATION_OPTIONS.md` for the detailed
implementation-readiness analysis of each item above. None of these are
approved; this table exists so the decision register is visible from the
repository itself, not only from session-report text.

## Decision needed before further frontend wiring work

1. For IOC Explorer / Threat Intel (top-level pages): investigation-picker
   UX, or new aggregate backend commands? Owner input required.
2. Should `AnalyzePage`'s recent-runs list be wired in the same pass as
   whichever of the above is chosen, or treated as its own small
   independent item since it has no such blocker?

## Verdict

**PASS WITH CONDITIONS** — re-audit performed, no regression introduced
(no code touched), one small independent item identified
(`AnalyzePage` recent-runs list) and two items blocked on a documented
product decision. Next pass should start from the checkpoint produced by
this report once the decision above is made, or should implement the
`AnalyzePage` item alone if that's preferred as the actual Part 1 item.
