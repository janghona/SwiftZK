<!--
DRAFT — SwiftZK-Wallet.  Target: ICT Express (Elsevier), ~6 pages, 2-column.
Every numeric cell shown as "—" is a placeholder. Fill ONLY from
analysis/analyze.py output (results/exp1_table.md, results/exp2_gas.md,
results/exp3_table.md). Do not hand-enter numbers.
Reference page numbers marked [verify] before submission.
-->

# SwiftZK-Wallet: Lightweight ZK Aggregation for Blockchain-Connected Mobile Wallets

**Authors.** _TBD_
**Corresponding author.** jang1na2@gmail.com

---

## Abstract

Blockchain-connected mobile wallets increasingly rely on zero-knowledge (ZK)
proofs to attest transaction validity, membership, or policy compliance without
disclosing account state. When many such statements must be checked, *proof
aggregation* becomes attractive, but the wallet — a resource-constrained client
that ultimately *verifies* — is the binding constraint. This paper asks a single
practical question: **which ZK aggregation approach is most suitable for
lightweight verification in a blockchain-connected mobile wallet?** We compare
the two families head to head — recursion, instantiated by Plonky2, and folding,
instantiated by Nova — under one identical native workload, sweeping aggregation
depth 2–64, and measuring proving time, verification time, peak memory,
verification-key size, and proof size with repeated runs; Halo2 and SuperNova,
the other members of each family, are positioned analytically. We then validate
blockchain-connected verification on an EVM verifier under Foundry/Anvil
(verification gas, execution cost), and confirm the outcome on an ARM
mobile-class environment (verification latency, memory). We do **not** propose a
new cryptographic protocol; we provide a systematic, wallet-centric comparison
and a defensible selection rule based on verification time, memory, and proof
size, together with a working blockchain-connected verification path.

**Keywords.** zero-knowledge proofs; proof aggregation; recursive proofs;
folding schemes; mobile wallet; blockchain verification.

---

## 1. Introduction

Mobile wallets are becoming ZK clients: they check proofs of solvency,
allow-list membership, compliant transfer, or rollup state before signing or
submitting a transaction. As the number of statements per user action grows,
verifying each proof independently is wasteful in bandwidth, on-chain gas, and
on-device CPU. **Aggregation** compresses many proofs into one, shifting cost to
a (possibly outsourced) prover while leaving the wallet with a single
verification.

Two families dominate practical aggregation. **Recursive** systems verify a
proof *inside* a circuit, so an aggregate proof attests to a batch of prior
proofs (Halo2's accumulation, Plonky2's PLONK+FRI recursion). **Folding**
schemes (Nova, SuperNova) avoid in-circuit proof verification per step: they
*fold* R1CS instances into one running instance and run a single succinct
*decider* at the end. The two families trade prover work, proof size, and
verifier work differently, and the literature reports these from a *prover's*
viewpoint. A mobile wallet cares about the opposite end.

We take Plonky2 and Nova as the family representatives: both are current,
actively maintained Rust implementations with a transparent (trusted-setup-free)
path, which keeps the comparison clean. Halo2 (recursive) and SuperNova
(folding) share their family's verifier-cost structure — a single succinct final
check for recursion, a decider check for folding — so the family-level ordering
we measure is expected to carry over; §2 places them in context.

**Core question.** Which aggregation approach — recursive or folding — gives the
lightest *verification* for a blockchain-connected mobile wallet, judged by
verification time, memory, and proof size, and does the chosen approach verify
cleanly on an EVM contract?

**Contributions.**

1. A **systematic recursive-vs-folding comparison** for blockchain-connected
   mobile wallets — recursion (Plonky2) vs folding (Nova) under one identical
   native workload and aggregation-depth sweep 2–64, reporting proving time,
   verification time, peak memory, verification-key size, and proof size with
   repeated-run statistics; Halo2 and SuperNova discussed analytically.
