//! Measurement primitives. Two metrics need care:
//!
//! * **Time** — monotonic `Instant`, wall-clock of the measured call only.
//!   Callers do warmup iterations first and report mean/variance over N runs.
//! * **Peak memory** — a tracking global allocator (`peak_alloc`) gives a
//!   deterministic, cross-platform peak *heap* figure, which is the fair basis
//!   for comparing schemes. On Linux (Exp 3 ARM host) we ALSO record process
//!   peak RSS (`VmHWM`) as an OS-level cross-check.

use peak_alloc::PeakAlloc;

/// Install as the global allocator in each binary:
/// `#[global_allocator] static GLOBAL: peak_alloc::PeakAlloc = zkbench_core::metrics::ALLOC;`
pub static ALLOC: PeakAlloc = PeakAlloc;

/// Reset the peak-heap counter to the current usage. Call immediately before a
/// measured section.
pub fn reset_peak_mem() {
    ALLOC.reset_peak_usage();
}

/// Peak heap bytes observed since the last `reset_peak_mem`.
pub fn peak_mem_bytes() -> u64 {
    ALLOC.peak_usage() as u64
}

/// Time a closure, returning `(result, elapsed_ms)`.
pub fn time_ms<T>(f: impl FnOnce() -> T) -> (T, f64) {
    let t0 = std::time::Instant::now();
    let out = f();
    (out, t0.elapsed().as_secs_f64() * 1000.0)
}

/// Linux process peak RSS in bytes from `/proc/self/status` (`VmHWM`).
/// Returns `None` off Linux or if the field is unavailable.
pub fn proc_peak_rss_bytes() -> Option<u64> {
    #[cfg(target_os = "linux")]
    {
        let status = std::fs::read_to_string("/proc/self/status").ok()?;
        for line in status.lines() {
            if let Some(rest) = line.strip_prefix("VmHWM:") {
                let kb: u64 = rest.trim().split_whitespace().next()?.parse().ok()?;
                return Some(kb * 1024);
            }
        }
        None
    }
    #[cfg(not(target_os = "linux"))]
    {
        None
    }
}

/// Simple summary statistics for the CLI to print a human-readable line
/// (the authoritative stats are computed in Python from the CSV).
pub fn mean_std(xs: &[f64]) -> (f64, f64) {
    let n = xs.len() as f64;
    if n == 0.0 {
        return (0.0, 0.0);
    }
    let mean = xs.iter().sum::<f64>() / n;
    let var = xs.iter().map(|x| (x - mean).powi(2)).sum::<f64>() / n;
    (mean, var.sqrt())
}
