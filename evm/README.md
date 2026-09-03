# Experiment 2 — EVM Verification Cost (Foundry)

Separate, self-contained experiment. Consumes the **real aggregate-proof files**
from Experiment 1 (`../proofs/<scheme>_d<depth>.bin`). No automated
Rust→Python→Ethereum pipeline.

## Run

```
export PATH="$PATH:$HOME/.foundry/bin"          # if foundryup installed here
forge install foundry-rs/forge-std --no-git     # once, into evm/lib/
forge test -vv                                   # prints both measurements
```

## What is measured

`test/Exp2Gas.t.sol`, via the BN254 precompiles (0x06 ecAdd, 0x07 ecMul,
0x08 ecPairing):

1. **`test_DeciderVerificationGas`** — a real 1-public-input Groth16 (BN254)
   verification: `vk_x` accumulation (`ecMul` + `ecAdd`) then a 4-pair pairing
   check. Points are valid BN254 generators chosen so the check returns `true`;
   gas is charged regardless of the boolean, so this is the representative
   on-chain **verification execution cost** for a Groth16-wrapped decider (the
   practical EVM path for both folding and wrapped recursion).
   → ~202 k gas.

2. **`test_RawProofCalldataGas`** — EIP-2028 calldata gas (4 gas/zero byte,
   16 gas/non-zero byte) + 21 000 base, for posting each scheme's **raw**
   aggregate proof on-chain.
   → Nova 9 872 B ≈ 177 k gas; Plonky2 127 208 B ≈ 2.05 M gas.

Results are transcribed to `../results/raw/exp2_gas.csv`
(`scheme,depth,verification_gas,tx_exec_cost,note`) and picked up by
`analysis/analyze.py` → `results/exp2_table.md` and dashboard panel E.

## Not done here

A full scheme-specific verifier (sonobe `NovaDecider` Solidity export, or a
`halo2-solidity-verifier`) would give per-scheme execution gas, but once wrapped
to Groth16 both land at ~202 k; the distinguishing on-chain cost is calldata
(measurement 2). See paper §6.3.