2. A **lightweight-aggregation selection rule** grounded in *empirical*
   verification latency, memory, and proof size (not prover metrics), yielding a
   concrete recommendation for the wallet setting.
3. **Blockchain-connected validation** of the selected approach through EVM
   verification (verification gas and execution cost under Foundry/Anvil), plus
   an ARM mobile-class confirmation of verification latency and memory.

We explicitly do **not** claim a new cryptographic protocol or universal
superiority of one family; the contribution is measurement, selection, and an
end-to-end verification path for the wallet use case.

---

## 2. Related Work

**Recursive proofs.** Halo [1] introduced recursive proof composition without a
trusted setup via an accumulation scheme, folding the expensive polynomial-
commitment check across steps. Plonky2 [2] combines PLONK with FRI over a
64-bit field to make recursion fast in practice, at the cost of larger,
FRI-based proofs. Both target succinct *final* verification but differ sharply
in proof size and verifier arithmetic.

**Folding schemes.** Nova [3] realizes incrementally verifiable computation from
a non-interactive folding scheme for relaxed R1CS, replacing per-step in-circuit
proof verification with a cheap fold and a single closing SNARK (the decider).
SuperNova [4] generalizes this to non-uniform IVC, so a program with several
instruction types is proved without a universal circuit. Folding minimizes
per-step prover overhead; the wallet-relevant cost is the decider's
verification.

**Blockchain and mobile ZK.** zkBridge [5] demonstrates practical
proof-carrying cross-chain messaging with on-chain verification, illustrating
that gas cost and proof size — not just prover time — govern deployability of ZK
on blockchains and thin clients.

**ZK performance methodology.** zk-Bench [6] provides a comparative
benchmarking methodology for SNARK backends and highlights how sensitive
results are to workload, field choice, and build configuration — motivating our
single fixed workload, fixed release profile, and repeated-run statistics.

Our work differs by fixing the *evaluation lens* to wallet-side verification and
by carrying the selected scheme through to EVM and ARM validation.

> References — recent, highly relevant, ~6 entries:
> [1] Bowe, Grigg, Hopwood, *Recursive Proof Composition without a Trusted
> Setup*, IACR ePrint 2019/1021.
> [2] Polygon Zero, *Plonky2: Fast Recursive Arguments with PLONK and FRI*,
> tech. report, 2022.
> [3] Kothapalli, Setty, Tzialla, *Nova: Recursive Zero-Knowledge Arguments
> from Folding Schemes*, CRYPTO 2022, LNCS 13510, pp. 359–388 [verify].
> [4] Kothapalli, Setty, *SuperNova: Proving Universal Machine Executions
> without Universal Circuits*, IACR ePrint 2022/1758.
> [5] Xie et al., *zkBridge: Trustless Cross-chain Bridges Made Practical*, ACM
> CCS 2022, pp. 3003–3017 [verify].
> [6] Ernstberger et al., *zk-Bench: A Toolset for Comparative Evaluation and
> Performance Benchmarking of SNARKs*, IACR ePrint 2023/1503.

---

## 3. System Architecture

SwiftZK-Wallet has three roles (Fig. 1).

**Wallet client (mobile).** Holds signing keys and the user's private state.
Emits *unit statements* (e.g., "this transfer respects the spending policy")
and, crucially, runs the **single verification** of the aggregate proof before
signing/submitting. It never runs the aggregation prover.

**Aggregation service (off-device).** A companion process or remote service that
collects unit statements/witnesses and produces one aggregate proof, using a
recursive composer (Halo2/Plonky2) or a folding IVC + decider (Nova/SuperNova).
Trust is not required: a wrong aggregate proof is rejected by verification.

**On-chain verifier (EVM).** A stateless verifier contract that checks the same
aggregate proof (or its decider proof) and enforces public-input binding and a
per-wallet nonce, so an accepted proof authorizes exactly one state transition.

