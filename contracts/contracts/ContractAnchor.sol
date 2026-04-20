// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";

/**
 * @title ContractAnchor
 * @dev Lightweight on-chain anchoring for NILBx contract terms and deliverable proofs.
 * @notice Stores only SHA-256 hashes — NEVER raw PII or contract content.
 *
 * Gas-optimized for high-volume anchoring (~30K gas per anchor vs ~100K+ for
 * SponsorshipContract.createTask). Uses event logs for cheap immutable storage
 * plus a mapping for on-chain verification.
 *
 * Supports two anchor types:
 *   1. Contract anchoring: SHA-256 of contract terms, anchored on execution
 *   2. Proof anchoring: SHA-256 of deliverable proof metadata, anchored on verification
 *
 * Security:
 *   - Owner-only write access (platform deployer wallet)
 *   - Duplicate anchor prevention (cannot overwrite existing anchors)
 *   - ReentrancyGuard for defense-in-depth
 *   - No ETH handling (pure data contract)
 */
contract ContractAnchor is Ownable, ReentrancyGuard {

    // ── Structs ─────────────────────────────────────────────────────────

    struct Anchor {
        uint256 timestamp;
        uint256 blockNumber;
        uint256 entityId;      // contractId or deliverableId
    }

    // ── Storage ─────────────────────────────────────────────────────────

    /// @dev termsHash => Anchor (contract anchors)
    mapping(bytes32 => Anchor) private _contractAnchors;

    /// @dev proofHash => Anchor (deliverable proof anchors)
    mapping(bytes32 => Anchor) private _proofAnchors;

    /// @dev Total number of contract anchors
    uint256 public contractAnchorCount;

    /// @dev Total number of proof anchors
    uint256 public proofAnchorCount;

    // ── Events ──────────────────────────────────────────────────────────

    /// @notice Emitted when a contract's terms hash is anchored on-chain
    event ContractAnchored(
        bytes32 indexed termsHash,
        uint256 indexed contractId,
        uint256 timestamp,
        uint256 blockNumber
    );

    /// @notice Emitted when a deliverable proof hash is anchored on-chain
    event ProofAnchored(
        bytes32 indexed proofHash,
        uint256 indexed deliverableId,
        uint256 timestamp,
        uint256 blockNumber
    );

    // ── Errors ──────────────────────────────────────────────────────────

    /// @dev Thrown when attempting to anchor a hash that already exists
    error AnchorAlreadyExists(bytes32 hash);

    /// @dev Thrown when the provided hash is zero
    error InvalidHash();

    // ── Constructor ─────────────────────────────────────────────────────

    constructor() Ownable() {}

    // ── Contract Anchoring ──────────────────────────────────────────────

    /**
     * @notice Anchor a contract's terms hash on-chain.
     * @dev Only callable by the contract owner (platform deployer).
     *      Reverts if the hash has already been anchored (idempotency).
     * @param termsHash SHA-256 hash of the contract terms
     * @param contractId NILBx platform contract instance ID
     */
    function anchorContract(
        bytes32 termsHash,
        uint256 contractId
    ) external onlyOwner nonReentrant {
        if (termsHash == bytes32(0)) revert InvalidHash();
        if (_contractAnchors[termsHash].timestamp != 0) {
            revert AnchorAlreadyExists(termsHash);
        }

        _contractAnchors[termsHash] = Anchor({
            timestamp: block.timestamp,
            blockNumber: block.number,
            entityId: contractId
        });

        unchecked {
            contractAnchorCount++;
        }

        emit ContractAnchored(
            termsHash,
            contractId,
            block.timestamp,
            block.number
        );
    }

    // ── Proof Anchoring ─────────────────────────────────────────────────

    /**
     * @notice Anchor a deliverable proof hash on-chain.
     * @dev Only callable by the contract owner (platform deployer).
     *      Reverts if the hash has already been anchored (idempotency).
     * @param proofHash SHA-256 hash of the deliverable proof metadata
     * @param deliverableId NILBx platform deliverable ID
     */
    function anchorProof(
        bytes32 proofHash,
        uint256 deliverableId
    ) external onlyOwner nonReentrant {
        if (proofHash == bytes32(0)) revert InvalidHash();
        if (_proofAnchors[proofHash].timestamp != 0) {
            revert AnchorAlreadyExists(proofHash);
        }

        _proofAnchors[proofHash] = Anchor({
            timestamp: block.timestamp,
            blockNumber: block.number,
            entityId: deliverableId
        });

        unchecked {
            proofAnchorCount++;
        }

        emit ProofAnchored(
            proofHash,
            deliverableId,
            block.timestamp,
            block.number
        );
    }

    // ── Verification (View Functions) ───────────────────────────────────

    /**
     * @notice Verify whether a contract terms hash has been anchored.
     * @param termsHash The SHA-256 hash to verify
     * @return exists True if the hash has been anchored
     * @return timestamp Unix timestamp when anchored (0 if not found)
     * @return blockNumber Block number when anchored (0 if not found)
     * @return contractId Platform contract ID (0 if not found)
     */
    function verifyContractAnchor(
        bytes32 termsHash
    ) external view returns (
        bool exists,
        uint256 timestamp,
        uint256 blockNumber,
        uint256 contractId
    ) {
        Anchor memory a = _contractAnchors[termsHash];
        return (
            a.timestamp != 0,
            a.timestamp,
            a.blockNumber,
            a.entityId
        );
    }

    /**
     * @notice Verify whether a deliverable proof hash has been anchored.
     * @param proofHash The SHA-256 hash to verify
     * @return exists True if the hash has been anchored
     * @return timestamp Unix timestamp when anchored (0 if not found)
     * @return blockNumber Block number when anchored (0 if not found)
     * @return deliverableId Platform deliverable ID (0 if not found)
     */
    function verifyProofAnchor(
        bytes32 proofHash
    ) external view returns (
        bool exists,
        uint256 timestamp,
        uint256 blockNumber,
        uint256 deliverableId
    ) {
        Anchor memory a = _proofAnchors[proofHash];
        return (
            a.timestamp != 0,
            a.timestamp,
            a.blockNumber,
            a.entityId
        );
    }
}
