//! Verification driver. Same binary for:
//!   * Experiment 1 verification rows  ->  --host x86  (on the dev machine)
//!   * Experiment 3 (mobile proxy)     ->  --host arm  (on the Ampere A1 VM)
//!
//! It NEVER proves. It loads `<proof-dir>/<scheme>_d<depth>.bin` (produced by
//! zkbench-prover), verifies it `warmup + runs` times, and writes a CSV of
//! verification time, peak memory, and proof size.
//!
//!   cargo run --release -p zkbench-verifier --features nova -- \
//!     --scheme nova --host arm --runs 100 --warmup 10 \
//!     --depths 8,16 --out-csv results/raw/verify_arm_nova.csv --proof-dir proofs

use anyhow::{bail, Result};
use clap::Parser;
use std::fs;
use std::path::PathBuf;
use zkbench_core::bench::verify_runs;
use zkbench_core::workload::AggWorkload;
use zkbench_core::DEPTHS;

#[global_allocator]
static GLOBAL: peak_alloc::PeakAlloc = zkbench_core::metrics::ALLOC;

#[derive(Parser)]
#[command(about = "SwiftZK-Wallet verification benchmark (Exp 1 x86 / Exp 3 arm)")]
struct Args {
    #[arg(long)]
    scheme: String,
    #[arg(long, value_delimiter = ',')]
    depths: Option<Vec<u32>>,
    #[arg(long, default_value_t = 0xA11CE)]
    seed: u64,
    #[arg(long, default_value_t = 10)]
    warmup: u32,
    #[arg(long, default_value_t = 100)]
    runs: u32,
    /// "x86" (Exp 1) or "arm" (Exp 3). Free-form label stored in the CSV.
    #[arg(long, default_value = "x86")]
    host: String,
    #[arg(long)]
    out_csv: PathBuf,
    #[arg(long)]
    proof_dir: PathBuf,
}

fn main() -> Result<()> {
    let args = Args::parse();
    let depths = args.depths.unwrap_or_else(|| DEPTHS.to_vec());
    if let Some(p) = args.out_csv.parent() {
        fs::create_dir_all(p)?;
    }
    let mut wtr = csv::Writer::from_path(&args.out_csv)?;

    eprintln!(
        "scheme={} host={} depths={:?} runs={} warmup={}",
        args.scheme, args.host, depths, args.runs, args.warmup
    );

    for &depth in &depths {
        let w = AggWorkload::new(depth, args.seed);
        let pf = args.proof_dir.join(format!("{}_d{}.bin", args.scheme, depth));
        let vkf = args.proof_dir.join(format!("{}_d{}.vk", args.scheme, depth));
        let proof = fs::read(&pf)
            .map_err(|e| anyhow::anyhow!("cannot read {}: {e}", pf.display()))?;
        let vk = fs::read(&vkf)
            .map_err(|e| anyhow::anyhow!("cannot read {}: {e}", vkf.display()))?;
        dispatch(&args.scheme, &w, &proof, &vk, &args.host, args.warmup, args.runs, &mut wtr)?;
        eprintln!("  depth {:>2}: verified {} B proof x {} runs", depth, proof.len(), args.runs);
    }
    eprintln!("wrote {}", args.out_csv.display());
    Ok(())
}

// Params are unused only in the no-feature build (wildcard arm); used with any
// `--features <scheme>`.
#[allow(clippy::too_many_arguments, unused_variables)]
fn dispatch(
    scheme: &str,
    w: &AggWorkload,
    proof: &[u8],
    vk: &[u8],
    host: &str,
    warmup: u32,
    runs: u32,
    wtr: &mut csv::Writer<fs::File>,
) -> Result<()> {
    use zkbench_core::adapters;
    match scheme {
        #[cfg(feature = "halo2")]
        "halo2" => verify_runs::<adapters::halo2::Halo2Agg, _>(w, proof, vk, host, warmup, runs, wtr),
        #[cfg(feature = "plonky2")]
        "plonky2" => {
            verify_runs::<adapters::plonky2::Plonky2Agg, _>(w, proof, vk, host, warmup, runs, wtr)
        }
        #[cfg(feature = "nova")]
        "nova" => verify_runs::<adapters::nova::NovaAgg, _>(w, proof, vk, host, warmup, runs, wtr),
        #[cfg(feature = "supernova")]
        "supernova" => {
            verify_runs::<adapters::supernova::SuperNovaAgg, _>(w, proof, vk, host, warmup, runs, wtr)
        }
        #[cfg(feature = "noop")]
        "noop" => verify_runs::<adapters::noop::NoopAgg, _>(w, proof, vk, host, warmup, runs, wtr),
        other => bail!(
            "scheme '{other}' not compiled in. Rebuild with `--features {other}`. \
             Available: {:?}",
            adapters::available()
        ),
    }
}
