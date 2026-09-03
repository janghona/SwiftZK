// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

/// @title Groth16 (BN254) decider verifier — representative on-chain verification
/// @notice This is the verification an EVM contract runs for the folding EVM
/// path (§6.3): a Groth16-wrapped decider proof. The pairing/curve arithmetic
/// (precompiles 0x06 ecAdd, 0x07 ecMul, 0x08 ecPairing) is what fixes the gas
/// cost — ~200k regardless of the concrete statement — so the shape here matches
/// a real snarkjs/arkworks Groth16 verifier: one ecMul + one ecAdd per public
/// input to accumulate vk_x, then a 4-pair pairing check.
///
/// The verifying key and proof passed in the test are valid BN254 group
/// elements (generators and their negations) chosen so the pairing check
/// returns success; the cryptographic statement is immaterial to the gas
/// measurement, which is the point of Experiment 2.
contract Groth16DeciderVerifier {
    uint256 internal constant P =
        0x30644e72e131a029b85045b68181585d97816a916871ca8d3c208c16d87cfd47;

    struct G1 {
        uint256 x;
        uint256 y;
    }
    // G2 in EVM precompile byte order: (x.c1, x.c0, y.c1, y.c0)
    struct G2 {
        uint256 x1;
        uint256 x0;
        uint256 y1;
        uint256 y0;
    }

    struct Proof {
        G1 a;
        G2 b;
        G1 c;
    }

    struct VK {
        G1 alpha;
        G2 beta;
        G2 gamma;
        G2 delta;
        G1[] ic; // length = nPublic + 1
    }

    error PairingFailed();
    error BadPairingInput();

    /// Mirrors a real Groth16 verifier: accumulate vk_x over the public inputs,
    /// then check e(-A,B)·e(alpha,beta)·e(vk_x,gamma)·e(C,delta) == 1.
    function verify(Proof calldata proof, uint256[] calldata input, VK calldata vk)
        external
        view
        returns (bool)
    {
        require(vk.ic.length == input.length + 1, "vk/input length");

        // vk_x = IC[0] + sum_i input[i] * IC[i+1]
        G1 memory vkx = vk.ic[0];
        for (uint256 i = 0; i < input.length; i++) {
            G1 memory term = _ecMul(vk.ic[i + 1], input[i]);
            vkx = _ecAdd(vkx, term);
        }

        // negate A
        G1 memory negA = G1(proof.a.x, proof.a.y == 0 ? 0 : P - proof.a.y);

        uint256[24] memory in_;
        _put(in_, 0, negA, proof.b);
        _put(in_, 6, vk.alpha, vk.beta);
        _put(in_, 12, vkx, vk.gamma);
        _put(in_, 18, proof.c, vk.delta);

        uint256[1] memory out;
        bool ok;
        assembly {
            ok := staticcall(gas(), 0x08, in_, 0x300, out, 0x20)
        }
        if (!ok) revert BadPairingInput();
        return out[0] == 1;
    }

    function _put(uint256[24] memory a, uint256 off, G1 memory p, G2 memory q)
        internal
        pure
    {
        a[off + 0] = p.x;
        a[off + 1] = p.y;
        a[off + 2] = q.x1;
        a[off + 3] = q.x0;
        a[off + 4] = q.y1;
        a[off + 5] = q.y0;
    }

    function _ecMul(G1 memory p, uint256 s) internal view returns (G1 memory r) {
        uint256[3] memory in_ = [p.x, p.y, s];
        uint256[2] memory out;
        bool ok;
        assembly {
            ok := staticcall(gas(), 0x07, in_, 0x60, out, 0x40)
        }
        require(ok, "ecMul");
        r = G1(out[0], out[1]);
    }

    function _ecAdd(G1 memory p, G1 memory q) internal view returns (G1 memory r) {
        uint256[4] memory in_ = [p.x, p.y, q.x, q.y];
        uint256[2] memory out;
        bool ok;
        assembly {
            ok := staticcall(gas(), 0x06, in_, 0x80, out, 0x40)
        }
        require(ok, "ecAdd");
        r = G1(out[0], out[1]);
    }
}
