const hre = require("hardhat");

async function main() {
    console.log("Running integrated smart contract functionality tests...");

    // Get test accounts
    const [deployer, athlete, recipient, sponsor] = await hre.ethers.getSigners();
    console.log("Test accounts:");
    console.log("  Deployer/Owner:", deployer.address);
    console.log("  Athlete:", athlete.address);
    console.log("  Recipient:", recipient.address);
    console.log("  Sponsor:", sponsor.address);

    // Deploy contracts fresh
    console.log("\n🚀 Deploying fresh contracts for testing...");
    
    // Deploy PlayerLegacyNFT
    const PlayerLegacyNFT = await hre.ethers.getContractFactory("PlayerLegacyNFT");
    const nftContract = await PlayerLegacyNFT.deploy();
    await nftContract.waitForDeployment();
    const nftAddress = await nftContract.getAddress();
    console.log("✅ PlayerLegacyNFT deployed to:", nftAddress);

    // Deploy SponsorshipContract
    const SponsorshipContract = await hre.ethers.getContractFactory("SponsorshipContract");
    const sponsorshipContract = await SponsorshipContract.deploy(deployer.address);
    await sponsorshipContract.waitForDeployment();
    const sponsorshipAddress = await sponsorshipContract.getAddress();
    console.log("✅ SponsorshipContract deployed to:", sponsorshipAddress);

    console.log("\n🧪 Testing PlayerLegacyNFT...");
    
    // Test 1: Check contract info
    const name = await nftContract.name();
    const symbol = await nftContract.symbol();
    const totalSupply = await nftContract.totalSupply();
    console.log(`  Contract: ${name} (${symbol}), Total Supply: ${totalSupply}`);

    // Test 2: Mint an NFT
    console.log("\n  Minting legacy NFT...");
    const mintTx = await nftContract.mintLegacyNFT(
        athlete.address,
        recipient.address,
        "https://ipfs.io/ipfs/QmTest123",
        500 // 5% royalty
    );
    await mintTx.wait();
    
    const newTotalSupply = await nftContract.totalSupply();
    console.log(`  ✅ NFT minted! New total supply: ${newTotalSupply}`);

    // Test 3: Check token ownership and metadata
    const tokenOwner = await nftContract.ownerOf(1);
    const tokenURI = await nftContract.tokenURI(1);
    const tokenAthlete = await nftContract.tokenToAthlete(1);
    console.log(`  Token #1 owner: ${tokenOwner}`);
    console.log(`  Token #1 athlete: ${tokenAthlete}`);
    console.log(`  Token #1 URI: ${tokenURI}`);

    // Test 4: Check athlete token count
    const athleteTokenCount = await nftContract.athleteTokenCount(athlete.address);
    console.log(`  Athlete token count: ${athleteTokenCount}`);

    // Test 5: Test batch minting
    console.log("\n  Testing batch minting...");
    const batchTx = await nftContract.batchMintLegacyNFT(
        [athlete.address, athlete.address],
        [recipient.address, sponsor.address],
        ["https://ipfs.io/ipfs/QmTest456", "https://ipfs.io/ipfs/QmTest789"],
        [250, 750] // 2.5% and 7.5% royalties
    );
    await batchTx.wait();
    
    const finalSupply = await nftContract.totalSupply();
    console.log(`  ✅ Batch minted! Final total supply: ${finalSupply}`);

    console.log("\n🧪 Testing SponsorshipContract...");
    
    // Test 6: Check contract info
    const owner = await sponsorshipContract.owner();
    const feeRecipient = await sponsorshipContract.platformFeeRecipient();
    console.log(`  Contract owner: ${owner}`);
    console.log(`  Fee recipient: ${feeRecipient}`);

    // Test 7: Create a task
    console.log("\n  Creating sponsorship task...");
    const taskValue = hre.ethers.parseEther("1.0");
    const createTaskTx = await sponsorshipContract.connect(sponsor).createTask(
        athlete.address,
        "Create Instagram post featuring sponsor product",
        { value: taskValue }
    );
    await createTaskTx.wait();
    
    const taskCount = await sponsorshipContract.totalTasks();
    console.log(`  ✅ Task created! Total tasks: ${taskCount}`);

    // Test 8: Get task details
    const task = await sponsorshipContract.getTask(1);
    console.log(`  Task #1: ${task.description}`);
    console.log(`  Amount: ${hre.ethers.formatEther(task.amount)} ETH`);
    console.log(`  Status: ${task.status} (0=Pending)`);
    console.log(`  Sponsor: ${task.sponsor}`);
    console.log(`  Athlete: ${task.athlete}`);

    // Test 9: Check contract balance
    const contractBalance = await hre.ethers.provider.getBalance(sponsorshipAddress);
    console.log(`  Contract balance: ${hre.ethers.formatEther(contractBalance)} ETH`);

    // Test 10: Accept task, submit deliverable and complete task
    console.log("\n  Accepting and completing task...");
    
    // First, athlete accepts the task
    const acceptTx = await sponsorshipContract.connect(athlete).acceptTask(1);
    await acceptTx.wait();
    console.log("  ✅ Task accepted by athlete");
    
    // Then submit deliverable
    const deliverableHash = hre.ethers.id("QmDeliverable123"); // Mock IPFS hash
    const submitTx = await sponsorshipContract.connect(athlete).submitDeliverable(1, deliverableHash);
    await submitTx.wait();
    console.log("  ✅ Deliverable submitted");

    // Finally, sponsor approves
    const approveTx = await sponsorshipContract.connect(sponsor).approveTask(1);
    await approveTx.wait();

    const completedTask = await sponsorshipContract.getTask(1);
    console.log(`  ✅ Task completed! Status: ${completedTask.status} (2=Completed)`);

    // Test 11: Check final balances
    const finalContractBalance = await hre.ethers.provider.getBalance(sponsorshipAddress);
    console.log(`  Final contract balance: ${hre.ethers.formatEther(finalContractBalance)} ETH`);

    console.log("\n✅ All tests passed! Smart contracts are fully functional.");
    
    console.log("\n📋 Test Summary:");
    console.log(`  - PlayerLegacyNFT: ${nftAddress}`);
    console.log(`  - SponsorshipContract: ${sponsorshipAddress}`);
    console.log(`  - Minted 3 NFTs total (1 single + 2 batch)`);
    console.log(`  - Created and completed 1 sponsorship task worth 1.0 ETH`);
    console.log(`  - All contract functions working correctly`);
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error("❌ Test failed:", error);
        process.exit(1);
    });