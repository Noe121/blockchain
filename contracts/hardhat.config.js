require("dotenv").config();
require("@nomicfoundation/hardhat-toolbox");
require("@nomicfoundation/hardhat-verify");
require("hardhat-contract-sizer");
require("hardhat-gas-reporter");
require("solidity-coverage");
require("@typechain/hardhat");

/** @type import('hardhat/config').HardhatUserConfig */
module.exports = {
  solidity: {
    version: "0.8.19",
    settings: {
      optimizer: {
        enabled: process.env.NODE_ENV === "production",
        runs: process.env.NODE_ENV === "production" ? 200 : 1,
        details: {
          yul: false, // Disable Yul optimizer for better debugging
        }
      },
      evmVersion: "paris",
      viaIR: false,
      metadata: {
        bytecodeHash: process.env.NODE_ENV === "production" ? "ipfs" : "none"
      }
    }
  },
  networks: {
    hardhat: {
      chainId: 31337,
      allowUnlimitedContractSize: true,
      forking: {
        url: process.env.MAINNET_RPC_URL || "https://eth-mainnet.g.alchemy.com/v2/demo",
        enabled: process.env.FORKING_ENABLED === "true"
      },
      accounts: {
        mnemonic: "test test test test test test test test test test test junk",
        accountsBalance: "1000000000000000000000" // 1000 ETH
      }
    },
    sepolia: {
      url: process.env.SEPOLIA_RPC_URL || process.env.INFURA_URL,
      accounts: process.env.PRIVATE_KEY ? [process.env.PRIVATE_KEY] : [],
      gasPrice: 20000000000, // 20 gwei
      verify: {
        etherscan: {
          apiKey: process.env.ETHERSCAN_API_KEY
        }
      }
    },
    mainnet: {
      url: process.env.MAINNET_RPC_URL,
      accounts: process.env.PRIVATE_KEY ? [process.env.PRIVATE_KEY] : [],
      gasPrice: 30000000000, // 30 gwei
      verify: {
        etherscan: {
          apiKey: process.env.ETHERSCAN_API_KEY
        }
      }
    }
  },
  gasReporter: {
    enabled: process.env.REPORT_GAS !== undefined,
    currency: "USD",
    gasPrice: 20,
    coinmarketcap: process.env.COINMARKETCAP_API_KEY,
    token: "ETH",
    gasPriceApi: "https://api.etherscan.io/api?module=proxy&action=eth_gasPrice",
    showTimeSpent: true,
    showMethodSig: true,
    onlyCalledMethods: false
  },
  contractSizer: {
    alphaSort: true,
    disambiguatePaths: false,
    runOnCompile: true,
    strict: true,
    only: [":PlayerLegacyNFT$", ":SponsorshipContract$"]
  },
  etherscan: {
    apiKey: process.env.ETHERSCAN_API_KEY
  },
  typechain: {
    outDir: "typechain-types",
    target: "ethers-v6"
  },
  paths: {
    sources: "./contracts",
    tests: "./test",
    cache: "./cache",
    artifacts: "./artifacts"
  },
  mocha: {
    timeout: 40000,
    bail: true,
    reporter: process.env.CI ? "spec" : "nyan"
  }
};