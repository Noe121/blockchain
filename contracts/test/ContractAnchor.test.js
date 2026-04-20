const { expect } = require("chai");
const { ethers } = require("hardhat");
const { loadFixture } = require("@nomicfoundation/hardhat-network-helpers");
const { anyValue } = require("@nomicfoundation/hardhat-chai-matchers/withArgs");

describe("ContractAnchor — On-Chain Immutability Proofs", function () {
  let anchor;
  let owner, attacker;

  // Test constants
  const TERMS_HASH = ethers.keccak256(ethers.toUtf8Bytes("contract-terms-sha256-hash"));
  const PROOF_HASH = ethers.keccak256(ethers.toUtf8Bytes("deliverable-proof-sha256-hash"));
  const CONTRACT_ID = 42;
  const DELIVERABLE_ID = 99;
  const ZERO_HASH = ethers.ZeroHash;

  async function deployFixture() {
    [owner, attacker] = await ethers.getSigners();
    const ContractAnchor = await ethers.getContractFactory("ContractAnchor");
    anchor = await ContractAnchor.deploy();
    return { anchor, owner, attacker };
  }

  // ── Deployment ──────────────────────────────────────────────────────

  describe("Deployment", function () {
    beforeEach(async function () {
      ({ anchor } = await loadFixture(deployFixture));
    });

    it("Should deploy with owner set correctly", async function () {
      expect(await anchor.owner()).to.equal(owner.address);
    });

    it("Should start with zero anchor counts", async function () {
      expect(await anchor.contractAnchorCount()).to.equal(0);
      expect(await anchor.proofAnchorCount()).to.equal(0);
    });
  });

  // ── Contract Anchoring ──────────────────────────────────────────────

  describe("Contract Anchoring", function () {
    beforeEach(async function () {
      ({ anchor, attacker } = await loadFixture(deployFixture));
    });

    it("Should anchor a contract terms hash", async function () {
      const tx = await anchor.anchorContract(TERMS_HASH, CONTRACT_ID);
      const receipt = await tx.wait();

      // Verify event emitted
      const event = receipt.logs.find(l => l.fragment?.name === "ContractAnchored");
      expect(event).to.not.be.undefined;

      // Verify counter incremented
      expect(await anchor.contractAnchorCount()).to.equal(1);
    });

    it("Should emit ContractAnchored event with correct args", async function () {
      await expect(anchor.anchorContract(TERMS_HASH, CONTRACT_ID))
        .to.emit(anchor, "ContractAnchored")
        .withArgs(TERMS_HASH, CONTRACT_ID, anyValue, anyValue);
    });

    it("Should revert on duplicate anchor (idempotency)", async function () {
      await anchor.anchorContract(TERMS_HASH, CONTRACT_ID);
      await expect(anchor.anchorContract(TERMS_HASH, CONTRACT_ID))
        .to.be.revertedWithCustomError(anchor, "AnchorAlreadyExists");
    });

    it("Should revert on zero hash", async function () {
      await expect(anchor.anchorContract(ZERO_HASH, CONTRACT_ID))
        .to.be.revertedWithCustomError(anchor, "InvalidHash");
    });

    it("Should revert when called by non-owner", async function () {
      await expect(
        anchor.connect(attacker).anchorContract(TERMS_HASH, CONTRACT_ID)
      ).to.be.revertedWith("Ownable: caller is not the owner");
    });

    it("Should allow anchoring different hashes", async function () {
      const hash2 = ethers.keccak256(ethers.toUtf8Bytes("another-contract-hash"));
      await anchor.anchorContract(TERMS_HASH, CONTRACT_ID);
      await anchor.anchorContract(hash2, CONTRACT_ID + 1);
      expect(await anchor.contractAnchorCount()).to.equal(2);
    });
  });

  // ── Proof Anchoring ─────────────────────────────────────────────────

  describe("Proof Anchoring", function () {
    beforeEach(async function () {
      ({ anchor, attacker } = await loadFixture(deployFixture));
    });

    it("Should anchor a deliverable proof hash", async function () {
      await anchor.anchorProof(PROOF_HASH, DELIVERABLE_ID);
      expect(await anchor.proofAnchorCount()).to.equal(1);
    });

    it("Should emit ProofAnchored event", async function () {
      await expect(anchor.anchorProof(PROOF_HASH, DELIVERABLE_ID))
        .to.emit(anchor, "ProofAnchored")
        .withArgs(PROOF_HASH, DELIVERABLE_ID, anyValue, anyValue);
    });

    it("Should revert on duplicate proof anchor", async function () {
      await anchor.anchorProof(PROOF_HASH, DELIVERABLE_ID);
      await expect(anchor.anchorProof(PROOF_HASH, DELIVERABLE_ID))
        .to.be.revertedWithCustomError(anchor, "AnchorAlreadyExists");
    });

    it("Should revert on zero proof hash", async function () {
      await expect(anchor.anchorProof(ZERO_HASH, DELIVERABLE_ID))
        .to.be.revertedWithCustomError(anchor, "InvalidHash");
    });

    it("Should revert when called by non-owner", async function () {
      await expect(
        anchor.connect(attacker).anchorProof(PROOF_HASH, DELIVERABLE_ID)
      ).to.be.revertedWith("Ownable: caller is not the owner");
    });
  });

  // ── Verification ────────────────────────────────────────────────────

  describe("Verification", function () {
    beforeEach(async function () {
      ({ anchor } = await loadFixture(deployFixture));
    });

    it("Should verify an anchored contract", async function () {
      await anchor.anchorContract(TERMS_HASH, CONTRACT_ID);
      const [exists, timestamp, blockNumber, contractId] =
        await anchor.verifyContractAnchor(TERMS_HASH);

      expect(exists).to.be.true;
      expect(timestamp).to.be.gt(0);
      expect(blockNumber).to.be.gt(0);
      expect(contractId).to.equal(CONTRACT_ID);
    });

    it("Should return false for non-existent contract anchor", async function () {
      const [exists, timestamp, blockNumber, contractId] =
        await anchor.verifyContractAnchor(TERMS_HASH);

      expect(exists).to.be.false;
      expect(timestamp).to.equal(0);
      expect(blockNumber).to.equal(0);
      expect(contractId).to.equal(0);
    });

    it("Should verify an anchored proof", async function () {
      await anchor.anchorProof(PROOF_HASH, DELIVERABLE_ID);
      const [exists, timestamp, blockNumber, deliverableId] =
        await anchor.verifyProofAnchor(PROOF_HASH);

      expect(exists).to.be.true;
      expect(timestamp).to.be.gt(0);
      expect(deliverableId).to.equal(DELIVERABLE_ID);
    });

    it("Should return false for non-existent proof anchor", async function () {
      const [exists, , ,] = await anchor.verifyProofAnchor(PROOF_HASH);
      expect(exists).to.be.false;
    });

    it("Contract and proof anchors are independent namespaces", async function () {
      // Same hash can exist in both namespaces
      const sharedHash = ethers.keccak256(ethers.toUtf8Bytes("shared-hash"));
      await anchor.anchorContract(sharedHash, 1);
      await anchor.anchorProof(sharedHash, 2);

      const [contractExists, , , contractId] = await anchor.verifyContractAnchor(sharedHash);
      const [proofExists, , , deliverableId] = await anchor.verifyProofAnchor(sharedHash);

      expect(contractExists).to.be.true;
      expect(proofExists).to.be.true;
      expect(contractId).to.equal(1);
      expect(deliverableId).to.equal(2);
    });
  });

  // ── Gas Optimization ────────────────────────────────────────────────

  describe("Gas Optimization", function () {
    beforeEach(async function () {
      ({ anchor } = await loadFixture(deployFixture));
    });

    it("anchorContract should use less than 150K gas", async function () {
      const tx = await anchor.anchorContract(TERMS_HASH, CONTRACT_ID);
      const receipt = await tx.wait();
      // First write to a cold storage slot costs ~118K gas.
      // Subsequent writes to warm slots cost ~50K.
      expect(receipt.gasUsed).to.be.lt(150000);
    });

    it("anchorProof should use less than 150K gas", async function () {
      const tx = await anchor.anchorProof(PROOF_HASH, DELIVERABLE_ID);
      const receipt = await tx.wait();
      expect(receipt.gasUsed).to.be.lt(150000);
    });

    it("Verification is free (view function)", async function () {
      // View functions don't consume gas when called off-chain
      await anchor.anchorContract(TERMS_HASH, CONTRACT_ID);
      const result = await anchor.verifyContractAnchor(TERMS_HASH);
      expect(result[0]).to.be.true;
    });
  });
});

