const { expect } = require("chai");
const { ethers } = require("hardhat");
const { loadFixture, time, mine } = require("@nomicfoundation/hardhat-network-helpers");

describe("NILbx Smart Contracts - Security Tests", function () {
  let playerNFT, sponsorshipContract;
  let owner, athlete, sponsor, recipient, attacker;

  async function deployContractsFixture() {
    [owner, athlete, sponsor, recipient, attacker] = await ethers.getSigners();

    const PlayerLegacyNFT = await ethers.getContractFactory("PlayerLegacyNFT");
    playerNFT = await PlayerLegacyNFT.deploy();

    const SponsorshipContract = await ethers.getContractFactory("SponsorshipContract");
    sponsorshipContract = await SponsorshipContract.deploy(owner.address);

    return { playerNFT, sponsorshipContract, owner, athlete, sponsor, recipient, attacker };
  }

  beforeEach(async function () {
    ({ playerNFT, sponsorshipContract, athlete, sponsor, recipient, attacker } = await loadFixture(deployContractsFixture));
  });

  describe("Access Control Tests", function () {
    it("Should prevent unauthorized NFT minting", async function () {
      await expect(
        playerNFT.connect(attacker).mintLegacyNFT(athlete.address, recipient.address, "ipfs://test", 500)
      ).to.be.revertedWith("Ownable: caller is not the owner");
    });

    it("Should prevent unauthorized batch NFT minting", async function () {
      const athletes = [athlete.address];
      const recipients = [recipient.address];
      const tokenURIs = ["ipfs://test"];
      const royaltyFees = [500];

      await expect(
        playerNFT.connect(attacker).batchMintLegacyNFT(athletes, recipients, tokenURIs, royaltyFees)
      ).to.be.revertedWith("Ownable: caller is not the owner");
    });

    it("Should prevent unauthorized platform fee updates", async function () {
      await expect(
        sponsorshipContract.connect(attacker).updatePlatformFee(500)
      ).to.be.revertedWith("Ownable: caller is not the owner");
    });

    it("Should prevent unauthorized fee recipient updates", async function () {
      await expect(
        sponsorshipContract.connect(attacker).updatePlatformFeeRecipient(attacker.address)
      ).to.be.revertedWith("Ownable: caller is not the owner");
    });

    it("Should prevent unauthorized emergency withdrawals", async function () {
      await expect(
        sponsorshipContract.connect(attacker).emergencyWithdraw()
      ).to.be.revertedWith("Ownable: caller is not the owner");
    });
  });

  describe("Reentrancy Protection Tests", function () {
    it("Should prevent reentrancy in NFT minting", async function () {
      // Deploy a mock reentrancy contract
      const ReentrancyAttacker = await ethers.getContractFactory("ReentrancyAttacker");
      const attackerContract = await ReentrancyAttacker.deploy(playerNFT.target);

      // Fund the attacker contract
      await owner.sendTransaction({ to: attackerContract.target, value: ethers.parseEther("1") });

      // Attempt reentrancy attack
      await expect(
        attackerContract.attack()
      ).to.be.reverted; // Should fail due to reentrancy guard
    });

    it("Should prevent reentrancy in sponsorship payments", async function () {
      // Deploy a mock reentrancy contract for sponsorship
      const SponsorshipReentrancyAttacker = await ethers.getContractFactory("SponsorshipReentrancyAttacker");
      const attackerContract = await SponsorshipReentrancyAttacker.deploy(sponsorshipContract.target);

      // Create a task
      await sponsorshipContract.connect(sponsor).createTask(attackerContract.target, "Test task", { value: ethers.parseEther("1") });

      // Accept and submit task
      await attackerContract.acceptTask(1);
      await attackerContract.submitDeliverable(1, ethers.keccak256(ethers.toUtf8Bytes("test")));

      // Attempt reentrancy attack during approval
      await expect(
        sponsorshipContract.connect(sponsor).approveTask(1)
      ).to.not.be.reverted; // Should complete without reentrancy issues
    });
  });

  describe("Input Validation Tests", function () {
    it("Should reject zero address for athlete in NFT minting", async function () {
      await expect(
        playerNFT.mintLegacyNFT(ethers.ZeroAddress, recipient.address, "ipfs://test", 500)
      ).to.be.revertedWith("Invalid athlete address");
    });

    it("Should reject zero address for recipient in NFT minting", async function () {
      await expect(
        playerNFT.mintLegacyNFT(athlete.address, ethers.ZeroAddress, "ipfs://test", 500)
      ).to.be.revertedWith("Invalid recipient address");
    });

    it("Should reject empty token URI", async function () {
      await expect(
        playerNFT.mintLegacyNFT(athlete.address, recipient.address, "", 500)
      ).to.be.revertedWith("Token URI cannot be empty");
    });

    it("Should reject excessive royalty fees", async function () {
      await expect(
        playerNFT.mintLegacyNFT(athlete.address, recipient.address, "ipfs://test", 1001)
      ).to.be.revertedWith("Royalty fee too high");
    });

    it("Should reject zero address athlete in task creation", async function () {
      await expect(
        sponsorshipContract.connect(sponsor).createTask(ethers.ZeroAddress, "Test task", { value: ethers.parseEther("0.1") })
      ).to.be.revertedWith("Invalid athlete address");
    });

    it("Should reject zero payment in task creation", async function () {
      await expect(
        sponsorshipContract.connect(sponsor).createTask(athlete.address, "Test task", { value: 0 })
      ).to.be.revertedWith("Payment required");
    });

    it("Should reject empty description in task creation", async function () {
      await expect(
        sponsorshipContract.connect(sponsor).createTask(athlete.address, "", { value: ethers.parseEther("0.1") })
      ).to.be.revertedWith("Description required");
    });

    it("Should reject zero address fee recipient update", async function () {
      await expect(
        sponsorshipContract.connect(owner).updatePlatformFeeRecipient(ethers.ZeroAddress)
      ).to.be.revertedWith("Invalid recipient");
    });
  });

  describe("Integer Overflow/Underflow Protection", function () {
    it("Should handle maximum royalty fees safely", async function () {
      const maxRoyalty = 1000; // 10%
      await playerNFT.mintLegacyNFT(athlete.address, recipient.address, "ipfs://test", maxRoyalty);

      const [royaltyRecipient, royaltyAmount] = await playerNFT.royaltyInfo(1, ethers.parseEther("1"));
      expect(royaltyRecipient).to.equal(athlete.address);
      expect(royaltyAmount).to.equal(ethers.parseEther("0.1")); // 10% of 1 ETH
    });

    it("Should handle large payment amounts in sponsorship", async function () {
      const largeAmount = ethers.parseEther("10000"); // 10,000 ETH

      await sponsorshipContract.connect(sponsor).createTask(athlete.address, "Large sponsorship", { value: largeAmount });
      await sponsorshipContract.connect(athlete).acceptTask(1);
      await sponsorshipContract.connect(athlete).submitDeliverable(1, ethers.keccak256(ethers.toUtf8Bytes("large")));
      await sponsorshipContract.connect(sponsor).approveTask(1);

      const task = await sponsorshipContract.getTask(1);
      expect(task.status).to.equal(3); // Completed
    });

    it("Should handle zero royalty fees", async function () {
      await playerNFT.mintLegacyNFT(athlete.address, recipient.address, "ipfs://test", 0);

      const [royaltyRecipient, royaltyAmount] = await playerNFT.royaltyInfo(1, 10000);
      expect(royaltyRecipient).to.equal(athlete.address);
      expect(royaltyAmount).to.equal(0);
    });
  });

  describe("Front-Running Protection", function () {
    it("Should maintain task order integrity", async function () {
      // Create multiple tasks rapidly
      const tasks = [];
      for (let i = 0; i < 5; i++) {
        const tx = await sponsorshipContract.connect(sponsor).createTask(
          athlete.address,
          `Task ${i}`,
          { value: ethers.parseEther("0.1") }
        );
        const receipt = await tx.wait();
        const taskId = receipt.logs[0].args[0];
        tasks.push(taskId);
      }

      // Verify task IDs are sequential
      for (let i = 0; i < tasks.length; i++) {
        expect(tasks[i]).to.equal(i + 1);
      }

      // Verify all tasks exist with correct data
      for (let i = 0; i < tasks.length; i++) {
        const task = await sponsorshipContract.getTask(tasks[i]);
        expect(task.taskId).to.equal(tasks[i]);
        expect(task.description).to.equal(`Task ${i}`);
      }
    });
  });

  describe("Denial of Service Protection", function () {
    it("Should handle large arrays in batch minting", async function () {
      const batchSize = 50; // Large batch
      const athletes = [];
      const recipients = [];
      const tokenURIs = [];
      const royaltyFees = [];

      for (let i = 0; i < batchSize; i++) {
        athletes.push(athlete.address);
        recipients.push(recipient.address);
        tokenURIs.push(`ipfs://test${i}`);
        royaltyFees.push(500);
      }

      const tx = await playerNFT.batchMintLegacyNFT(athletes, recipients, tokenURIs, royaltyFees);
      const receipt = await tx.wait();

      // Should complete without running out of gas
      expect(receipt.status).to.equal(1);
      expect(await playerNFT.totalSupply()).to.equal(batchSize);
    });

    it("Should handle many concurrent tasks", async function () {
      const numTasks = 20;
      const taskIds = [];

      for (let i = 0; i < numTasks; i++) {
        const tx = await sponsorshipContract.connect(sponsor).createTask(
          athlete.address,
          `Task ${i}`,
          { value: ethers.parseEther("0.1") }
        );
        const receipt = await tx.wait();
        taskIds.push(receipt.logs[0].args[0]);
      }

      expect(await sponsorshipContract.totalTasks()).to.equal(numTasks);

      // Should be able to query all tasks without issues
      for (const taskId of taskIds) {
        const task = await sponsorshipContract.getTask(taskId);
        expect(task.taskId).to.equal(taskId);
      }
    });
  });

  describe("Timestamp Dependence", function () {
    it("Should handle timestamp-based operations correctly", async function () {
      // Create task
      await sponsorshipContract.connect(sponsor).createTask(athlete.address, "Test task", { value: ethers.parseEther("0.1") });

      // Fast forward time
      await time.increase(86400); // 1 day

      // Complete task
      await sponsorshipContract.connect(athlete).acceptTask(1);
      await sponsorshipContract.connect(athlete).submitDeliverable(1, ethers.keccak256(ethers.toUtf8Bytes("test")));
      await sponsorshipContract.connect(sponsor).approveTask(1);

      const task = await sponsorshipContract.getTask(1);
      expect(task.completedAt).to.be.gt(task.createdAt);
    });
  });

  describe("Gas Limit Tests", function () {
    it("Should complete operations within reasonable gas limits", async function () {
      // Test NFT minting gas usage
      const mintTx = await playerNFT.mintLegacyNFT(athlete.address, recipient.address, "ipfs://test", 500);
      const mintReceipt = await mintTx.wait();
      expect(mintReceipt.gasUsed).to.be.lt(300000n); // Reasonable limit for minting

      // Test task creation gas usage
      const taskTx = await sponsorshipContract.connect(sponsor).createTask(
        athlete.address,
        "Test task",
        { value: ethers.parseEther("0.1") }
      );
      const taskReceipt = await taskTx.wait();
      expect(taskReceipt.gasUsed).to.be.lt(200000n); // Reasonable limit for task creation
    });
  });

  describe("Emergency Functions", function () {
    it("Should allow owner emergency withdrawal", async function () {
      // Send some ETH to the contract
      await owner.sendTransaction({ to: sponsorshipContract.target, value: ethers.parseEther("1") });

      const contractBalanceBefore = await ethers.provider.getBalance(sponsorshipContract.target);
      const ownerBalanceBefore = await ethers.provider.getBalance(owner.address);

      await sponsorshipContract.connect(owner).emergencyWithdraw();

      const contractBalanceAfter = await ethers.provider.getBalance(sponsorshipContract.target);
      const ownerBalanceAfter = await ethers.provider.getBalance(owner.address);

      expect(contractBalanceAfter).to.equal(0);
      expect(ownerBalanceAfter).to.be.gt(ownerBalanceBefore);
    });

    it("Should prevent non-owner emergency withdrawal", async function () {
      await owner.sendTransaction({ to: sponsorshipContract.target, value: ethers.parseEther("1") });

      await expect(
        sponsorshipContract.connect(attacker).emergencyWithdraw()
      ).to.be.revertedWith("Ownable: caller is not the owner");
    });
  });
});