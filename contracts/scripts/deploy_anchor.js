/**
 * Deploy ContractAnchor to target network.
 *
 * Usage:
 *   npx hardhat run scripts/deploy_anchor.js --network sepolia
 *   npx hardhat run scripts/deploy_anchor.js --network hardhat
 */
const { ethers } = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  const [deployer] = await ethers.getSigners();
  const network = await ethers.provider.getNetwork();

  console.log("=== ContractAnchor Deployment ===");
  console.log(`Network: ${network.name} (chainId: ${network.chainId})`);
  console.log(`Deployer: ${deployer.address}`);
  console.log(`Balance: ${ethers.formatEther(await ethers.provider.getBalance(deployer.address))} ETH`);
  console.log("");

  // Deploy
  console.log("Deploying ContractAnchor...");
  const ContractAnchor = await ethers.getContractFactory("ContractAnchor");
  const anchor = await ContractAnchor.deploy();
  await anchor.waitForDeployment();

  const address = await anchor.getAddress();
  console.log(`ContractAnchor deployed to: ${address}`);

  // Verify deployment
  const owner = await anchor.owner();
  console.log(`Owner: ${owner}`);
  console.log(`Contract anchor count: ${await anchor.contractAnchorCount()}`);

  // Save deployment info
  const deploymentFile = path.join(__dirname, "..", "deployment.json");
  let deployments = {};
  if (fs.existsSync(deploymentFile)) {
    deployments = JSON.parse(fs.readFileSync(deploymentFile, "utf8"));
  }

  deployments[`ContractAnchor_${network.chainId}`] = {
    address,
    deployer: deployer.address,
    chainId: Number(network.chainId),
    network: network.name,
    deployedAt: new Date().toISOString(),
    transactionHash: anchor.deploymentTransaction()?.hash || "unknown",
  };

  fs.writeFileSync(deploymentFile, JSON.stringify(deployments, null, 2));
  console.log(`\nDeployment info saved to ${deploymentFile}`);

  // Verification instructions
  if (network.chainId !== 31337n) {
    console.log("\n=== Verify on Etherscan ===");
    console.log(`npx hardhat verify --network ${network.name} ${address}`);
  }
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
