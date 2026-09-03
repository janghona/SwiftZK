//! One adapter per scheme under comparison. Each is gated by a Cargo feature so
//! the workspace builds before the heavy crypto crates are added. Integration
//! notes and crate choices: see `../../../docs/adapters.md`.
//!
//! Comparison set (fixed by the study design — do not add others):
//!   Recursive: Halo2, Plonky2
//!   Folding:   Nova, SuperNova

#[cfg(feature = "halo2")]
pub mod halo2;
#[cfg(feature = "plonky2")]
pub mod plonky2;
#[cfg(feature = "nova")]
pub mod nova;
#[cfg(feature = "supernova")]
pub mod supernova;
#[cfg(feature = "noop")]
pub mod noop;

/// Names compiled into this build.
pub fn available() -> Vec<&'static str> {
    #[allow(unused_mut)]
    let mut v = Vec::new();
    #[cfg(feature = "halo2")]
    v.push("halo2");
    #[cfg(feature = "plonky2")]
    v.push("plonky2");
    #[cfg(feature = "nova")]
    v.push("nova");
    #[cfg(feature = "supernova")]
    v.push("supernova");
    #[cfg(feature = "noop")]
    v.push("noop");
    v
}
