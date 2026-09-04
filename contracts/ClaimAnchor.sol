// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title ClaimAnchor — forward-only wallet claim anchoring on Base
/// @notice Stores no state. Emits an event binding msg.sender to a claim hash at block.timestamp.
///         The claim hash is keccak256 of the EIP-191 claim message. Wiping the off-chain
///         database cannot make this claim retroactive: the block timestamp is the proof.
///         Cost: one event log (~375 gas + 8 gas per byte of hash).
contract ClaimAnchor {
    event Claimed(address indexed claimer, bytes32 indexed claimHash, uint256 at, string venue);

    function anchor(bytes32 claimHash, string calldata venue) external {
        emit Claimed(msg.sender, claimHash, block.timestamp, venue);
    }

    function anchorBatch(bytes32[] calldata claimHashes, string calldata venue) external {
        for (uint256 i = 0; i < claimHashes.length; i++) {
            emit Claimed(msg.sender, claimHashes[i], block.timestamp, venue);
        }
    }
}
