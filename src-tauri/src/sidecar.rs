//! Part 2B: real sidecar process adapter.
//!
//! Wires `sidecar-core`'s framework-independent `Supervisor` to actual
//! OS process spawning, actual stdout handshake reading, and an actual
//! (minimal, dependency-free) HTTP health check -- the "future Tauri/
//! native adapter" that `sidecar-core`'s own doc comments describe as
//! depending on it, never the reverse. This module is the ONLY place
//! in the SOC-IQ Rust code that spawns a process, opens a socket, or
//! blocks on a timer; `sidecar-core` continues to do none of those
//! things (see its crate-level "Hard architectural boundary" doc).
//!
//! Deliberately dependency-free: uses `std::process`, `std::net`, and
//! `std::time` only, consistent with `src-tauri/Cargo.toml`'s existing
//! decision to defer `tokio`/`reqwest` until an actual caller needs
//! them. This module is that caller, but a synchronous std-only
//! implementation is sufficient for one child process and one health
//! poll, so no async runtime is added here.
//!
//! # Ownership
//!
//! `sidecar_core::Supervisor` remains the single source of truth for
//! lifecycle *state*. This module owns the process handle and the wall
//! clock, and reports every observation it makes (spawn result,
//! handshake line, health result, exit status, elapsed time) to the
//! supervisor via its existing public API -- exactly as
//! `docs/phase4/PHASE4_PRE_2A_CONTRACT.md` §2/§4 describe. This module
//! never reads or mutates `Supervisor`'s internal state directly; it
//! only calls its public event methods, so there is exactly one
//! lifecycle owner (task brief §3).
//!
//! # NOT implemented here (deferred to a later phase, per task brief §9)
//!
//! - No `#[tauri::command]` registration and no wiring into
//!   `src-tauri/src/lib.rs`'s `tauri::Builder` -- that is the Tauri
//!   command/event-bridge phase, a distinct increment from "can this
//!   adapter supervise a real process at all".
//! - No event emission -- `lib.rs` (Phase 4E-P2 Part 2A) now drives
//!   `poll_for_crash()` on a real periodic loop once `RUNNING`, but
//!   only detects and logs a crash; emitting a Tauri event about it
//!   still belongs to whichever phase adds the Tauri event bridge
//!   (`docs/contracts/event-model.md`).
//! - No automatic restart after a detected crash -- Phase 4E-P2 Part 2B.
//! - No graceful (SIGTERM-then-escalate) shutdown signal -- see
//!   `SidecarProcess::shutdown`'s doc comment for why a hard kill was
//!   the smallest production-correct increment for Part 2B specifically.

use std::io::{BufRead, BufReader, Read, Write};
use std::net::TcpStream;
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::time::{Duration, Instant};

use keystore_core::{KeystoreError, RustSecretStore, SecretStore};
use sidecar_core::{ExitStatus, LifecycleState, ShutdownOutcome, SidecarError, Supervisor};

/// Phase 4O Security Part 1B-1 (ADR-008: "Rust owns OS keystore access"): the
/// `keystore-core`/`app/secrets/store.py` secret `name` the VirusTotal API key is stored
/// under. Deliberately identical on both sides of the language boundary -- see
/// `app/settings/repository.py`'s `_VT_API_KEY_SECRET_NAME` and `keystore-core::store`'s own
/// module doc ("same seam `app/secrets/store.py`'s `SecretStore` protocol already uses... so
/// Part 1B's eventual handoff has a matching vocabulary on both ends").
const VIRUSTOTAL_SECRET_NAME: &str = "virustotal_api_key";

