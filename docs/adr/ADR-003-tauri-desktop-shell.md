# ADR-003: Tauri as the Desktop Shell and Capability Boundary

**Status:** Proposed
**Related:** Master Plan §28, §7, baseline problem #15.

## Context

Introducing a React frontend requires a desktop shell to host it, package it, and mediate its
access to the operating system. The current PySide6 app has no equivalent capability-scoped
boundary — Qt widgets call OS-integration APIs in-process with no declared permission model.

## Problem

A plain web view (e.g. Electron with default settings, or a bare browser-based app) does not
by itself provide a least-privilege permission boundary between frontend JavaScript and
native OS capabilities, and general-purpose runtimes like Electron carry a larger bundled
footprint than necessary for this use case.

## Decision

Tauri is adopted as the desktop shell: window lifecycle, packaging, and — critically — an
explicit, declared capability/permission model (Master Plan §7) that determines exactly what
native operations the frontend may request. Master Plan baseline problem #15 states no
current evidence *technically requires* Tauri; its justified value is specifically the native
shell/capability/security boundary it provides, not raw necessity.

## Alternatives Considered

- **Electron.** Larger bundled runtime (ships its own Chromium + Node), and its default
  security posture requires more manual hardening to reach an equivalent least-privilege
  capability model to what Tauri provides out of the box.
- **A bare Python-served local web page opened in the OS's default browser.** Rejected —
  provides no packaging story, no native OS integration (notifications, file dialogs), and no
  capability boundary at all; effectively worse than the current PySide6 app on every axis
  except technology novelty.

## Rejected Alternatives (explicit)

Building a fully custom native shell (no framework) — rejected as unjustified engineering
cost for a single-developer desktop-security-tool project; Tauri already provides the
capability model this project specifically needs (Master Plan §7).

## Consequences

- Positive: least-privilege capability manifest is a first-class Tauri feature, not something
  built from scratch (see `docs/security/tauri-capability-model.md`).
- Negative: Tauri requires a Rust toolchain in the build pipeline, which is new to this
  project's build/release process (see `docs/architecture/18-packaging-release-architecture.md`).

## Security Implications

This is the ADR most directly responsible for closing the "no current trust boundary" gap
noted in `docs/architecture/04-tauri-rust-architecture.md`'s current-state section. Full
detail: `docs/security/tauri-capability-model.md`.

## Migration Implications

Tauri foundation work is Phase 4E (Master Plan §26); its exit criterion — "sidecar lifecycle
(spawn/health/kill) proven" — has no dependency on any frontend or business-logic code
existing yet.
