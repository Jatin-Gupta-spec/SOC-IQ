# Phase 4B — Git Baseline Note

The uploaded source archive (`SOC-IQ-Phase4A-DOCUMENTATION-FROZEN.zip`) contains no `.git`
directory — it is a flat source snapshot, not a git checkout. `git status` and `git log -n 5`
both failed with `fatal: not a git repository` before any work began this phase.

This means:

- Phase brief §3 ("verify the repository baseline" via `git status`/`git log`) could not be
  performed against real history — there is none in this archive.
- Phase brief §20's final `git diff --stat`/`git diff --name-only`/`git log -n 5` checks
  are performed this phase against a **locally initialized repository**, created solely to
  give this checkpoint a verifiable diff going forward. That local repository's history
  starts at this phase, not at Phase 4A or earlier — it is not a substitute for the project's
  real development history, which lives elsewhere and was not included in this archive.

If the actual project repository does have full history, future phases should work directly
against a clone of it rather than this archive, so `git log` reflects real project history
instead of a synthetic single-commit baseline created for this documentation pass.