/// Environment variable the VirusTotal credential is exposed to the Python sidecar under, for
/// exactly the lifetime of that one child process (ADR-008: "Python receives the key at
/// sidecar startup via a short-lived process-scoped handoff (e.g. an environment variable set
/// only for the child process)"). Never set on this (the Rust parent) process's own
/// environment -- see [`apply_secret_handoff`]'s doc for why, and this module's "process-scoped
/// only" guarantee.
///
/// Part 1B-1 scope note: this constant is now defined and the child environment is populated
/// from it (below), but nothing on the Python side reads it yet -- `app/secrets/store.py`
/// still reads the OS keystore directly via `keyring`, unchanged, until Part 1B-2. Both paths
/// resolve to the same underlying OS credential store entry (`SERVICE_NAME`/`_SERVICE_NAME`
/// are identical, `"SOC-IQ"`), so this is an additive, currently-unconsumed handoff, not a
/// second, divergent credential source.
pub const VIRUSTOTAL_ENV_VAR: &str = "SOCIQ_SECRET_VIRUSTOTAL_API_KEY";

/// How the sidecar process should be located and launched.
///
/// The real sidecar is `python -m app.api.entrypoint`
/// (`app/api/entrypoint.py`) -- see that module's own doc comment for
/// the loopback/ephemeral-port/handshake contract this adapter relies
/// on. `python_executable` and `working_directory` are parameters
/// (rather than hard-coded) so a caller (a test, or real Tauri startup
/// code resolving the repo root) can point this at a controllable
/// location instead of assuming the current process's cwd.
///
/// Part 3A-2A (production sidecar packaging): `args` was added so a
/// packaged, production launch and a source-checkout, development
/// launch can share this same struct and the same `start()` code path
/// without either one having to lie about its command line. A source
/// checkout still runs `python -m app.api.entrypoint` (this struct's
/// `Default` reproduces that exactly, unchanged, so every pre-existing
/// caller/test keeps its previous behavior). A packaged installation
/// instead launches the frozen `socq-backend(.exe)` executable
/// directly, which is already the whole `app.api.entrypoint` program
/// (see `packaging/pyinstaller/socq_backend.spec`) -- passing it
/// `-m app.api.entrypoint` would be a `python`-interpreter argument
/// handed to a program that is not the `python` interpreter, so
/// production launches with `args` empty instead. This is the one
/// genuinely-required command-line change task brief S8 asks to be
/// documented rather than made silently; everything else about the
/// launch contract (loopback host, ephemeral port, stdout handshake
/// line, env-var secret handoff, shutdown signal) is unchanged.
#[derive(Debug, Clone)]
pub struct SidecarLaunchConfig {
    pub python_executable: String,
    pub working_directory: PathBuf,
    pub args: Vec<String>,
}

impl Default for SidecarLaunchConfig {
    fn default() -> Self {
        Self {
            python_executable: "python".to_string(),
            working_directory: PathBuf::from("."),
            args: vec!["-m".to_string(), "app.api.entrypoint".to_string()],
        }
    }
}

/// A running (or previously-running) supervised sidecar process.
///
/// Combines the OS process handle with the framework-independent
/// `Supervisor` from `sidecar-core`. All public methods drive the
/// supervisor's event API as a side effect, so `self.state()` is
/// always the authoritative lifecycle state -- callers should read
/// state from there, never infer it from whether an internal child
/// handle is present.
pub struct SidecarProcess {
    supervisor: Supervisor,
    child: Option<Child>,
    port: Option<u16>,
}

impl SidecarProcess {
    pub fn new(supervisor: Supervisor) -> Self {
        Self {
            supervisor,
            child: None,
            port: None,
        }
    }

    pub fn state(&self) -> LifecycleState {
        self.supervisor.state()
    }

    pub fn port(&self) -> Option<u16> {
        self.port
    }

    /// Explicit recovery step (Phase 4E-P2 Part 2B-2): any terminal
    /// state (`FAILED`/`TIMEOUT`/`CRASHED`/`STOPPED`) -> `NOT_STARTED`,
    /// wrapping `Supervisor::reset()` unchanged (no new core-FSM
    /// behavior, per the architecture doc §5). A caller driving an
    /// automatic restart (`src-tauri/src/lib.rs`'s restart-scheduling
    /// logic) calls this immediately before a fresh [`SidecarProcess::start`]
    /// -- exactly the same two-call sequence a manual restart would
    /// use, just invoked automatically instead of only ever by hand.
    /// This does not itself decide *whether* a restart should happen;
    /// that is `RestartPolicy`/`RestartTracker`'s job (§7) -- this
    /// method only performs the state transition once that decision has
    /// already been made.
    pub fn reset(&mut self) -> Result<(), SidecarError> {
        self.supervisor.reset()
    }