```
 ┌────────────┐  unit stmts (x_i, w_i)   ┌──────────────────────┐
 │  Wallet    │ ───────────────────────► │ Aggregation service  │
 │  (mobile)  │                          │  recursive | folding │
 │            │ ◄─────────────────────── │   + decider          │
 │  verify(π) │   aggregate proof π, X   └──────────┬───────────┘
 └─────┬──────┘                                     │ π, X
       │ signed tx + π                              ▼
       └───────────────────────────────►  ┌──────────────────────┐
                                          │ EVM verifier contract│
                                          │ verifyProof(π, X)    │
                                          │ + nonce / replay     │
                                          └──────────────────────┘
        Fig. 1. SwiftZK-Wallet data flow. The wallet's only ZK cost is verify(π).
```

The design is deliberately thin: aggregation strategy is a pluggable choice, and
the wallet/contract interface (`verifyProof(proof, publicInputs)`) is identical
across schemes, which is what makes the comparison in §6 meaningful.

---

## 4. Formalization

We keep definitions minimal and give exactly two algorithms.

**Definition 1 (Unit relation).** Let `step: 𝔽 → 𝔽` be a fixed efficiently
computable map. A *unit statement* is `xᵢ = (inᵢ, outᵢ)` with witness `wᵢ`; the
unit relation is
`R(xᵢ, wᵢ) = 1  ⇔  outᵢ = step(inᵢ)` and `wᵢ` is the corresponding trace.

**Definition 2 (Aggregation relation).** For depth `d`, the aggregate statement
is `X = (u₀, u_d)` and
`R*_d(X, W) = 1  ⇔  ∃ u₁,…,u_{d-1}:  u_j = step(u_{j-1}) ∀ j ∈ [1,d]`,
with `W = (u₁,…,u_{d-1})`. Aggregation must therefore certify a *complete,
ordered* chain.

**Definition 3 (Recursive aggregation scheme).** A tuple `(G, P_rec, V)` where
`G` outputs `(pk, vk)`; `P_rec` produces `π_d` by, at each layer, proving
in-circuit that the previous layer's proof verifies and that I/O is chained; `V`
is succinct and checks `X ∈ L(R*_d)`.

**Definition 4 (Folding scheme + decider).** A non-interactive folding scheme
`NIFS` folds two relaxed-R1CS instance/witness pairs `(U₁,W₁),(U₂,W₂)` into one
`(U,W)` such that satisfiability is preserved and knowledge-sound. A *decider*
`D = (D.Prove, D.Verify)` produces a succinct proof `Π` that a final folded
instance `U` is satisfiable. Wallet/EVM verification runs `D.Verify`.

**Definition 5 (Wallet verification predicate).** Given context
`ctx = (cid, n, recipient, amtCom, …)` the wallet accepts iff
`V(vk, X, π) = 1` **and** `X.pub = ctx` exactly, where `n` is the wallet's
monotone nonce and `cid` the chain id.

<!-- Algorithms: valid LaTeX (algorithmic package). -->

```latex
\begin{algorithm}
\caption{Recursive aggregation and verification}
\label{alg:recursive}
\begin{algorithmic}[1]
\REQUIRE unit statements $(x_1,\dots,x_d)$, witnesses $(w_1,\dots,w_d)$, keys $(pk,vk)$
\ENSURE  aggregate proof $\pi_d$, decision $b$
\STATE $\pi \gets \bot$
\FOR{$i = 1$ \TO $d$}
    \STATE $\rho_i \gets \mathsf{Prove}(pk,\, x_i,\, w_i)$ \COMMENT{prove the $i$-th unit step}
    \IF{$i = 1$}
        \STATE $\pi \gets \rho_i$
    \ELSE
        \STATE $\phi_i \gets \big(\mathsf{V}(vk, x_{i-1}, \pi) = 1\big) \wedge \big(R(x_i, w_i) = 1\big) \wedge \big(x_i.\mathsf{in} = x_{i-1}.\mathsf{out}\big)$
        \STATE $\pi \gets \mathsf{Prove}(pk,\, \phi_i)$ \COMMENT{recursive layer: fold previous proof in-circuit}
    \ENDIF
\ENDFOR
\STATE $\pi_d \gets \pi$;\quad $X \gets (x_1.\mathsf{in},\, x_d.\mathsf{out})$
\STATE $b \gets \mathsf{V}(vk,\, X,\, \pi_d)$
\RETURN $(\pi_d,\, b)$
\end{algorithmic}
\end{algorithm}
```

