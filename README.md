# NILBx Blockchain Service

Serverless blockchain integration for the NILBx platform. Provides on-chain contract anchoring, automatic NFT minting for athlete contracts, and smart contract escrow for sponsorship deals. Deployed as AWS Lambda functions triggered by SNS contract lifecycle events.

## Architecture

```
                     SNS (contract events)
                            |
         +------------------+------------------+
         |                  |                  |
         v                  v                  v
+-----------------+ +-----------------+ +-----------------+
| Anchor Handler  | |  NFT Handler    | | Escrow Handler  |
| contract hash   | | party detect    | | createTask()    |
| proof hash      | | IPFS upload     | | approveTask()   |
| property hash   | | mint ERC721     | | 4% platform fee |
+--------+--------+ +--------+--------+ +--------+--------+
         |                   |                   |
         +----------+-------+----------+--------+
                    |                   |
         +----------v----------+   +----v-----------+
         | Blockchain Handler  |   | Contract Svc   |
         | (EthereumService)   |   | /anchor-result |
         | Web3 + Infura       |   |  callback      |
         | Secrets Manager     |   +----------------+
         +----------+----------+
                    |
    +---------------+------------------+
    |               |                  |
    v               v                  v
+----------+ +--------------+ +------------------+
| Contract | | PlayerLegacy | | Sponsorship      |
| Anchor   | | NFT (ERC721) | | Contract (Escrow)|
| 2.88 KiB | | + Royalties  | | + 4% Platform    |
+----------+ +--------------+ +------------------+
        Sepolia Testnet (Chain ID: 11155111)
```

## Smart Contracts

| Contract | File | Size | Gas/Op | Purpose |
|----------|------|------|--------|---------|
| ContractAnchor | `contracts/contracts/ContractAnchor.sol` | 2.88 KiB | ~118K | Hash anchoring for contracts, proofs, and property events |
| PlayerLegacyNFT | `contracts/contracts/PlayerLegacyNFT.sol` | 17.3 KiB | ~200K | ERC721 NFT with ERC2981 royalties for athlete contracts |
| SponsorshipContract | `contracts/contracts/SponsorshipContract.sol` | 12.2 KiB | ~100K | Task-based escrow with 4% platform fee |

All contracts use OpenZeppelin v4.9.6 (Ownable, ReentrancyGuard, ERC721, ERC2981). Compiled with Solidity ^0.8.19.

## Lambda Functions (7)

| Function | File | Trigger | Purpose |
|----------|------|---------|---------|
| blockchain_handler | `lambda/blockchain_handler.py` | API Gateway | Core EthereumService: mint, task, anchor, verify |
| ipfs_handler | `lambda/ipfs_handler.py` | API Gateway | IPFS metadata upload via Pinata |
| integration_handler | `lambda/integration_handler.py` | API Gateway | API orchestration between services |
| fee_management_handler | `lambda/main.py` | API Gateway | DynamoDB fee calculation and analytics |
| anchor_handler | `lambda/anchor_handler.py` | **SNS** | Contract + proof + property anchoring |
| nft_handler | `lambda/nft_handler.py` | **SNS** | Auto-mint PlayerLegacyNFT for athlete contracts |
| escrow_handler | `lambda/escrow_handler.py` | **SNS** | On-chain escrow create + release lifecycle |

### Supporting Modules
| File | Purpose |
|------|---------|
| `lambda/pending_mint_processor.py` | Scheduled: process queued NFT mints when athletes add wallets |
| `lambda/safety.py` | Contract address trust validation per chain_id |
| `lambda/kms_signer.py` | Signer abstraction (Secrets Manager now, KMS-ready) |
| `lambda/dynamodb_service.py` | DynamoDB single-table operations |
| `lambda/fee_service.py` | Fee calculation engine |
| `scripts/backfill_anchoring.py` | One-time backfill for existing executed contracts |

## Event Types Handled

| Event | Handler | Action |
|-------|---------|--------|
| `contract.executed` | anchor_handler | Anchor terms hash on ContractAnchor |
| `contract.executed` | nft_handler | Mint PlayerLegacyNFT if athlete party exists |
| `contract.executed` | escrow_handler | Create SponsorshipContract task if blockchain_escrow=true |
| `deliverable.proof.verified` | anchor_handler | Anchor proof hash for dispute resolution |
| `contract.fulfillment.completed` | escrow_handler | Release escrow funds to athlete |
| `property.construction.draw_approved` | anchor_handler | Anchor draw approval (Alabama audit trail) |
| `property.lease.created` | anchor_handler | Anchor lease terms |
| `property.lease.renewed` | anchor_handler | Anchor lease renewal |
| `property.lease.terminated` | anchor_handler | Anchor lease termination |
| `property.construction.lien_waiver_verified` | anchor_handler | Anchor waiver verification |

## Quick Start

### Prerequisites
- Node.js 18+ (for Hardhat)
- Python 3.11+ (for Lambda handlers)
- AWS CLI configured with appropriate credentials

### Smart Contract Development

```bash
cd contracts

# Install dependencies
npm install

# Compile contracts
npx hardhat compile

# Run tests (21 tests for ContractAnchor + existing suite)
npx hardhat test

# Deploy ContractAnchor to Sepolia
npx hardhat run scripts/deploy_anchor.js --network sepolia

# Verify on Etherscan
npx hardhat verify --network sepolia <DEPLOYED_ADDRESS>
```

### Lambda Development

