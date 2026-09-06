//! Timeout configuration.
//!
//! A small, explicit abstraction for the two lifecycle timeouts the
//! contract requires be bounded (§2 "neither Phase 2A implementation
//! may block indefinitely on either step", §4 shutdown escalation).
//! Part 1 does not implement any sleep-based waiting itself — this
//! type only carries the configured durations for a future caller
//! (Part 2's real handshake/health-poll/shutdown loop) to enforce.

use std::time::Duration;

/// Bounded timeouts for the two lifecycle phases the contract names:
/// startup (handshake + health-poll, contract §2) and shutdown
/// (contract §4).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct TimeoutConfig {
    pub startup: Duration,
    pub shutdown: Duration,
}

impl TimeoutConfig {
    pub fn new(startup: Duration, shutdown: Duration) -> Self {
        Self { startup, shutdown }
    }
}

impl Default for TimeoutConfig {
    /// Part 1's default values. The contract requires both timeouts to
    /// be bounded but does not mandate specific numbers (task brief §7:
    /// "Use the contract's values if specified" — none are), so these
    /// are a documented starting point, not a contractual constant; a
    /// later phase's real handshake/health-poll implementation may
    /// override them via [`TimeoutConfig::new`].
    fn default() -> Self {
        Self {
            startup: Duration::from_secs(10),
            shutdown: Duration::from_secs(5),
        }
    }
}