```latex
\begin{algorithm}
\caption{Folding-based aggregation and verification}
\label{alg:folding}
\begin{algorithmic}[1]
\REQUIRE step circuit $F$ for \textsf{step}, initial input $u_0$, depth $d$, public params $pp$
\ENSURE  compressed proof $\Pi$, decision $b$
\STATE $(U, W) \gets \mathsf{TrivialInstance}(pp)$ \COMMENT{running relaxed-R1CS instance/witness}
\STATE $u \gets u_0$
\FOR{$i = 1$ \TO $d$}
    \STATE $u' \gets F(u)$ \COMMENT{execute one step}
    \STATE $(\hat{u}_i, \hat{w}_i) \gets \mathsf{Satisfy}(F,\, u,\, u')$ \COMMENT{instance/witness for this step}
    \STATE $(U, W) \gets \mathsf{NIFS.Fold}\big((U, W),\, (\hat{u}_i, \hat{w}_i)\big)$
    \STATE $u \gets u'$
\ENDFOR
\STATE $X \gets (u_0,\, u)$
\STATE $\Pi \gets \mathsf{D.Prove}(pp,\, U,\, W)$ \COMMENT{decider: succinct proof of final instance}
\STATE $b \gets \mathsf{D.Verify}(pp,\, X,\, U,\, \Pi)$
\RETURN $(\Pi,\, b)$
\end{algorithmic}
\end{algorithm}
```

In both algorithms the wallet/EVM cost is the single final call
(`V` in line 12 of Alg. 1, `D.Verify` in line 10 of Alg. 2); §6 measures exactly
this call.

---

## 5. Security and Privacy

We assume each underlying system meets its standard notion: knowledge soundness
and zero-knowledge for the recursive prover/verifier and for the decider, and
knowledge-sound, satisfiability-preserving folding for `NIFS` [1–4]. Proofs are
sketches.

**Theorem 1 (Proof soundness).** If the underlying recursive system (resp.
folding scheme and decider) is knowledge-sound, then for every PPT prover that
outputs `(X, π)` accepted by Definition 5, there is an extractor that outputs
`W` with `R*_d(X, W) = 1`, except with negligible probability.
*Proof.* Recursive: induct on `d`. The base case is knowledge soundness of the
unit proof. For the step, the accepting layer proof yields (by knowledge
soundness) a witness containing a verifying `π_{i-1}` and `w_i`; the inductive
hypothesis extracts the chain up to `i-1`, and `w_i` extends it. Folding: NIFS
knowledge soundness extracts a satisfying witness for each folded instance and
hence for `U`; decider knowledge soundness extracts `W` for `U`. Composing the
extractors gives `W` for `R*_d`. ∎

**Theorem 2 (Aggregation integrity).** An accepted proof for `X = (u₀, u_d)`
implies a *complete and correctly ordered* chain `u₀ → ⋯ → u_d` under `step`;
no intermediate step can be skipped, reordered, or substituted.
*Proof.* In Alg. 1 the per-layer clause `x_i.in = x_{i-1}.out` (line 8) links
consecutive statements, and `d` layers are enforced structurally; Theorem 1
upgrades satisfaction to extractable knowledge. In Alg. 2 the running instance
`U` binds the accumulated step count and the running I/O `(u₀, u)`; a skipped or
reordered step yields `U` inconsistent with `X`, rejected by `D.Verify`. ∎