    /// Full startup sequence: `NOT_STARTED -> STARTING`, spawn the
    /// real process, read+validate the handshake, poll `/health` until
    /// it succeeds or the startup timeout elapses. On any failure, the
    /// supervisor is left in the correct terminal state
    /// (`FAILED`/`TIMEOUT`) per contract §2/§3, and the child process
    /// is killed if it is still running (contract §2: "on expiry ...
    /// it is killed as part of the timeout handling").
    pub fn start(&mut self, config: &SidecarLaunchConfig) -> Result<(), SidecarError> {
        self.supervisor.request_start()?;

        let start_instant = Instant::now();

        let mut command = Command::new(&config.python_executable);
        command
            .args(&config.args)
            .current_dir(&config.working_directory)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .stdin(Stdio::null());

        // Phase 4O Security Part 1B-1 (ADR-008): retrieve the VirusTotal credential from the
        // Rust-owned OS keystore and place it into *this specific child's* environment only,
        // immediately before spawning it -- see `apply_secret_handoff`'s own doc for the full
        // missing-credential/backend-unavailable contract and the secret-safety guarantees.
        apply_secret_handoff(&mut command, &RustSecretStore::new());

        let mut child = match command.spawn() {
            Ok(child) => child,
            Err(io_err) => return self.supervisor.spawn_failed(io_err.to_string()),
        };

        let line = match Self::read_handshake_line(&mut child) {
            Ok(line) => line,
            Err(_) => {
                Self::kill_and_reap(&mut child);
                let elapsed = start_instant.elapsed();
                return self.supervisor.startup_timed_out(elapsed);
            }
        };

        let startup_info = match self.supervisor.validate_handshake(&line) {
            Ok(info) => info,
            Err(parse_err) => {
                Self::kill_and_reap(&mut child);
                return self.supervisor.handshake_failed(parse_err);
            }
        };

        self.port = Some(startup_info.port);
        let timeouts = self.supervisor.timeouts();

        loop {
            if Self::poll_exit(&mut child).is_some() {
                // The process exited before ever becoming healthy --
                // this is a startup failure, not a crash (contract
                // distinguishes STARTING->TIMEOUT/FAILED from
                // RUNNING->CRASHED; the process was never RUNNING).
                let elapsed = start_instant.elapsed();
                return self.supervisor.startup_timed_out(elapsed);
            }

            if health_check_ok(startup_info.port) {
                self.child = Some(child);
                return self.supervisor.health_check_succeeded();
            }

            if start_instant.elapsed() >= timeouts.startup {
                Self::kill_and_reap(&mut child);
                let elapsed = start_instant.elapsed();
                return self.supervisor.startup_timed_out(elapsed);
            }

            std::thread::sleep(Duration::from_millis(100));
        }
    }

