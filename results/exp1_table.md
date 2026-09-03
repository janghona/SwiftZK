**Table 1a — Wallet-side verification (x86), mean ± 95% CI.**

| Scheme | Kind | Depth | Verify (ms) | Verify Peak Mem (MiB) | Proof (KiB) | VK (KiB) |
|---|---|---:|---:|---:|---:|---:|
| nova | folding | 2 | 67.308 ± 15.626 | 39.34 | 9.64 | 10453.20 |
| nova | folding | 4 | 165.544 ± 1.664 | 39.39 | 9.64 | 10453.20 |
| nova | folding | 8 | 164.610 ± 2.447 | 38.91 | 9.64 | 10453.20 |
| nova | folding | 16 | 162.945 ± 1.343 | 39.38 | 9.64 | 10453.20 |
| nova | folding | 32 | 164.859 ± 1.749 | 38.91 | 9.64 | 10453.20 |
| nova | folding | 64 | 162.984 ± 0.872 | 39.24 | 9.64 | 10453.20 |
| plonky2 | recursive | 2 | 4.976 ± 0.138 | 0.47 | 124.23 | 1.85 |
| plonky2 | recursive | 4 | 4.856 ± 0.044 | 0.47 | 124.23 | 1.85 |
| plonky2 | recursive | 8 | 4.877 ± 0.050 | 0.47 | 124.23 | 1.85 |
| plonky2 | recursive | 16 | 4.845 ± 0.041 | 0.47 | 124.23 | 1.85 |
| plonky2 | recursive | 32 | 4.854 ± 0.038 | 0.47 | 124.23 | 1.85 |
| plonky2 | recursive | 64 | 4.820 ± 0.020 | 0.47 | 124.23 | 1.85 |

**Table 1b — Prover-side cost (x86), mean ± 95% CI.**

| Scheme | Kind | Depth | Prove (ms) | Prove Peak Mem (MiB) |
|---|---|---:|---:|---:|
| nova | folding | 2 | 6716.5 ± 16.2 | 131.0 |
| nova | folding | 4 | 7233.9 ± 17.2 | 130.9 |
| nova | folding | 8 | 8167.7 ± 31.5 | 131.1 |
| nova | folding | 16 | 9861.2 ± 105.3 | 130.9 |
| nova | folding | 32 | 13201.0 ± 35.4 | 131.0 |
| nova | folding | 64 | 20296.9 ± 283.2 | 130.5 |
| plonky2 | recursive | 2 | 900.3 ± 312.0 | 116.6 |
| plonky2 | recursive | 4 | 3962.6 ± 115.1 | 191.9 |
| plonky2 | recursive | 8 | 9110.3 ± 110.2 | 342.3 |
| plonky2 | recursive | 16 | 19393.8 ± 158.8 | 643.2 |
| plonky2 | recursive | 32 | 41130.0 ± 370.7 | 1245.0 |
| plonky2 | recursive | 64 | 137844.5 ± 2181.9 | 2448.6 |