```bash
cd lambda

# Create virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run tests (39 tests: anchor + NFT + escrow handlers)
python -m pytest tests/ -v

# Set environment for local testing
export INFURA_URL="https://sepolia.infura.io/v3/YOUR_PROJECT_ID"
export CHAIN_ID="11155111"
export NFT_CONTRACT_ADDRESS="0x..."
export SPONSORSHIP_CONTRACT_ADDRESS="0x..."
export ANCHOR_CONTRACT_ADDRESS="0x..."
```

### Backfill Existing Contracts

```bash
cd scripts

# Preview what would be anchored
python backfill_anchoring.py --dry-run

# Anchor up to 50 contracts with 5s delay between each
python backfill_anchoring.py --limit 50 --delay 5
```

## Project Structure

```
blockchain/
+-- contracts/                    # Smart contract sources (Hardhat)
|   +-- contracts/
|   |   +-- ContractAnchor.sol    # Hash anchoring (Phase 1)
|   |   +-- PlayerLegacyNFT.sol   # ERC721 + royalties
|   |   +-- SponsorshipContract.sol # Escrow + platform fee
|   +-- test/
|   |   +-- ContractAnchor.test.js # 21 tests
|   |   +-- NILbx.test.js         # NFT + sponsorship tests
|   +-- scripts/
|   |   +-- deploy_anchor.js      # ContractAnchor deployment
|   |   +-- deploy.js             # Full deployment
|   +-- hardhat.config.js
|   +-- package.json
+-- lambda/                       # AWS Lambda handlers
|   +-- blockchain_handler.py     # EthereumService (mint, task, anchor, verify)
|   +-- anchor_handler.py         # SNS: contract + proof + property anchoring
|   +-- nft_handler.py            # SNS: auto-mint NFT for athlete contracts
|   +-- escrow_handler.py         # SNS: on-chain escrow lifecycle
|   +-- pending_mint_processor.py # Scheduled: process queued mints
|   +-- ipfs_handler.py           # IPFS via Pinata
|   +-- integration_handler.py    # API orchestration
|   +-- main.py                   # FastAPI wrapper for fee management
|   +-- fee_service.py            # Fee calculation
|   +-- dynamodb_service.py       # DynamoDB operations
|   +-- safety.py                 # Contract trust validation
|   +-- kms_signer.py             # Signer abstraction
|   +-- requirements.txt
|   +-- tests/
|       +-- test_anchor_handler.py  # 15 tests
|       +-- test_nft_handler.py     # 13 tests
|       +-- test_escrow_handler.py  # 11 tests
+-- scripts/
|   +-- backfill_anchoring.py     # One-time backfill for existing contracts
+-- config/
|   +-- development.env
|   +-- production.env
```

## Security

| Concern | Implementation |
|---------|----------------|
| Private keys | AWS Secrets Manager — never in env vars or code |
| PII on-chain | NEVER stored — only SHA-256 hashes of terms/proofs |
| Gas control | Configurable `ANCHOR_GAS_LIMIT`, abort if exceeded |
| Idempotency | DynamoDB check before every on-chain write |
| Nonce races | Serialized via `asyncio.Lock` (no concurrent signing) |
| Contract trust | Checksum address validation + trusted allowlist per chain_id |
| Kill switches | `ANCHOR_ENABLED`, `NFT_MINT_ENABLED`, `BLOCKCHAIN_ESCROW_ENABLED` |
| Reentrancy | OpenZeppelin `ReentrancyGuard` on all smart contracts |
| Access control | `Ownable` on all write functions (platform deployer only) |

## Infrastructure (Terraform)

Terraform module: `NILbx-env/modules/lambda/blockchain/`

- **7 Lambda functions** (Python 3.12, 256MB, 120s timeout for SNS handlers)
- **3 SNS subscriptions** (anchor, NFT, escrow) to contract events topic
- **7 CloudWatch log groups** (14-day retention)
- **3 Secrets Manager secrets** (ethereum-keys, contract-abis, ipfs-keys)
- **DynamoDB table** (single-table design, pay-per-request, GSIs for wallet/analytics queries)
- **IAM role** with minimal permissions (logs, secrets, DynamoDB)

## Fee Structure

| Component | Fee | Notes |
|-----------|-----|-------|
| On-chain platform fee | 4% | SponsorshipContract auto-deduction |
| Off-chain processing | 2-4% | Stripe/PayPal via payment-service |
| Contract deployment | $10-15 | Per contract (1-2% of deal value) |
| NFT minting | Gas only | ~200K gas (~$0.50 on Sepolia) |
| Contract anchoring | Gas only | ~118K gas (~$0.30 on Sepolia) |

## Test Coverage

| Component | Tests | Status |
|-----------|-------|--------|
| ContractAnchor.sol (Hardhat) | 21 | Pass |
| Anchor handler (Python) | 15 | Pass |
| NFT handler (Python) | 13 | Pass |
| Escrow handler (Python) | 11 | Pass |
| **Total blockchain tests** | **60** | **All pass** |

Contract-service anchor callback tested separately (126 tests in contract-service suite).

## Chain Configuration

| Network | Chain ID | Status | Config |
|---------|----------|--------|--------|
| Sepolia testnet | 11155111 | Active (dev) | `CHAIN_ID=11155111` |
| Ethereum mainnet | 1 | Ready | `CHAIN_ID=1` |
| Polygon | 137 | Planned | `chain_id` field supports multi-chain |

Switch networks via `CHAIN_ID` env var. Each network uses separate deployer wallets and contract addresses.
