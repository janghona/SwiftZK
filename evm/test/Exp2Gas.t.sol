// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import {Test, console2} from "forge-std/Test.sol";
import {Groth16DeciderVerifier as V} from "../src/Groth16DeciderVerifier.sol";

/// Experiment 2 — EVM verification cost.
///
/// Two measurements, both reported in the paper (§6.3):
///   1. Decider verification gas — the pairing-based Groth16 check an EVM
///      contract runs for the folding EVM path (and for any Groth16-wrapped
///      recursion). Uses valid BN254 generators; gas is result-independent.
///   2. Calldata gas of each scheme's *raw* aggregate proof (EIP-2028), i.e.
///      the cost of posting the proof itself on-chain. Uses the real proof
///      files from Experiment 1.
contract Exp2GasTest is Test {
    // BN254 G1 generator and its negation
    uint256 constant P =
        0x30644e72e131a029b85045b68181585d97816a916871ca8d3c208c16d87cfd47;
    // G2 generator, EVM precompile order (x.c1, x.c0, y.c1, y.c0)
    uint256 constant G2_X1 =
        11559732032986387107991004021392285783925812861821192530917403151452391805634;
    uint256 constant G2_X0 =
        10857046999023057135944570762232829481370756359578518086990519993285655852781;
    uint256 constant G2_Y1 =
        4082367875863433681332203403145435568316851327593401208105741076214120093531;
    uint256 constant G2_Y0 =
        8495653923123431417604973247489272438418190587263600148770280649306958101930;

    V verifier;

    function setUp() public {
        verifier = new V();
    }

    function _g1() internal pure returns (V.G1 memory) {
        return V.G1(1, 2);
    }

    function _negG1() internal pure returns (V.G1 memory) {
        return V.G1(1, P - 2);
    }

    function _g2() internal pure returns (V.G2 memory) {
        return V.G2(G2_X1, G2_X0, G2_Y1, G2_Y0);
    }

    /// Measurement 1: decider verification gas.
    function test_DeciderVerificationGas() public view {
        V.G1[] memory ic = new V.G1[](2);
        ic[0] = _g1();
        ic[1] = _g1();
        V.VK memory vk = V.VK(_g1(), _g2(), _g2(), _g2(), ic);

        // A=g1, B=g2, C=-g1  =>  e(-A,B)e(alpha,beta)e(vkx,gamma)e(C,delta)
        //                       = e(g1,g2)^(-1+1+1-1) = 1
        V.Proof memory proof = V.Proof(_g1(), _g2(), _negG1());

        uint256[] memory input = new uint256[](1);
        input[0] = 0; // vkx = ic[0] + 0*ic[1] = g1

        uint256 g0 = gasleft();
        bool ok = verifier.verify(proof, input, vk);
        uint256 used = g0 - gasleft();

        console2.log("decider_verification_gas :", used);
        console2.log("decider_verify_ok        :", ok);
        assertTrue(ok, "valid decider proof rejected");
        // sanity band for a 1-public-input Groth16 verify (4-pair pairing +
        // 1 ecMul + 1 ecAdd + call overhead)
        assertLt(used, 400000);
        assertGt(used, 150000);
    }

    /// Measurement 2: calldata gas for posting each scheme's raw aggregate proof.
    function test_RawProofCalldataGas() public view {
        _calldata("nova", 8);
        _calldata("nova", 16);
        _calldata("plonky2", 8);
        _calldata("plonky2", 16);
    }

    function _calldata(string memory scheme, uint256 depth) internal view {
        string memory path =
            string.concat("../proofs/", scheme, "_d", vm.toString(depth), ".bin");
        bytes memory proof = vm.readFileBinary(path);

        uint256 zero;
        uint256 nonzero;
        for (uint256 i = 0; i < proof.length; i++) {
            if (proof[i] == 0) zero++;
            else nonzero++;
        }
        // EIP-2028: 4 gas per zero byte, 16 per non-zero byte; + 21000 base tx.
        uint256 calldataGas = zero * 4 + nonzero * 16;
        uint256 txCost = 21000 + calldataGas;

        console2.log("scheme_depth        :", string.concat(scheme, "_d", vm.toString(depth)));
        console2.log("  proof_bytes       :", proof.length);
        console2.log("  calldata_gas      :", calldataGas);
        console2.log("  tx_post_cost      :", txCost);
    }
}
