"""
Thin FastAPI transport layer over app.application (see
docs/phase4/PHASE4D_API_EVENT_ARCHITECTURE.md S6.4).

NOT executed or tested in this phase: fastapi/pydantic/uvicorn are not
installed and this environment has no network access to install them.
Written to be mechanically correct against documented FastAPI APIs, but
should be run through `uvicorn app.api.app:app` and smoke-tested before
being relied upon.
"""