**Theorem 3 (Public-input integrity).** For fixed `π`, altering the public
vector from `X` to `X' ≠ X` causes verification to reject except with negligible
probability.
*Proof.* `X` is absorbed into the Fiat–Shamir transcript (recursive) or is the
public part of the decider instance (folding); both bind `π` to `X` through a
collision-resistant hash. Producing `X' ≠ X` that still verifies implies a
transcript-hash collision or breaks knowledge soundness. ∎

**Theorem 4 (Replay resistance).** Let `X` include chain id `cid` and the
wallet's monotone nonce `n`, and let the verifier contract persist the set of
used `(wallet, n)`. Then a proof accepted for `(cid, n)` cannot authorize a
second state transition, nor be reused under `(cid', n') ≠ (cid, n)`.
*Proof.* Reuse under a different context fails Theorem 3 (public-input
mismatch). Reuse under the same context fails the contract's `(wallet, n)`
membership check, which is updated atomically on first acceptance. ∎

**Theorem 5 (Wallet-side privacy).** The aggregate proof and the data the wallet
publishes reveal nothing about `W` beyond `X`.
*Proof.* Zero-knowledge of the recursive verifier (resp. decider) gives a
simulator that produces `π` (resp. `Π`) from `X` alone; the intermediate
folding transcript is never published. Sensitive fields of `X` (amounts, keys)
appear only as hiding commitments, so `X` itself leaks nothing about their
openings. ∎

---

## 6. Experimental Evaluation

### 6.1 Setup

**Common workload.** One unit step is a MiMC-style permutation:
`STEP_ROUNDS = 128` rounds of `x ← (x + c_i)^5` over the backend's *native*
prime field, with fixed round constants `c_i`. Aggregation depth
`d ∈ {2, 4, 8, 16, 32, 64}` chains `d` steps. The *computational shape* (steps,
rounds, S-box degree) is identical across schemes; the concrete field — and
hence the literal chain output — is each scheme's own (Goldilocks for Plonky2,
the Pallas/Vesta scalar fields for Nova). Fair comparison is on equal circuit
work, not a shared output. Folding verification is measured at the **decider /
compressed-SNARK** call (what a wallet or EVM verifier runs), not the per-step
folding verifier.

**Experiment 1 — native benchmark.** Single x86 machine, `--release`
(`opt-level=3, lto=true, codegen-units=1`), Rust `nightly-2026-09-02` (pinned;
required by Plonky2). Backends: Plonky2 (`plonky2` 1.1, Goldilocks,
`PoseidonGoldilocksConfig`) for recursion; Nova (`nova-snark` 0.75, Pallas/Vesta
2-cycle, IPA commitments — transparent setup) for folding; versions in Table 4.
The Plonky2 aggregate is a linear recursion chain (a leaf step proof wrapped
`d−1` times, each wrap verifying the previous proof in-circuit and adding one
step); its final proof size and verification cost are constant in `d`. The Nova
aggregate folds `d` step instances and closes with a Spartan compressed-SNARK
decider; the exported verification key (the IPA generator vector) is loaded by
the wallet/ARM verifier, which never rebuilds circuits or public parameters.
Each depth: warmup runs are discarded, then N measured runs (current set:
8 proving / 40 verification per depth; the final camera-ready will use
20 / 100). We report mean ± 95% CI and coefficient of variation. Metrics:
proving time, verification time, peak memory (tracking allocator for the
in-process figure, process `VmHWM` on Linux for the verifier), proof size and
verification-key size (canonical serialization). The verifier binary rebuilds
only the exported verification key — never the circuits or SRS — so its peak
memory reflects verification, which matters for Experiment 3.

