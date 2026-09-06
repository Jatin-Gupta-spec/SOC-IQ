# DTO Boundaries

**Status:** Documentation Foundation (Phase 4A).
**Related:** `docs/architecture/02-python-backend-architecture.md`, `command-model.md`,
`response-model.md`.

## CURRENT STATE

The current architecture has no DTO boundary — Qt controllers/services call domain functions
and receive Python domain objects directly, in-process (CONFIRMED, Master Plan §1.1). There
is no existing serialization layer to describe as current state beyond this absence.

## TARGET STATE (PROPOSED)

A strict boundary is introduced at the `backend/app/api/` layer (see
`docs/architecture/02-python-backend-architecture.md`):

- Domain objects (`app/domain/*` models) never cross the API boundary directly — every
  command handler maps a domain object to an explicit DTO (Pydantic model) before it's
  serialized into a command response, and maps an incoming validated DTO to domain-layer
  arguments before calling application/domain logic.
- This mapping step is deliberate, not an incidental side effect of using Pydantic for HTTP
  — it exists so that a change to an internal domain model's shape does not automatically
  become a breaking change to the frontend contract; the DTO is the frontend's actual
  contract, and is versioned independently via the event/response models
  (`event-versioning.md`).
- The same DTOs are the source from which TypeScript client types are generated (Master Plan
  §16), so the frontend's types are always derived from the same schema the backend
  validates against — never hand-duplicated.

## MIGRATION NOTES

DTO definitions are written per-command as each command is implemented in Phase 4D, informed
by the Phase 4B inventory of current controller/service data shapes.

## UNKNOWN / REQUIRES VERIFICATION

See `docs/architecture/02-python-backend-architecture.md` — the underlying domain data shapes
this DTO layer will wrap are not yet exhaustively inventoried. **UNKNOWN — VERIFY IN
PHASE 4B.**