    /// `RUNNING -> STOPPING -> STOPPED`: request shutdown, then wait
    /// (bounded) for the process to actually exit before declaring
    /// success (contract §4). A no-op success if the sidecar was not
    /// `RUNNING` (delegated entirely to `Supervisor::request_shutdown`'s
    /// existing no-op behavior).
    ///
    /// **Kill signal note:** `std::process::Child` has no portable
    /// graceful-terminate primitive -- `Child::kill()` is SIGKILL on
    /// Unix and `TerminateProcess` on Windows, both hard kills, not a
    /// SIGTERM the Python sidecar's own signal handler could catch. A
    /// real graceful shutdown needs a platform-specific dependency
    /// (`libc` on Unix, `windows`/`winapi` on Windows) that
    /// `src-tauri/Cargo.toml` deliberately does not carry yet. Part
    /// 2B's smallest production-correct increment (task brief §4)
    /// sends the hard kill immediately rather than adding that
    /// dependency speculatively -- this is contract-safe because the
    /// sidecar has no unflushed state of its own to lose (persistent
    /// writes happen in the Python domain/database layer this process
    /// boundary never touches directly) -- and then still *waits*
    /// (bounded) for the OS to confirm the process is actually gone
    /// before returning, so the "no orphaned process" invariant
    /// (contract §4) holds regardless of which kill signal was used.
    /// A graceful SIGTERM-first escalation path is intentionally
    /// deferred, not silently dropped -- see the module-level "NOT
    /// implemented here" note.
    pub fn shutdown(&mut self) -> Result<(), SidecarError> {
        let outcome = self.supervisor.request_shutdown()?;
        if !matches!(outcome, ShutdownOutcome::Stopping) {
            return Ok(());
        }

        let Some(mut child) = self.child.take() else {
            // RUNNING but no child handle should be unreachable in
            // practice (start() always sets self.child before
            // returning Ok on the success path), but if it ever
            // happens there is nothing left to wait on -- report the
            // process as exited rather than leaving the supervisor
            // stuck in STOPPING forever.
            return self.supervisor.process_exited(ExitStatus::unknown());
        };

        let shutdown_timeout = self.supervisor.timeouts().shutdown;
        let deadline = Instant::now() + shutdown_timeout;

        let _ = child.kill();

        loop {
            match child.try_wait() {
                Ok(Some(status)) => {
                    return self
                        .supervisor
                        .process_exited(ExitStatus { code: status.code() });
                }
                Ok(None) => {
                    if Instant::now() >= deadline {
                        return self.supervisor.shutdown_timed_out(shutdown_timeout);
                    }
                    std::thread::sleep(Duration::from_millis(50));
                }
                Err(_) => {
                    // try_wait() itself failed (rare OS-level error).
                    // Treat as "could not confirm exit" -> shutdown
                    // failure, same as a real timeout, rather than
                    // guessing success.
                    return self.supervisor.shutdown_timed_out(shutdown_timeout);
                }
            }
        }
    }

    /// Non-blocking check: has the child already exited on its own
    /// while `RUNNING`? A caller's own event loop polls this to detect
    /// a crash (contract §1 `RUNNING -> CRASHED`). This module does not
    /// itself run a background poll loop -- it only exposes the
    /// primitive -- but as of Phase 4E-P2 Part 2A, `lib.rs`'s `run()`
    /// is a real caller: see its `setup` closure's crash-poll loop.
    pub fn poll_for_crash(&mut self) -> Option<Result<(), SidecarError>> {
        let child = self.child.as_mut()?;
        match child.try_wait() {
            Ok(Some(status)) => {
                self.child = None;
                Some(
                    self.supervisor
                        .unexpected_exit(ExitStatus { code: status.code() }),
                )
            }
            _ => None,
        }
    }

    fn poll_exit(child: &mut Child) -> Option<std::process::ExitStatus> {
        child.try_wait().ok().flatten()
    }

    fn kill_and_reap(child: &mut Child) {
        let _ = child.kill();
        let _ = child.wait();
    }

    /// Read exactly one line from the child's stdout -- the
    /// synchronous handshake (contract §2). This blocks the calling
    /// thread until the child either writes a line or its stdout pipe
    /// closes (e.g. because it exited); a process that hangs without
    /// writing or exiting would block this call indefinitely, which is
    /// a known limitation of the synchronous std-only approach (see
    /// module doc) -- `start()`'s overall timeout still applies to the
    /// rest of the sequence, but not to this specific blocking read.
    /// A future increment could use a non-blocking read with its own
    /// poll loop if a hang-without-exit sidecar bug is ever observed
    /// in practice; Part 2B does not add that complexity speculatively.
    fn read_handshake_line(child: &mut Child) -> std::io::Result<String> {
        let stdout = child.stdout.as_mut().ok_or_else(|| {
            std::io::Error::new(
                std::io::ErrorKind::Other,
                "child process has no captured stdout",
            )
        })?;
        let mut reader = BufReader::new(stdout);
        let mut line = String::new();
        reader.read_line(&mut line)?;
        if line.is_empty() {
            return Err(std::io::Error::new(
                std::io::ErrorKind::UnexpectedEof,
                "child closed stdout before writing a handshake line",
            ));
        }
        Ok(line)
    }
}

