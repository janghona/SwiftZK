//! Experiment 1 driver (x86 native, release). Produces:
//!   * a proving-metrics CSV (proving time, peak memory, proof size per run)
//!   * one exported proof file per depth: `<proof-dir>/<scheme>_d<depth>.bin`
//!     used by Experiment 2 (EVM) and Experiment 3 (ARM verification).
//!
//! Run one scheme per invocation, e.g.:
//!   cargo run --release -p zkbench-prover --features plonky2 -- \
//!     --scheme plonky2 --runs 20 --warmup 3 \
//!     --out-csv results/raw/prove_plonky2.csv --proof-dir proofs

use anyhow::{bail, Result};
use clap::Parser;
use std::fs;
use std::path::PathBuf;
use zkbench_core::bench::{prove_runs, ProveArtifacts};
use zkbench_core::workload::AggWorkload;
use zkbench_core::DEPTHS;

#[global_allocator]
static GLOBAL: peak_alloc::PeakAlloc = zkbench_core::metrics::ALLOC;

#[derive(Parser)]
#[command(about = "SwiftZK-Wallet Experiment 1: proving benchmark")]
struct Args {
    /// halo2 | plonky2 | nova | supernova | noop (must also be a build feature)
    #[arg(long)]
    scheme: String,
    /// Comma-separated depths; default is the full sweep 2,4,8,16,32,64
    #[arg(long, value_delimiter = ',')]
    depths: Option<Vec<u32>>,
    #[arg(long, default_value_t = 0xA11CE)]
    seed: u64,
    #[arg(long, default_value_t = 3)]
    warmup: u32,
    #[arg(long, default_value_t = 20)]
    runs: u32,
    #[arg(long)]
    out_csv: PathBuf,
    #[arg(long)]
    proof_dir: PathBuf,
}

fn main() -> Result<()> {
    let args = Args::parse();
    let depths = args.depths.unwrap_or_else(|| DEPTHS.to_vec());
    fs::create_dir_all(&args.proof_dir)?;
    if let Some(p) = args.out_csv.parent() {
        fs::create_dir_all(p)?;
    }
    let mut wtr = csv::Writer::from_path(&args.out_csv)?;

    eprintln!(
        "scheme={} depths={:?} runs={} warmup={}",
        args.scheme, depths, args.runs, args.warmup
    );

    for &depth in &depths {
        let w = AggWorkload::new(depth, args.seed);
        let art = dispatch(&args.scheme, &w, args.warmup, args.runs, &mut wtr)?;
        let pf = args.proof_dir.join(format!("{}_d{}.bin", args.scheme, depth));
        let vk = args.proof_dir.join(format!("{}_d{}.vk", args.scheme, depth));
        fs::write(&pf, &art.proof)?;
        fs::write(&vk, &art.vk)?;
        eprintln!(
            "  depth {:>2}: proof {} B -> {} ; vk {} B -> {}",
            depth, art.proof.len(), pf.display(), art.vk.len(), vk.display()
        );
    }
    eprintln!("wrote {}", args.out_csv.display());
    Ok(())
}

// Some params are unused when no scheme feature is enabled (only the wildcard
// arm compiles); they are all used once any `--features <scheme>` is set.
#[allow(unused_variables)]
fn dispatch(
    scheme: &str,
    w: &AggWorkload,
    warmup: u32,
    runs: u32,
    wtr: &mut csv::Writer<fs::File>,
) -> Result<ProveArtifacts> {
    use zkbench_core::adapters;
    match scheme {
        #[cfg(feature = "halo2")]
        "halo2" => prove_runs::<adapters::halo2::Halo2Agg, _>(w, warmup, runs, wtr),
        #[cfg(feature = "plonky2")]
        "plonky2" => prove_runs::<adapters::plonky2::Plonky2Agg, _>(w, warmup, runs, wtr),
        #[cfg(feature = "nova")]
        "nova" => prove_runs::<adapters::nova::NovaAgg, _>(w, warmup, runs, wtr),
        #[cfg(feature = "supernova")]
        "supernova" => prove_runs::<adapters::supernova::SuperNovaAgg, _>(w, warmup, runs, wtr),
        #[cfg(feature = "noop")]
        "noop" => prove_runs::<adapters::noop::NoopAgg, _>(w, warmup, runs, wtr),
        other => bail!(
            "scheme '{other}' not compiled in. Rebuild with `--features {other}`. \
             Available: {:?}",
            adapters::available()
        ),
    }
}
