const { ethers } = require("hardhat");
const hre = require("hardhat");

async function main() {
  console.log("Starting NILbx smart contract deployment...");

  // Get the deployer account
  const [deployer] = await hre.ethers.getSigners();
  console.log("Deploying contracts with account:", deployer.address);

  // Check deployer balance
  const balance = await hre.ethers.provider.getBalance(deployer.address);
  console.log("Account balance:", hre.ethers.formatEther(balance), "ETH");

  // Deploy PlayerLegacyNFT
  console.log("\n🚀 Deploying PlayerLegacyNFT...");
  const PlayerLegacyNFT = await hre.ethers.getContractFactory("PlayerLegacyNFT");
  const playerNFT = await PlayerLegacyNFT.deploy();
  await playerNFT.waitForDeployment();
  const nftAddress = await playerNFT.getAddress();
  console.log("✅ PlayerLegacyNFT deployed to:", nftAddress);

  // Deploy SponsorshipContract
  console.log("\n🚀 Deploying SponsorshipContract...");
  const SponsorshipContract = await hre.ethers.getContractFactory("SponsorshipContract");
  // Use deployer address as platform fee recipient for testing
  const sponsorshipContract = await SponsorshipContract.deploy(deployer.address);
  await sponsorshipContract.waitForDeployment();
  const sponsorshipAddress = await sponsorshipContract.getAddress();
  console.log("✅ SponsorshipContract deployed to:", sponsorshipAddress);
  console.log("  Platform fee recipient:", deployer.address);

  // Save deployment information
  const deploymentInfo = {
    network: hre.network.name,
    timestamp: new Date().toISOString(),
    deployer: deployer.address,
    contracts: {
      PlayerLegacyNFT: {
        address: nftAddress,
        transactionHash: playerNFT.deploymentTransaction()?.hash
      },
      SponsorshipContract: {
        address: sponsorshipAddress,
        transactionHash: sponsorshipContract.deploymentTransaction()?.hash
      }
    }
  };

  // Write deployment info to file
  const fs = require('fs');
  const path = require('path');
  
  const deploymentFile = path.join(__dirname, '..', 'deployment.json');
  fs.writeFileSync(deploymentFile, JSON.stringify(deploymentInfo, null, 2));
  
  console.log("\n📄 Deployment information saved to deployment.json");
  console.log("\n🎯 Deployment Summary:");
  console.log(`Network: ${deploymentInfo.network}`);
  console.log(`PlayerLegacyNFT: ${nftAddress}`);
  console.log(`SponsorshipContract: ${sponsorshipAddress}`);
  
  // Verify contracts on Etherscan (if on testnet/mainnet)
  if (hre.network.name !== "hardhat" && hre.network.name !== "localhost") {
    console.log("\n⏳ Waiting for block confirmations...");
    await playerNFT.deploymentTransaction()?.wait(5);
    await sponsorshipContract.deploymentTransaction()?.wait(5);
    
    console.log("\n🔍 Verifying contracts on Etherscan...");
    try {
      await hre.run("verify:verify", {
        address: nftAddress,
        constructorArguments: []
      });
      console.log("✅ PlayerLegacyNFT verified");
    } catch (error) {
      console.log("⚠️ PlayerLegacyNFT verification failed:", error.message);
    }

    try {
      await hre.run("verify:verify", {
        address: sponsorshipAddress,
        constructorArguments: []
      });
      console.log("✅ SponsorshipContract verified");
    } catch (error) {
      console.log("⚠️ SponsorshipContract verification failed:", error.message);
    }
  }

  console.log("\n🎉 Deployment completed successfully!");
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error("❌ Deployment failed:", error);
    process.exit(1);
  });