/// Retrieve the VirusTotal credential from the Rust-owned OS keystore (ADR-008) and, if one is
/// currently stored, place it into `command`'s child-process environment -- and nowhere else.
///
/// # Process-scoped only
/// This calls [`Command::env`], which affects only the environment `command` will spawn its
/// child with; it never touches this (the Rust parent) process's own environment. There is no
/// `std::env::set_var` call anywhere in this module, deliberately -- a global mutation would
/// leak the credential to every future child this process ever spawns, not just this one
/// Python sidecar invocation.
///
/// `store` is taken as `&dyn SecretStore` (not the concrete [`RustSecretStore`]) specifically
/// so this function is directly unit-testable against a fake in-process store, the same reason
/// `keystore_core::SecretStore` is a trait rather than only ever `RustSecretStore` (see that
/// trait's own doc comment) -- this crate's real `cargo test` coverage for the branches below
/// does not require a real OS credential store.
///
/// # Missing credential
/// [`KeystoreError::NotFound`] is the ordinary, expected outcome for a fresh install, or any
/// install where the user has not yet configured a VirusTotal API key -- not an error
/// condition. This preserves the existing startup contract exactly: the sidecar today already
/// starts successfully with no VirusTotal key configured (Python's own
/// `SettingsService`/`ApplicationSettings.virustotal_api_key` already tolerates an empty
/// string, per `app/settings/repository.py`), and this Part 1B-1 addition does not change that
/// -- it simply leaves [`VIRUSTOTAL_ENV_VAR`] unset on the child rather than inventing a fake
/// or empty value to inject.
///
/// # OS keystore unavailable
/// [`KeystoreError::Unavailable`] (the credential store itself could not be reached -- service
/// disabled, permission failure, unsupported backend, etc.) is deliberately treated the same
/// way as "not found": [`VIRUSTOTAL_ENV_VAR`] is left unset and startup continues. This Rust
/// side handoff is additive on top of the sidecar's existing startup contract, not a new hard
/// dependency of it -- a keystore outage must not become "SOC-IQ will not start" merely because
/// this checkpoint added a lookup that did not exist before. A single, secret-free diagnostic
/// line is printed so the condition remains visible (matching this module's existing
/// `eprintln!`-based diagnostics elsewhere, e.g. [`SidecarProcess::start`]'s own crash logging)
/// without being fatal.
///
/// # Invalid input
/// [`KeystoreError::InvalidInput`] can only occur, per `keystore_core::store::validate_name`,
/// for an empty, oversized, or non-identifier `name` -- [`VIRUSTOTAL_SECRET_NAME`] is a fixed,
/// valid, code-level constant, never user input, so this branch is unreachable in practice. It
/// is still handled explicitly (rather than `unreachable!()`/`unwrap()`) and folded into the
/// same non-fatal path as `Unavailable`, on the same reasoning: a defensive branch here should
/// degrade the same way a genuine backend outage does, not panic and crash sidecar startup over
/// what can only ever be an internal, static value.
///
/// # Secret safety
/// Never prints, logs, returns, or otherwise surfaces the credential *value* itself -- only the
/// non-secret fact that a lookup was attempted and which of the three outcomes above occurred.
/// [`KeystoreError`]'s own `Display` impl already guarantees its rendered text never contains a
/// secret value (see that type's doc comment), so the `eprintln!` calls below inherit that
/// guarantee rather than needing their own redaction.
fn apply_secret_handoff(command: &mut Command, store: &dyn SecretStore) {
    match store.get_secret(VIRUSTOTAL_SECRET_NAME) {
        Ok(value) => {
            command.env(VIRUSTOTAL_ENV_VAR, value);
        }
        Err(KeystoreError::NotFound { .. }) => {
            // Expected: no VirusTotal credential configured yet. Leave the child environment
            // exactly as it already was -- no env var, no placeholder value.
        }
        Err(KeystoreError::Unavailable { reason, .. }) => {
            eprintln!(
                "SOC-IQ: could not read the VirusTotal credential from the OS keystore \
                 ({reason}); sidecar will start without it"
            );
        }
        Err(KeystoreError::InvalidInput { .. }) => {
            // Unreachable in practice -- see this function's doc, "Invalid input".
            eprintln!(
                "SOC-IQ: VirusTotal credential lookup rejected the fixed internal secret name; \
                 sidecar will start without it"
            );
        }
    }
}