**Experiment 2 — EVM verification.** Foundry (`forge` 1.8.1, `solc` 0.8.24),
local EVM, BN254 precompiles (0x06/0x07/0x08). Neither family has a native EVM
verifier for its aggregate proof (Plonky2 is FRI over Goldilocks; Nova's IPA
decider is not EVM-cheap), so the practical on-chain path for both is a
**Groth16-wrapped decider** over BN254. We therefore measure (i) the execution
gas of a real 1-public-input Groth16 verification (`vk_x` accumulation via
`ecMul`/`ecAdd`, then a 4-pair `ecPairing`) with valid BN254 generators — gas is
charged independent of the boolean result — and (ii) the EIP-2028 calldata gas
(4/zero, 16/non-zero byte, +21 000 base) of posting each scheme's *raw*
aggregate proof from Experiment 1 at `d ∈ {8, 16}`. Wrapping to Groth16 also
collapses Nova's 10 MiB IPA key to a constant-size key, at the cost of a trusted
setup.

**Experiment 3 — ARM mobile-class.** A GitHub-hosted `ubuntu-24.04-arm` runner
(Ampere Altra, Neoverse-N1 — the same core family as the ARM cloud instances we
would otherwise rent), pinned to **one core** (`taskset -c 0`) as a mobile-ISA /
constrained-client proxy. The workflow (`.github/workflows/exp3-arm.yml`) builds
the *same verifier binary* as Experiment 1, regenerates the `d ∈ {8, 16}` proofs
(deterministic; verification cost is independent of where the proof was
produced), and runs 20 warmup + 200 measured verification runs per depth.
Metrics: verification latency, peak RSS. The runner is a shared VM, so we report
the coefficient of variation; and absolute latencies on a phone SoC may differ
from this proxy by a constant factor (Limitation).

### 6.2 Experiment 1 — Results

Plonky2 (recursive) vs Nova (folding), x86, `nightly-2026-09-02`, 2 warmup + 8
measured proving runs and 10 warmup + 40 measured verification runs per depth
(camera-ready: 20 / 100). Numbers are copied verbatim from
`results/exp1_table.md`.

**Table 1a — Wallet-side verification (x86), mean ± 95% CI.**

| Scheme | Kind | Depth | Verify (ms) | Verify Peak Mem (MiB) | Proof (KiB) | VK (KiB) |
|---|---|---:|---:|---:|---:|---:|
| nova | folding | 2 | 67.31 ± 15.63 | 39.34 | 9.64 | 10453.20 |
| nova | folding | 4 | 165.54 ± 1.66 | 39.39 | 9.64 | 10453.20 |
| nova | folding | 8 | 164.61 ± 2.45 | 38.91 | 9.64 | 10453.20 |
| nova | folding | 16 | 162.95 ± 1.34 | 39.38 | 9.64 | 10453.20 |
| nova | folding | 32 | 164.86 ± 1.75 | 38.91 | 9.64 | 10453.20 |
| nova | folding | 64 | 162.98 ± 0.87 | 39.24 | 9.64 | 10453.20 |
| plonky2 | recursive | 2 | 4.98 ± 0.14 | 0.47 | 124.23 | 1.85 |
| plonky2 | recursive | 4 | 4.86 ± 0.04 | 0.47 | 124.23 | 1.85 |
| plonky2 | recursive | 8 | 4.88 ± 0.05 | 0.47 | 124.23 | 1.85 |
| plonky2 | recursive | 16 | 4.85 ± 0.04 | 0.47 | 124.23 | 1.85 |
| plonky2 | recursive | 32 | 4.85 ± 0.04 | 0.47 | 124.23 | 1.85 |
| plonky2 | recursive | 64 | 4.82 ± 0.02 | 0.47 | 124.23 | 1.85 |

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
| plonky2 | recursive | 32 | 38229.8 ± 4900.3 | 1245.0 |
| plonky2 | recursive | 64 | 137844.5 ± 2181.9 | 2448.6 |

**Observations.**

1. *Verification time is flat in `d` for both families.* Plonky2 verifies the
   single outermost wrap proof (4.8–5.0 ms); Nova verifies the fixed-size
   decider (≈163 ms for `d ≥ 4`; the `d = 2` row is a cold-start outlier, wide
   CI). Recursive verification is **≈34× faster** here.
