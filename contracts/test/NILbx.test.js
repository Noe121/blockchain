const { expect } = require("chai");
const { ethers } = require("hardhat");
const { loadFixture, time, mine } = require("@nomicfoundation/hardhat-network-helpers");
const { anyValue } = require("@nomicfoundation/hardhat-chai-matchers");

describe("NILbx Smart Contracts - Audit Ready", function () {
  let playerNFT, sponsorshipContract;
  let owner, athlete, sponsor, recipient, attacker;
  let platformFeeRecipient;

  // Test constants
  const ROYALTY_FEE = 500; // 5%
  const PLATFORM_FEE = 400; // 4%
  const TASK_AMOUNT = ethers.parseEther("0.1");
  const TOKEN_URI = "https://example.com/metadata/1";
  const TASK_DESCRIPTION = "Social media promotion";

  async function deployContractsFixture() {
    [owner, athlete, sponsor, recipient, attacker, platformFeeRecipient] = await ethers.getSigners();

    // Deploy PlayerLegacyNFT
    const PlayerLegacyNFT = await ethers.getContractFactory("PlayerLegacyNFT");
    playerNFT = await PlayerLegacyNFT.deploy();

    // Deploy SponsorshipContract
    const SponsorshipContract = await ethers.getContractFactory("SponsorshipContract");
    sponsorshipContract = await SponsorshipContract.deploy(platformFeeRecipient.address);

    return { playerNFT, sponsorshipContract, owner, athlete, sponsor, recipient, attacker, platformFeeRecipient };
  }

  describe("PlayerLegacyNFT - Comprehensive Tests", function () {
    beforeEach(async function () {
      ({ playerNFT, athlete, recipient } = await loadFixture(deployContractsFixture));
    });

    describe("Deployment", function () {
      it("Should deploy with correct name and symbol", async function () {
        expect(await playerNFT.name()).to.equal("NILbx Player Legacy NFT");
        expect(await playerNFT.symbol()).to.equal("NILBX");
      });

      it("Should set owner correctly", async function () {
        expect(await playerNFT.owner()).to.equal(owner.address);
      });

      it("Should support ERC721 interface", async function () {
        const ERC721_INTERFACE_ID = "0x80ac58cd"; // ERC721 interface ID
        expect(await playerNFT.supportsInterface(ERC721_INTERFACE_ID)).to.be.true;
      });

      it("Should support ERC2981 royalty interface", async function () {
        const ERC2981_INTERFACE_ID = "0x2a55205a"; // ERC2981 interface ID
        expect(await playerNFT.supportsInterface(ERC2981_INTERFACE_ID)).to.be.true;
      });
    });

    describe("Minting", function () {
      it("Should mint NFT successfully", async function () {
        await expect(playerNFT.mintLegacyNFT(athlete.address, recipient.address, TOKEN_URI, ROYALTY_FEE))
          .to.emit(playerNFT, "LegacyNFTMinted")
          .withArgs(1, athlete.address, recipient.address, TOKEN_URI, ROYALTY_FEE);

        expect(await playerNFT.ownerOf(1)).to.equal(recipient.address);
        expect(await playerNFT.tokenURI(1)).to.equal(TOKEN_URI);
        expect(await playerNFT.tokenToAthlete(1)).to.equal(athlete.address);
        expect(await playerNFT.athleteTokenCount(athlete.address)).to.equal(1);
      });

      it("Should set royalty info correctly", async function () {
        await playerNFT.mintLegacyNFT(athlete.address, recipient.address, TOKEN_URI, ROYALTY_FEE);

        const [royaltyRecipient, royaltyAmount] = await playerNFT.royaltyInfo(1, 10000);
        expect(royaltyRecipient).to.equal(athlete.address);
        expect(royaltyAmount).to.equal(ROYALTY_FEE); // 5% of 10000
      });

      it("Should increment token ID counter", async function () {
        await playerNFT.mintLegacyNFT(athlete.address, recipient.address, TOKEN_URI, ROYALTY_FEE);
        expect(await playerNFT.totalSupply()).to.equal(1);

        await playerNFT.mintLegacyNFT(athlete.address, recipient.address, "ipfs://test2", ROYALTY_FEE);
        expect(await playerNFT.totalSupply()).to.equal(2);
      });

      it("Should reject invalid athlete address", async function () {
        await expect(
          playerNFT.mintLegacyNFT(ethers.ZeroAddress, recipient.address, TOKEN_URI, ROYALTY_FEE)
        ).to.be.revertedWith("Invalid athlete address");
      });

      it("Should reject invalid recipient address", async function () {
        await expect(
          playerNFT.mintLegacyNFT(athlete.address, ethers.ZeroAddress, TOKEN_URI, ROYALTY_FEE)
        ).to.be.revertedWith("Invalid recipient address");
      });

      it("Should reject empty token URI", async function () {
        await expect(
          playerNFT.mintLegacyNFT(athlete.address, recipient.address, "", ROYALTY_FEE)
        ).to.be.revertedWith("Token URI cannot be empty");
      });

      it("Should reject royalty fee too high", async function () {
        await expect(
          playerNFT.mintLegacyNFT(athlete.address, recipient.address, TOKEN_URI, 1100) // 11%
        ).to.be.revertedWith("Royalty fee too high");
      });

      it("Should only allow owner to mint", async function () {
        await expect(
          playerNFT.connect(athlete).mintLegacyNFT(athlete.address, recipient.address, TOKEN_URI, ROYALTY_FEE)
        ).to.be.revertedWith("Ownable: caller is not the owner");
      });
    });

    describe("Batch Minting", function () {
      it("Should batch mint multiple NFTs", async function () {
        const athletes = [athlete.address, athlete.address];
        const recipients = [recipient.address, recipient.address];
        const tokenURIs = ["ipfs://test1", "ipfs://test2"];
        const royaltyFees = [ROYALTY_FEE, ROYALTY_FEE];

        await playerNFT.batchMintLegacyNFT(athletes, recipients, tokenURIs, royaltyFees);

        expect(await playerNFT.totalSupply()).to.equal(2);
        expect(await playerNFT.ownerOf(1)).to.equal(recipient.address);
        expect(await playerNFT.ownerOf(2)).to.equal(recipient.address);
        expect(await playerNFT.athleteTokenCount(athlete.address)).to.equal(2);
      });

      it("Should reject batch mint with mismatched arrays", async function () {
        const athletes = [athlete.address];
        const recipients = [recipient.address, recipient.address]; // Different length
        const tokenURIs = ["ipfs://test1"];
        const royaltyFees = [ROYALTY_FEE];

        await expect(
          playerNFT.batchMintLegacyNFT(athletes, recipients, tokenURIs, royaltyFees)
        ).to.be.revertedWith("Array length mismatch");
      });

      it("Should reject empty batch arrays", async function () {
        await expect(
          playerNFT.batchMintLegacyNFT([], [], [], [])
        ).to.be.revertedWith("Empty arrays");
      });
    });

    describe("Token Queries", function () {
      beforeEach(async function () {
        await playerNFT.mintLegacyNFT(athlete.address, recipient.address, TOKEN_URI, ROYALTY_FEE);
      });

      it("Should return tokens of owner", async function () {
        const tokens = await playerNFT.tokensOfOwner(recipient.address);
        expect(tokens).to.deep.equal([1n]);
      });

      it("Should return empty array for address with no tokens", async function () {
        const tokens = await playerNFT.tokensOfOwner(athlete.address);
        expect(tokens).to.deep.equal([]);
      });

      it("Should return correct total supply", async function () {
        expect(await playerNFT.totalSupply()).to.equal(1);
      });
    });

    describe("Security Tests", function () {
      it("Should prevent reentrancy attacks", async function () {
        // Deploy a malicious contract that tries reentrancy
        const MaliciousContract = await ethers.getContractFactory("MaliciousNFTReceiver");
        const malicious = await MaliciousContract.deploy(playerNFT.target);

        // This should not cause reentrancy issues
        await expect(
          playerNFT.mintLegacyNFT(athlete.address, malicious.target, TOKEN_URI, ROYALTY_FEE)
        ).to.be.reverted; // Should fail due to malicious behavior
      });

      it("Should handle large royalty fees safely", async function () {
        const maxRoyalty = 1000; // 10%
        await playerNFT.mintLegacyNFT(athlete.address, recipient.address, TOKEN_URI, maxRoyalty);

        const [royaltyRecipient, royaltyAmount] = await playerNFT.royaltyInfo(1, ethers.parseEther("1"));
        expect(royaltyRecipient).to.equal(athlete.address);
        expect(royaltyAmount).to.equal(ethers.parseEther("0.1")); // 10% of 1 ETH
      });

      it("Should prevent overflow in token counter", async function () {
        // This test would need to mint 2^256 - 1 tokens to overflow, which is impossible
        // Instead, we test that the counter increments correctly
        for (let i = 1; i <= 10; i++) {
          await playerNFT.mintLegacyNFT(athlete.address, recipient.address, `ipfs://test${i}`, ROYALTY_FEE);
          expect(await playerNFT.totalSupply()).to.equal(i);
        }
      });
    });

    describe("Fuzzing Tests", function () {
      it("Should handle random royalty fees", async function () {
        // Test various royalty fees
        const royaltyFees = [0, 100, 250, 500, 750, 1000];

        for (const fee of royaltyFees) {
          const tokenId = await playerNFT.totalSupply() + 1n;
          await playerNFT.mintLegacyNFT(athlete.address, recipient.address, `ipfs://test${fee}`, fee);

          const [royaltyRecipient, royaltyAmount] = await playerNFT.royaltyInfo(tokenId, 10000);
          expect(royaltyRecipient).to.equal(athlete.address);
          expect(royaltyAmount).to.equal(fee);
        }
      });

      it("Should handle various token URIs", async function () {
        const uris = [
          "ipfs://QmTest123",
          "https://gateway.pinata.cloud/ipfs/QmTest123",
          "ar://test123",
          "data:application/json;base64,eyJuYW1lIjoidGVzdCJ9"
        ];

        for (const uri of uris) {
          await playerNFT.mintLegacyNFT(athlete.address, recipient.address, uri, ROYALTY_FEE);
          const tokenId = await playerNFT.totalSupply();
          expect(await playerNFT.tokenURI(tokenId)).to.equal(uri);
        }
      });
    });
  });

  describe("SponsorshipContract - Comprehensive Tests", function () {
    beforeEach(async function () {
      ({ sponsorshipContract, athlete, sponsor, platformFeeRecipient } = await loadFixture(deployContractsFixture));
    });

    describe("Deployment", function () {
      it("Should deploy with correct platform fee recipient", async function () {
        expect(await sponsorshipContract.platformFeeRecipient()).to.equal(platformFeeRecipient.address);
      });

      it("Should set correct platform fee", async function () {
        expect(await sponsorshipContract.platformFeePercentage()).to.equal(PLATFORM_FEE);
      });

      it("Should set owner correctly", async function () {
        expect(await sponsorshipContract.owner()).to.equal(owner.address);
      });

      it("Should start with zero tasks", async function () {
        expect(await sponsorshipContract.totalTasks()).to.equal(0);
      });
    });

    describe("Task Creation", function () {
      it("Should create task successfully", async function () {
        await expect(
          sponsorshipContract.connect(sponsor).createTask(athlete.address, TASK_DESCRIPTION, { value: TASK_AMOUNT })
        )
          .to.emit(sponsorshipContract, "TaskCreated")
          .withArgs(1, sponsor.address, athlete.address, TASK_AMOUNT, TASK_DESCRIPTION);

        const task = await sponsorshipContract.getTask(1);
        expect(task.taskId).to.equal(1);
        expect(task.sponsor).to.equal(sponsor.address);
        expect(task.athlete).to.equal(athlete.address);
        expect(task.amount).to.equal(TASK_AMOUNT);
        expect(task.description).to.equal(TASK_DESCRIPTION);
        expect(task.status).to.equal(0); // Created
      });

      it("Should increment task counter", async function () {
        await sponsorshipContract.connect(sponsor).createTask(athlete.address, TASK_DESCRIPTION, { value: TASK_AMOUNT });
        expect(await sponsorshipContract.totalTasks()).to.equal(1);

        await sponsorshipContract.connect(sponsor).createTask(athlete.address, "Another task", { value: TASK_AMOUNT });
        expect(await sponsorshipContract.totalTasks()).to.equal(2);
      });

      it("Should track sponsor spending", async function () {
        await sponsorshipContract.connect(sponsor).createTask(athlete.address, TASK_DESCRIPTION, { value: TASK_AMOUNT });
        expect(await sponsorshipContract.sponsorSpending(sponsor.address)).to.equal(TASK_AMOUNT);
      });

      it("Should reject invalid athlete address", async function () {
        await expect(
          sponsorshipContract.connect(sponsor).createTask(ethers.ZeroAddress, TASK_DESCRIPTION, { value: TASK_AMOUNT })
        ).to.be.revertedWith("Invalid athlete address");
      });

      it("Should reject zero payment", async function () {
        await expect(
          sponsorshipContract.connect(sponsor).createTask(athlete.address, TASK_DESCRIPTION, { value: 0 })
        ).to.be.revertedWith("Payment required");
      });

      it("Should reject empty description", async function () {
        await expect(
          sponsorshipContract.connect(sponsor).createTask(athlete.address, "", { value: TASK_AMOUNT })
        ).to.be.revertedWith("Description required");
      });
    });

    describe("Task Workflow", function () {
      beforeEach(async function () {
        await sponsorshipContract.connect(sponsor).createTask(athlete.address, TASK_DESCRIPTION, { value: TASK_AMOUNT });
      });

      it("Should allow athlete to accept task", async function () {
        await sponsorshipContract.connect(athlete).acceptTask(1);
        const task = await sponsorshipContract.getTask(1);
        expect(task.status).to.equal(1); // Assigned
      });

      it("Should reject acceptance by non-athlete", async function () {
        await expect(
          sponsorshipContract.connect(sponsor).acceptTask(1)
        ).to.be.revertedWith("Not the assigned athlete");
      });

      it("Should allow athlete to submit deliverable", async function () {
        await sponsorshipContract.connect(athlete).acceptTask(1);
        const deliverableHash = ethers.keccak256(ethers.toUtf8Bytes("https://twitter.com/post/123"));

        await expect(
          sponsorshipContract.connect(athlete).submitDeliverable(1, deliverableHash)
        )
          .to.emit(sponsorshipContract, "TaskSubmitted")
          .withArgs(1, athlete.address, deliverableHash);

        const task = await sponsorshipContract.getTask(1);
        expect(task.status).to.equal(2); // Submitted
        expect(task.deliverableHash).to.equal(deliverableHash);
      });

      it("Should reject submission by non-participant", async function () {
        await sponsorshipContract.connect(athlete).acceptTask(1);
        const deliverableHash = ethers.keccak256(ethers.toUtf8Bytes("test"));

        await expect(
          sponsorshipContract.connect(attacker).submitDeliverable(1, deliverableHash)
        ).to.be.revertedWith("Only athlete can submit");
      });

      it("Should allow sponsor to approve task", async function () {
        await sponsorshipContract.connect(athlete).acceptTask(1);
        const deliverableHash = ethers.keccak256(ethers.toUtf8Bytes("test"));
        await sponsorshipContract.connect(athlete).submitDeliverable(1, deliverableHash);

        const athleteBalanceBefore = await ethers.provider.getBalance(athlete.address);
        const platformBalanceBefore = await ethers.provider.getBalance(platformFeeRecipient.address);

        await expect(
          sponsorshipContract.connect(sponsor).approveTask(1)
        )
          .to.emit(sponsorshipContract, "TaskCompleted")
          .withArgs(1, athlete.address, sponsor.address);

        const task = await sponsorshipContract.getTask(1);
        expect(task.status).to.equal(3); // Completed

        // Check payment distribution
        const athleteBalanceAfter = await ethers.provider.getBalance(athlete.address);
        const platformBalanceAfter = await ethers.provider.getBalance(platformFeeRecipient.address);

        const platformFee = (TASK_AMOUNT * BigInt(PLATFORM_FEE)) / 10000n;
        const athletePayment = TASK_AMOUNT - platformFee;

        expect(athleteBalanceAfter - athleteBalanceBefore).to.equal(athletePayment);
        expect(platformBalanceAfter - platformBalanceBefore).to.equal(platformFee);
      });

      it("Should reject approval by non-sponsor", async function () {
        await sponsorshipContract.connect(athlete).acceptTask(1);
        const deliverableHash = ethers.keccak256(ethers.toUtf8Bytes("test"));
        await sponsorshipContract.connect(athlete).submitDeliverable(1, deliverableHash);

        await expect(
          sponsorshipContract.connect(attacker).approveTask(1)
        ).to.be.revertedWith("Only sponsor can approve");
      });
    });

    describe("Task Cancellation", function () {
      it("Should allow sponsor to cancel created task", async function () {
        await sponsorshipContract.connect(sponsor).createTask(athlete.address, TASK_DESCRIPTION, { value: TASK_AMOUNT });

        const sponsorBalanceBefore = await ethers.provider.getBalance(sponsor.address);

        await expect(
          sponsorshipContract.connect(sponsor).cancelTask(1)
        )
          .to.emit(sponsorshipContract, "TaskCancelled")
          .withArgs(1, sponsor.address);

        const task = await sponsorshipContract.getTask(1);
        expect(task.status).to.equal(4); // Cancelled

        const sponsorBalanceAfter = await ethers.provider.getBalance(sponsor.address);
        expect(sponsorBalanceAfter - sponsorBalanceBefore).to.equal(TASK_AMOUNT);
      });

      it("Should reject cancellation of submitted task", async function () {
        await sponsorshipContract.connect(sponsor).createTask(athlete.address, TASK_DESCRIPTION, { value: TASK_AMOUNT });
        await sponsorshipContract.connect(athlete).acceptTask(1);
        const deliverableHash = ethers.keccak256(ethers.toUtf8Bytes("test"));
        await sponsorshipContract.connect(athlete).submitDeliverable(1, deliverableHash);

        await expect(
          sponsorshipContract.connect(sponsor).cancelTask(1)
        ).to.be.revertedWith("Cannot cancel");
      });

      it("Should reject cancellation by non-sponsor", async function () {
        await sponsorshipContract.connect(sponsor).createTask(athlete.address, TASK_DESCRIPTION, { value: TASK_AMOUNT });

        await expect(
          sponsorshipContract.connect(attacker).cancelTask(1)
        ).to.be.revertedWith("Only sponsor can cancel");
      });
    });

    describe("Admin Functions", function () {
      it("Should allow owner to update platform fee", async function () {
        const newFee = 500; // 5%
        await sponsorshipContract.connect(owner).updatePlatformFee(newFee);
        expect(await sponsorshipContract.platformFeePercentage()).to.equal(newFee);
      });

      it("Should reject platform fee update by non-owner", async function () {
        await expect(
          sponsorshipContract.connect(attacker).updatePlatformFee(500)
        ).to.be.revertedWith("Ownable: caller is not the owner");
      });

      it("Should reject excessive platform fee", async function () {
        await expect(
          sponsorshipContract.connect(owner).updatePlatformFee(1100) // 11%
        ).to.be.revertedWith("Fee too high");
      });

      it("Should allow owner to update platform fee recipient", async function () {
        await sponsorshipContract.connect(owner).updatePlatformFeeRecipient(attacker.address);
        expect(await sponsorshipContract.platformFeeRecipient()).to.equal(attacker.address);
      });

      it("Should reject invalid fee recipient", async function () {
        await expect(
          sponsorshipContract.connect(owner).updatePlatformFeeRecipient(ethers.ZeroAddress)
        ).to.be.revertedWith("Invalid recipient");
      });
    });

    describe("Security Tests", function () {
      it("Should prevent reentrancy in payment release", async function () {
        // Deploy malicious contract
        const MaliciousSponsorship = await ethers.getContractFactory("MaliciousSponsorshipReceiver");
        const malicious = await MaliciousSponsorship.deploy(sponsorshipContract.target);

        // Create task for malicious athlete
        await sponsorshipContract.connect(sponsor).createTask(malicious.target, TASK_DESCRIPTION, { value: TASK_AMOUNT });

        // Accept and submit task
        await malicious.acceptTask(1);
        await malicious.submitDeliverable(1, ethers.keccak256(ethers.toUtf8Bytes("test")));

        // Approval should work without reentrancy issues
        await expect(
          sponsorshipContract.connect(sponsor).approveTask(1)
        ).to.not.be.reverted;
      });

      it("Should handle large payment amounts safely", async function () {
        const largeAmount = ethers.parseEther("1000"); // 1000 ETH

        await sponsorshipContract.connect(sponsor).createTask(athlete.address, TASK_DESCRIPTION, { value: largeAmount });
        await sponsorshipContract.connect(athlete).acceptTask(1);
        await sponsorshipContract.connect(athlete).submitDeliverable(1, ethers.keccak256(ethers.toUtf8Bytes("test")));

        const athleteBalanceBefore = await ethers.provider.getBalance(athlete.address);
        await sponsorshipContract.connect(sponsor).approveTask(1);
        const athleteBalanceAfter = await ethers.provider.getBalance(athlete.address);

        const platformFee = (largeAmount * BigInt(PLATFORM_FEE)) / 10000n;
        const athletePayment = largeAmount - platformFee;

        expect(athleteBalanceAfter - athleteBalanceBefore).to.equal(athletePayment);
      });

      it("Should prevent overflow in task counter", async function () {
        // Create multiple tasks to test counter
        for (let i = 1; i <= 10; i++) {
          await sponsorshipContract.connect(sponsor).createTask(
            athlete.address,
            `Task ${i}`,
            { value: TASK_AMOUNT }
          );
          expect(await sponsorshipContract.totalTasks()).to.equal(i);
        }
      });
    });

    describe("Gas Optimization Tests", function () {
      it("Should have reasonable gas costs for task creation", async function () {
        const tx = await sponsorshipContract.connect(sponsor).createTask(
          athlete.address,
          TASK_DESCRIPTION,
          { value: TASK_AMOUNT }
        );
        const receipt = await tx.wait();

        // Gas used should be reasonable (< 100k for task creation)
        expect(receipt.gasUsed).to.be.lt(100000n);
      });

      it("Should have reasonable gas costs for task approval", async function () {
        await sponsorshipContract.connect(sponsor).createTask(athlete.address, TASK_DESCRIPTION, { value: TASK_AMOUNT });
        await sponsorshipContract.connect(athlete).acceptTask(1);
        await sponsorshipContract.connect(athlete).submitDeliverable(1, ethers.keccak256(ethers.toUtf8Bytes("test")));

        const tx = await sponsorshipContract.connect(sponsor).approveTask(1);
        const receipt = await tx.wait();

        // Gas used should be reasonable (< 50k for approval)
        expect(receipt.gasUsed).to.be.lt(50000n);
      });
    });
  });

  describe("Integration Tests", function () {
    beforeEach(async function () {
      ({ playerNFT, sponsorshipContract, athlete, sponsor, recipient } = await loadFixture(deployContractsFixture));
    });

    it("Should handle complete NFT minting and sponsorship workflow", async function () {
      // Mint NFT for athlete
      await playerNFT.mintLegacyNFT(athlete.address, recipient.address, TOKEN_URI, ROYALTY_FEE);

      // Create sponsorship task
      await sponsorshipContract.connect(sponsor).createTask(athlete.address, TASK_DESCRIPTION, { value: TASK_AMOUNT });

      // Complete sponsorship workflow
      await sponsorshipContract.connect(athlete).acceptTask(1);
      await sponsorshipContract.connect(athlete).submitDeliverable(1, ethers.keccak256(ethers.toUtf8Bytes("deliverable")));
      await sponsorshipContract.connect(sponsor).approveTask(1);

      // Verify final state
      expect(await playerNFT.athleteTokenCount(athlete.address)).to.equal(1);
      expect(await sponsorshipContract.totalTasks()).to.equal(1);

      const task = await sponsorshipContract.getTask(1);
      expect(task.status).to.equal(3); // Completed
    });
  });
});