/// Minimal, dependency-free `GET /health` over loopback TCP. Returns
/// `true` only for a `200`-status HTTP response, matching contract §2's
/// "readiness only via a successful GET /health response". Any I/O
/// error, connection refusal (sidecar still binding its listener), or
/// non-200 status is treated as "not yet healthy" -- the caller's
/// timeout loop decides when to give up; this function only reports
/// one poll's result.
fn health_check_ok(port: u16) -> bool {
    let address = format!("127.0.0.1:{port}");
    let Ok(mut stream) = TcpStream::connect(&address) else {
        return false;
    };
    let _ = stream.set_read_timeout(Some(Duration::from_secs(1)));
    let _ = stream.set_write_timeout(Some(Duration::from_secs(1)));

    let request =
        format!("GET /health HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nConnection: close\r\n\r\n");
    if stream.write_all(request.as_bytes()).is_err() {
        return false;
    }

    let mut response = Vec::new();
    if stream.read_to_end(&mut response).is_err() {
        return false;
    }

    let status_line_bytes = response.split(|&b| b == b'\n').next().unwrap_or(&[]);
    let status_line = String::from_utf8_lossy(status_line_bytes);
    is_http_200_status_line(&status_line)
}

/// Pure parsing helper, split out of [`health_check_ok`] specifically
/// so it is testable without a real socket/process (this crate's tests
/// have no way to spin up a real HTTP server in this environment, but
/// this function's logic can still be verified directly). Only the
/// status line matters -- this adapter does not parse or act on the
/// response body (contract §2: "/health has no database or domain
/// dependency", so a bare 200 status is the complete readiness signal).
fn is_http_200_status_line(status_line: &str) -> bool {
    let trimmed = status_line.trim_end_matches(['\r', '\n']);
    trimmed
        .split_ascii_whitespace()
        .nth(1)
        .map(|code| code == "200")
        .unwrap_or(false)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn recognizes_a_real_200_status_line() {
        assert!(is_http_200_status_line("HTTP/1.1 200 OK"));
    }

    #[test]
    fn rejects_non_200_status_codes() {
        assert!(!is_http_200_status_line("HTTP/1.1 404 Not Found"));
        assert!(!is_http_200_status_line("HTTP/1.1 500 Internal Server Error"));
        assert!(!is_http_200_status_line("HTTP/1.1 503 Service Unavailable"));
    }

    #[test]
    fn rejects_empty_or_malformed_status_line() {
        assert!(!is_http_200_status_line(""));
        assert!(!is_http_200_status_line("garbage"));
        assert!(!is_http_200_status_line("HTTP/1.1"));
    }

    #[test]
    fn tolerates_trailing_carriage_return() {
        assert!(is_http_200_status_line("HTTP/1.1 200 OK\r\n"));
    }

    #[test]
    fn does_not_match_200_appearing_elsewhere_in_the_line() {
        // The status code must be the second whitespace-separated
        // token, not merely present anywhere in the line.
        assert!(!is_http_200_status_line("HTTP/1.1 404 Not Found (was 200 before)"));
    }

    #[test]
    fn default_launch_config_targets_the_documented_entrypoint_invocation() {
        let config = SidecarLaunchConfig::default();
        assert_eq!(config.python_executable, "python");
        // Part 3A-2A: the default (source-checkout/dev) launch must
        // still invoke the entrypoint exactly the same way every
        // pre-existing caller/test already relied on.
        assert_eq!(config.args, vec!["-m", "app.api.entrypoint"]);
    }

    #[test]
    fn production_launch_config_can_omit_module_args() {
        // A packaged config points `python_executable` at the frozen
        // sidecar binary itself and passes it no arguments -- see
        // `SidecarLaunchConfig::args`'s doc comment for why `-m
        // app.api.entrypoint` would be wrong there.
        let config = SidecarLaunchConfig {
            python_executable: "/opt/SOC-IQ/socq-backend".to_string(),
            working_directory: PathBuf::from("/opt/SOC-IQ"),
            args: Vec::new(),
        };
        assert!(config.args.is_empty());
        assert_eq!(config.python_executable, "/opt/SOC-IQ/socq-backend");
    }

    #[test]
    fn new_sidecar_process_starts_not_started() {
        let process = SidecarProcess::new(Supervisor::default());
        assert_eq!(process.state(), LifecycleState::NotStarted);
        assert_eq!(process.port(), None);
    }

    // -------------------------------------------------------------
    // Phase 4O Security Part 1B-1 -- Rust -> Python credential handoff
    // -------------------------------------------------------------
    //
    // A fake, in-process `SecretStore` (never a real OS keystore, and never
    // `keystore_core::RustSecretStore`) so `apply_secret_handoff`'s three branches are
    // deterministically testable without any platform credential-store dependency. Only
    // `get_secret` is exercised by `apply_secret_handoff`; the other three trait methods are
    // never called on this path and simply panic if they ever are, so a test would fail loudly
    // instead of silently passing on the wrong assumption.
    struct FakeStore {
        result: KeystoreError,
        value: Option<String>,
    }

    impl FakeStore {
        fn found(value: &str) -> Self {
            // `result` is unused on the `Ok` path; give it an inert placeholder so the struct
            // does not need an `Option<KeystoreError>` just for this one variant.
            Self {
                result: KeystoreError::NotFound {
                    name: "unused".to_string(),
                },
                value: Some(value.to_string()),
            }
        }

        fn not_found() -> Self {
            Self {
                result: KeystoreError::NotFound {
                    name: VIRUSTOTAL_SECRET_NAME.to_string(),
                },
                value: None,
            }
        }

        fn unavailable(reason: &str) -> Self {
            Self {
                result: KeystoreError::Unavailable {
                    name: VIRUSTOTAL_SECRET_NAME.to_string(),
                    reason: reason.to_string(),
                },
                value: None,
            }
        }
    }

    impl SecretStore for FakeStore {
        fn set_secret(&self, _name: &str, _value: &str) -> Result<(), KeystoreError> {
            panic!("apply_secret_handoff must never call set_secret");
        }

        fn get_secret(&self, name: &str) -> Result<String, KeystoreError> {
            assert_eq!(
                name, VIRUSTOTAL_SECRET_NAME,
                "apply_secret_handoff must look up the exact VirusTotal secret name"
            );
            match &self.value {
                Some(v) => Ok(v.clone()),
                None => Err(clone_keystore_error(&self.result)),
            }
        }

        fn delete_secret(&self, _name: &str) -> Result<(), KeystoreError> {
            panic!("apply_secret_handoff must never call delete_secret");
        }

        fn has_secret(&self, _name: &str) -> Result<bool, KeystoreError> {
            panic!("apply_secret_handoff must never call has_secret");
        }
    }

    /// `KeystoreError` is intentionally `Debug`-only (not `Clone`) in `keystore_core` -- it is
    /// constructed fresh at each real call site and never needs to be duplicated in production
    /// code. This test-only helper exists solely so [`FakeStore`] can hold one constructed
    /// value and still hand it out from a `&self` method without cloning `keystore_core`'s
    /// type.
    fn clone_keystore_error(error: &KeystoreError) -> KeystoreError {
        match error {
            KeystoreError::NotFound { name } => KeystoreError::NotFound { name: name.clone() },
            KeystoreError::Unavailable { name, reason } => KeystoreError::Unavailable {
                name: name.clone(),
                reason: reason.clone(),
            },
            KeystoreError::InvalidInput { reason } => {
                KeystoreError::InvalidInput { reason: reason.clone() }
            }
        }
    }

    /// Reads back the value `Command::env` set for a given key, using
    /// `Command::get_envs` (stable, std-only introspection -- no need to actually spawn the
    /// child to observe what environment it was configured with).
    fn command_env(command: &Command, key: &str) -> Option<String> {
        command.get_envs().find_map(|(k, v)| {
            if k.to_str() == Some(key) {
                v.and_then(|v| v.to_str().map(|s| s.to_string()))
            } else {
                None
            }
        })
    }

    #[test]
    fn credential_found_is_placed_into_the_child_environment() {
        let mut command = Command::new("python");
        let store = FakeStore::found("s3cr3t-vt-key");

        apply_secret_handoff(&mut command, &store);

        assert_eq!(
            command_env(&command, VIRUSTOTAL_ENV_VAR),
            Some("s3cr3t-vt-key".to_string())
        );
    }

    #[test]
    fn missing_credential_leaves_the_env_var_unset_and_does_not_panic() {
        let mut command = Command::new("python");
        let store = FakeStore::not_found();

        apply_secret_handoff(&mut command, &store);

        assert_eq!(command_env(&command, VIRUSTOTAL_ENV_VAR), None);
    }

    #[test]
    fn unavailable_backend_leaves_the_env_var_unset_and_does_not_panic() {
        let mut command = Command::new("python");
        let store = FakeStore::unavailable("simulated backend outage");

        apply_secret_handoff(&mut command, &store);

        assert_eq!(command_env(&command, VIRUSTOTAL_ENV_VAR), None);
    }

    #[test]
    fn secret_handoff_never_mutates_the_parent_processs_own_environment() {
        // Guards against a regression back to `std::env::set_var` (the module doc's explicit
        // "process-scoped only" requirement): even after a successful handoff, this process's
        // own environment must remain untouched -- only `command`'s child-to-be is affected.
        std::env::remove_var(VIRUSTOTAL_ENV_VAR);
        let mut command = Command::new("python");
        let store = FakeStore::found("must-not-leak-to-parent-env");

        apply_secret_handoff(&mut command, &store);

        assert!(
            std::env::var(VIRUSTOTAL_ENV_VAR).is_err(),
            "apply_secret_handoff must never set the parent process's own environment"
        );
        // The child-to-be's environment, in contrast, *does* have it -- proving this is a
        // scoping difference, not simply "nothing was set anywhere".
        assert_eq!(
            command_env(&command, VIRUSTOTAL_ENV_VAR),
            Some("must-not-leak-to-parent-env".to_string())
        );
    }

    #[test]
    fn secret_value_never_appears_in_a_debug_render_of_the_keystore_error_path() {
        // `Unavailable`'s `reason` text is real platform-error text, not the secret -- but this
        // asserts the specific secret value used elsewhere in this module's tests still cannot
        // appear via this path, matching `keystore_core::KeystoreError`'s own "never carries a
        // secret value" guarantee that this module inherits rather than re-implements.
        let mut command = Command::new("python");
        let store = FakeStore::unavailable("simulated backend outage");

        apply_secret_handoff(&mut command, &store);

        let rendered = format!("{command:?}");
        assert!(!rendered.contains("s3cr3t-vt-key"));
        assert!(!rendered.contains("must-not-leak-to-parent-env"));
    }
}
