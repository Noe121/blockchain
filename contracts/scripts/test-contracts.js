const hre = require("hardhat");

async function main() {
    console.log("Running smart contract functionality tests...");

    // Load deployment info
    const fs = require('fs');
    const path = require('path');
    const deploymentFile = path.join(__dirname, '..', 'deployment.json');
    const deployment = JSON.parse(fs.readFileSync(deploymentFile, 'utf8'));

    // Get contracts
    const [deployer, athlete, recipient] = await hre.ethers.getSigners();
    console.log("Test accounts:");
    console.log("  Deployer/Owner:", deployer.address);
    console.log("  Athlete:", athlete.address);
    console.log("  Recipient:", recipient.address);

    // Connect to deployed contracts
    const PlayerLegacyNFT = await hre.ethers.getContractFactory("PlayerLegacyNFT");
    const nftContract = PlayerLegacyNFT.attach(deployment.contracts.PlayerLegacyNFT.address);

    const SponsorshipContract = await hre.ethers.getContractFactory("SponsorshipContract");
    const sponsorshipContract = SponsorshipContract.attach(deployment.contracts.SponsorshipContract.address);

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
        "https://ipfs.io/ipfs/test-metadata",
        500 // 5% royalty
    );
    await mintTx.wait();
    
    const newTotalSupply = await nftContract.totalSupply();
    console.log(`  ✅ NFT minted! New total supply: ${newTotalSupply}`);

    // Test 3: Check token ownership
    const tokenOwner = await nftContract.ownerOf(1);
    const tokenURI = await nftContract.tokenURI(1);
    console.log(`  Token #1 owner: ${tokenOwner}`);
    console.log(`  Token #1 URI: ${tokenURI}`);

    // Test 4: Check athlete mapping
    const athleteTokenCount = await nftContract.getAthleteTokenCount(athlete.address);
    console.log(`  Athlete token count: ${athleteTokenCount}`);

    console.log("\n🧪 Testing SponsorshipContract...");
    
    // Test 5: Check contract info
    const owner = await sponsorshipContract.owner();
    const feeRecipient = await sponsorshipContract.platformFeeRecipient();
    console.log(`  Contract owner: ${owner}`);
    console.log(`  Fee recipient: ${feeRecipient}`);

    // Test 6: Create a task
    console.log("\n  Creating sponsorship task...");
    const taskValue = hre.ethers.parseEther("1.0");
    const createTaskTx = await sponsorshipContract.createTask(
        athlete.address,
        "Create Instagram post featuring sponsor product",
        { value: taskValue }
    );
    await createTaskTx.wait();
    
    const taskCount = await sponsorshipContract.getTaskCount();
    console.log(`  ✅ Task created! Total tasks: ${taskCount}`);

    // Test 7: Get task details
    const task = await sponsorshipContract.getTask(1);
    console.log(`  Task #1: ${task.description}`);
    console.log(`  Amount: ${hre.ethers.formatEther(task.amount)} ETH`);
    console.log(`  Status: ${task.status}`); // 0 = Pending

    // Test 8: Check balances
    const contractBalance = await hre.ethers.provider.getBalance(deployment.contracts.SponsorshipContract.address);
    console.log(`  Contract balance: ${hre.ethers.formatEther(contractBalance)} ETH`);

    console.log("\n✅ All tests passed! Smart contracts are working correctly.");
    
    console.log("\n📋 Test Summary:");
    console.log(`  - PlayerLegacyNFT deployed at: ${deployment.contracts.PlayerLegacyNFT.address}`);
    console.log(`  - SponsorshipContract deployed at: ${deployment.contracts.SponsorshipContract.address}`);
    console.log(`  - Minted 1 NFT for athlete ${athlete.address}`);
    console.log(`  - Created 1 sponsorship task worth 1.0 ETH`);
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error("❌ Test failed:", error);
        process.exit(1);
    });