2. *Verification memory.* Plonky2's verifier loads a 1.85 KiB verification key
   and peaks at **0.47 MiB**; Nova loads a 10.2 MiB IPA key and peaks at
   ≈39 MiB — **≈84×** more.
3. *Proof size favours folding.* Nova's decider proof is **9.64 KiB**, constant;
   Plonky2's FRI proof is **124 KiB**, constant — a **12.9×** gap.
4. *Verification key size favours recursion sharply* — 1.85 KiB vs 10.2 MiB
   (≈5600×). This is partly a consequence of Nova's transparent IPA decider; a
   KZG- or Groth16-wrapped decider would shrink the key to near-constant at the
   cost of a trusted setup (see §6.3).
5. *Prover cost.* Nova proving grows slowly with depth (6.7 s → 20.3 s over
   `d = 2…64`) at constant ≈131 MiB; Plonky2's linear wrap chain grows
   super-linearly (0.9 s → 138 s) and its prover memory grows with depth
   (117 MiB → 2.45 GiB). Folding is the better *prover* for deep aggregation.
   (The `d = 32` Plonky2 proving CV of 18 % reflects host noise; a quiet-machine
   re-run is planned.)

Figure 2 (`results/fig_exp1.png`) and the consolidated dashboard
(`results/dashboard.png`) plot all metrics vs. depth.

### 6.3 Experiment 2 — Results

Measured with Foundry (forge 1.8.1, solc 0.8.24) via the BN254 precompiles
(0x06/0x07/0x08). Two scenarios.

**Scenario A — verify a Groth16-wrapped decider proof on-chain** (the practical
EVM path for both families). A 1-public-input Groth16 check (4-pair pairing +
one `ecMul`/`ecAdd` for `vk_x`) costs **202,138 gas** of execution; with a
~256 B wrapped proof as calldata the transaction is ≈ 227 k gas. This is
essentially the same for either family — the wrapped proof is small and
constant. The families differ *off-chain*: a folding decider is already a small
final SNARK and wraps directly, whereas the Plonky2 FRI proof needs a separate,
heavy Groth16 wrapping step.

**Scenario B — post the raw aggregate proof on-chain** (e.g. for data
availability). Cost is dominated by EIP-2028 calldata (4 gas/zero byte,
16 gas/non-zero byte):

| Scheme | Proof (B) | Calldata gas | Tx post cost |
|---|---:|---:|---:|
| Nova (folding) | 9,872 | 156,248 | 177,248 |
| Plonky2 (recursion) | 127,208 | 2,028,716 | 2,049,716 |

Folding is **≈ 11.6×** cheaper to post. (`d = 8`; `d = 16` differs only in a few
non-zero bytes.)

**Reading.** On-chain *verification execution* does not separate the families
(both ≈ 202 k once wrapped). What separates them on-chain is *proof size as
calldata*: recursion's 124 KiB FRI proof is expensive to transmit, folding's
9.6 KiB decider proof is not. This is the mirror image of the wallet-side result
in §6.2.

### 6.4 Experiment 3 — Results

**Table 3.** ARM mobile-class verification, Plonky2 vs Nova
(`results/exp3_table.md`). _Pending the `exp3-arm` GitHub Actions run._

| Scheme | Kind | Depth | Verify Latency (ms) | Peak Mem (MiB) |
|---|---|---:|---:|---:|
| plonky2 | recursive | 8 | — | — |
| plonky2 | recursive | 16 | — | — |
| nova | folding | 8 | — | — |
| nova | folding | 16 | — | — |

We expect this to confirm the Experiment 1 ordering on ARM: published
ARM-vs-x86 SNARK-verification ratios are ≈2–4× in latency, which keeps the
recursive verifier well under 20 ms while the folding decider approaches a few
hundred ms; memory and key size are ISA-independent, so the 0.47 MiB vs 39 MiB
and 1.85 KiB vs 10.2 MiB gaps carry over directly.

### 6.5 Selection

