const { expect } = require("chai");
const { ethers } = require("hardhat");
const { loadFixture } = require("@nomicfoundation/hardhat-network-helpers");

describe("NILbx Smart Contracts - Fuzzing Tests", function () {
  let playerNFT, sponsorshipContract;
  let owner, athlete, sponsor, recipient;

  async function deployContractsFixture() {
    [owner, athlete, sponsor, recipient] = await ethers.getSigners();

    const PlayerLegacyNFT = await ethers.getContractFactory("PlayerLegacyNFT");
    playerNFT = await PlayerLegacyNFT.deploy();

    const SponsorshipContract = await ethers.getContractFactory("SponsorshipContract");
    sponsorshipContract = await SponsorshipContract.deploy(owner.address);

    return { playerNFT, sponsorshipContract, owner, athlete, sponsor, recipient };
  }

  beforeEach(async function () {
    ({ playerNFT, sponsorshipContract, athlete, sponsor, recipient } = await loadFixture(deployContractsFixture));
  });

  describe("PlayerLegacyNFT Fuzzing", function () {
    // Generate random royalty fees between 0-1000 (0-10%)
    function randomRoyaltyFee() {
      return Math.floor(Math.random() * 1001);
    }

    // Generate random addresses
    function randomAddress() {
      return ethers.Wallet.createRandom().address;
    }

    // Generate random token URIs
    function randomTokenURI() {
      const prefixes = ["ipfs://", "https://", "ar://", "data:"];
      const randomPrefix = prefixes[Math.floor(Math.random() * prefixes.length)];
      const randomHash = ethers.hexlify(ethers.randomBytes(32)).slice(2);
      return `${randomPrefix}${randomHash}`;
    }

    it("Should handle random royalty fees correctly", async function () {
      // Run multiple iterations with random fees
      for (let i = 0; i < 50; i++) {
        const royaltyFee = randomRoyaltyFee();
        const athleteAddr = randomAddress();
        const recipientAddr = randomAddress();
        const tokenURI = randomTokenURI();

        // Skip invalid royalty fees
        if (royaltyFee > 1000) continue;

        const tx = await playerNFT.mintLegacyNFT(athleteAddr, recipientAddr, tokenURI, royaltyFee);
        const receipt = await tx.wait();
        const tokenId = receipt.logs[0].args[0]; // Extract tokenId from event

        const [royaltyRecipient, royaltyAmount] = await playerNFT.royaltyInfo(tokenId, 10000);
        expect(royaltyRecipient).to.equal(athleteAddr);
        expect(royaltyAmount).to.equal(royaltyFee);
      }
    });

    it("Should handle random token URIs", async function () {
      for (let i = 0; i < 50; i++) {
        const tokenURI = randomTokenURI();
        const athleteAddr = randomAddress();
        const recipientAddr = randomAddress();
        const royaltyFee = Math.floor(Math.random() * 1001);

        if (royaltyFee > 1000) continue;

        const tx = await playerNFT.mintLegacyNFT(athleteAddr, recipientAddr, tokenURI, royaltyFee);
        const receipt = await tx.wait();
        const tokenId = receipt.logs[0].args[0];

        expect(await playerNFT.tokenURI(tokenId)).to.equal(tokenURI);
      }
    });

    it("Should handle batch minting with random data", async function () {
      const batchSize = Math.floor(Math.random() * 10) + 1; // 1-10 items
      const athletes = [];
      const recipients = [];
      const tokenURIs = [];
      const royaltyFees = [];

      for (let i = 0; i < batchSize; i++) {
        athletes.push(randomAddress());
        recipients.push(randomAddress());
        tokenURIs.push(randomTokenURI());
        royaltyFees.push(Math.floor(Math.random() * 1001));
      }

      await playerNFT.batchMintLegacyNFT(athletes, recipients, tokenURIs, royaltyFees);

      const totalSupply = await playerNFT.totalSupply();
      expect(totalSupply).to.equal(batchSize);
    });

    it("Should reject invalid royalty fees fuzzing", async function () {
      for (let i = 0; i < 20; i++) {
        const invalidFee = 1001 + Math.floor(Math.random() * 1000); // 1001-2000
        const athleteAddr = randomAddress();
        const recipientAddr = randomAddress();
        const tokenURI = randomTokenURI();

        await expect(
          playerNFT.mintLegacyNFT(athleteAddr, recipientAddr, tokenURI, invalidFee)
        ).to.be.revertedWith("Royalty fee too high");
      }
    });
  });

  describe("SponsorshipContract Fuzzing", function () {
    // Generate random payment amounts
    function randomPaymentAmount() {
      return ethers.parseEther((Math.random() * 10).toFixed(2)); // 0-10 ETH
    }

    // Generate random descriptions
    function randomDescription() {
      const words = ["social", "media", "promotion", "advertisement", "sponsorship", "marketing", "brand", "partnership"];
      const length = Math.floor(Math.random() * 5) + 1;
      let description = "";
      for (let i = 0; i < length; i++) {
        description += words[Math.floor(Math.random() * words.length)] + " ";
      }
      return description.trim();
    }

    it("Should handle random payment amounts", async function () {
      for (let i = 0; i < 30; i++) {
        const amount = randomPaymentAmount();
        const description = randomDescription();
        const athleteAddr = randomAddress();

        const tx = await sponsorshipContract.connect(sponsor).createTask(athleteAddr, description, { value: amount });
        const receipt = await tx.wait();

        // Extract taskId from event
        const taskId = receipt.logs[0].args[0];
        const task = await sponsorshipContract.getTask(taskId);

        expect(task.amount).to.equal(amount);
        expect(task.description).to.equal(description);
        expect(task.sponsor).to.equal(sponsor.address);
        expect(task.athlete).to.equal(athleteAddr);
      }
    });

    it("Should handle random task descriptions", async function () {
      for (let i = 0; i < 30; i++) {
        const description = randomDescription();
        const amount = ethers.parseEther("0.1");
        const athleteAddr = randomAddress();

        const tx = await sponsorshipContract.connect(sponsor).createTask(athleteAddr, description, { value: amount });
        const receipt = await tx.wait();
        const taskId = receipt.logs[0].args[0];
        const task = await sponsorshipContract.getTask(taskId);

        expect(task.description).to.equal(description);
      }
    });

    it("Should handle multiple concurrent tasks", async function () {
      const numTasks = Math.floor(Math.random() * 20) + 5; // 5-25 tasks
      const taskIds = [];

      for (let i = 0; i < numTasks; i++) {
        const amount = randomPaymentAmount();
        const description = `Task ${i}: ${randomDescription()}`;
        const athleteAddr = randomAddress();

        const tx = await sponsorshipContract.connect(sponsor).createTask(athleteAddr, description, { value: amount });
        const receipt = await tx.wait();
        const taskId = receipt.logs[0].args[0];
        taskIds.push(taskId);
      }

      expect(await sponsorshipContract.totalTasks()).to.equal(numTasks);

      // Verify all tasks exist
      for (const taskId of taskIds) {
        const task = await sponsorshipContract.getTask(taskId);
        expect(task.taskId).to.equal(taskId);
        expect(task.sponsor).to.equal(sponsor.address);
      }
    });

    it("Should handle random platform fee updates", async function () {
      const validFees = [0, 100, 250, 400, 500, 750, 1000];

      for (const fee of validFees) {
        await sponsorshipContract.connect(owner).updatePlatformFee(fee);
        expect(await sponsorshipContract.platformFeePercentage()).to.equal(fee);
      }

      // Test invalid fees
      const invalidFees = [1001, 1100, 2000, 10000];
      for (const fee of invalidFees) {
        await expect(
          sponsorshipContract.connect(owner).updatePlatformFee(fee)
        ).to.be.revertedWith("Fee too high");
      }
    });
  });

  describe("Gas Usage Fuzzing", function () {
    it("Should maintain reasonable gas usage with increasing token count", async function () {
      const gasUsages = [];

      for (let i = 1; i <= 20; i++) {
        const athleteAddr = randomAddress();
        const recipientAddr = randomAddress();
        const tokenURI = randomTokenURI();
        const royaltyFee = Math.floor(Math.random() * 1001);

        const tx = await playerNFT.mintLegacyNFT(athleteAddr, recipientAddr, tokenURI, royaltyFee);
        const receipt = await tx.wait();
        gasUsages.push(receipt.gasUsed);

        // Gas usage should remain relatively stable
        if (i > 5) {
          const avgGas = gasUsages.reduce((a, b) => a + b, 0n) / BigInt(gasUsages.length);
          expect(receipt.gasUsed).to.be.lt(avgGas * 2n); // Should not double
        }
      }
    });

    it("Should maintain reasonable gas usage for task operations", async function () {
      const createGasUsages = [];
      const approveGasUsages = [];

      for (let i = 0; i < 10; i++) {
        const amount = randomPaymentAmount();
        const description = randomDescription();
        const athleteAddr = randomAddress();

        // Create task
        const createTx = await sponsorshipContract.connect(sponsor).createTask(athleteAddr, description, { value: amount });
        const createReceipt = await createTx.wait();
        createGasUsages.push(createReceipt.gasUsed);

        const taskId = createReceipt.logs[0].args[0];

        // Complete workflow
        await sponsorshipContract.connect(athlete).acceptTask(taskId);
        await sponsorshipContract.connect(athlete).submitDeliverable(taskId, ethers.keccak256(ethers.toUtf8Bytes(`deliverable${i}`)));

        const approveTx = await sponsorshipContract.connect(sponsor).approveTask(taskId);
        const approveReceipt = await approveTx.wait();
        approveGasUsages.push(approveReceipt.gasUsed);
      }

      // Gas usage should be consistent
      const avgCreateGas = createGasUsages.reduce((a, b) => a + b, 0n) / BigInt(createGasUsages.length);
      const avgApproveGas = approveGasUsages.reduce((a, b) => a + b, 0n) / BigInt(approveGasUsages.length);

      expect(avgCreateGas).to.be.lt(150000n); // Reasonable gas limit
      expect(avgApproveGas).to.be.lt(100000n); // Reasonable gas limit
    });
  });
});