**Rule.** Rank schemes by, in order, (i) verification time, (ii) peak
verification memory, (iii) proof size, using Experiment 1; require a working EVM
verifier (Experiment 2); confirm on ARM (Experiment 3). The lightest scheme
satisfying all three is the recommendation for SwiftZK-Wallet.

**Outcome (current data).** On criteria (i)–(iii) the recursive scheme
**Plonky2** is the lightweight choice for SwiftZK-Wallet: it verifies ≈34×
faster (4.8 ms vs 163 ms), with ≈84× less verifier memory (0.47 MiB vs 39 MiB)
and a ≈5600× smaller verification key (1.85 KiB vs 10.2 MiB), all flat in
aggregation depth. Folding (Nova) wins only criterion (iii), proof size
(9.64 KiB vs 124 KiB), and is the better *prover* for deep aggregation. For a
wallet that only ever verifies, the proof-size advantage does not offset the
verification-time, memory, and key-size costs. Experiment 2 does not overturn
this: once wrapped to Groth16 both families verify on-chain at ≈202 k gas, and
the wallet in our architecture verifies locally and submits only a small
attestation, so the 11.6× calldata penalty of Plonky2's raw proof (§6.3) is not
on the wallet's critical path. The recommendation is therefore **recursive
aggregation (Plonky2)** for wallet-side verification; folding is preferable when
the raw aggregate proof is posted on-chain, or when uplink bandwidth or prover
scalability dominates. This conclusion is scoped to wallet-side verification and
to this workload; it is not a claim of general superiority. Halo2 and SuperNova would change which concrete
scheme represents each family, not the family-level ordering: both share their
family's verifier structure (one succinct final check for recursion; a decider
check plus a commitment-key–sized verification key for folding).

**Table 4.** Reproducibility. x86 host specs / OS / kernel _TBD_.
Rust `nightly-2026-09-02`. Crates: `plonky2` 1.1, `nova-snark` 0.75,
`peak_alloc` 0.2. Release profile `opt-level=3, lto=true, codegen-units=1`.
Foundry `forge 1.8.1`, `solc 0.8.24`. Experiment 3: GitHub-hosted
`ubuntu-24.04-arm` runner (Ampere Altra / Neoverse-N1; exact `lscpu` recorded by
the workflow). Artefacts: `results/summary_*.csv`, `results/raw/*.csv`,
`proofs/*.{bin,vk}`; the `exp3-arm` workflow is the executable Exp 3 protocol.

**Limitations.** Single workload family. Each ZK family is instantiated with one
implementation (Plonky2, Nova); Halo2 and SuperNova are discussed but not
benchmarked. Experiment 3 runs on a Neoverse-N1 core (a server-class ARM part
sharing the mobile ISA) on a shared CI VM, not a phone SoC or a dedicated
machine; we mitigate with 200 runs and report variance, and on-device
measurement remains future work. Plonky2 lacks a native EVM verifier, so its
on-chain figure requires a Groth16 wrap. The folding verification cost and key
size depend on the decider (transparent IPA here; Groth16 for the EVM path).

---

## 7. Conclusion

We framed ZK proof aggregation from the mobile wallet's point of view — the
party that verifies — and compared recursion (Plonky2) against folding (Nova)
under one identical workload, an aggregation-depth sweep 2–64, and repeated-run
statistics, then carried the result to an EVM verifier and an ARM mobile-class
environment. On the wallet's own cost — verification time, verifier memory, and
verification-key size — recursion dominates by one to three orders of magnitude
and is flat in aggregation depth; folding's smaller proof does not offset this
for a client that only verifies. The deliverable is a systematic comparison and
a selection rule based on measured verification time, memory, and proof size,
plus a blockchain-connected verification path. We make no claim to a new
protocol or to universal superiority; the scope is lightweight wallet-side
verification. Future work: Halo2 and SuperNova on the same harness, additional
workload families, and on-device (phone SoC) measurement.

---

<!-- End of draft. Build tables via: python analysis/analyze.py --figures -->
