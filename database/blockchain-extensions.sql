-- ====================================
-- Blockchain Extensions for nilbx-db Schema
-- Adds blockchain-specific tables to the base nilbx-db schema
-- ====================================

USE blockchain_test_db;

-- ====================================
-- Enhanced Athletes Table (add blockchain fields if not exist)
-- ====================================
-- Add wallet_address to athletes if not exists
SELECT COUNT(*) INTO @wallet_column_exists FROM information_schema.columns 
WHERE table_schema = DATABASE() AND table_name = 'athletes' AND column_name = 'wallet_address';

SET @sql = IF(@wallet_column_exists = 0, 
    'ALTER TABLE athletes ADD COLUMN wallet_address VARCHAR(42) AFTER profile_picture, ADD INDEX idx_wallet_address (wallet_address)',
    'SELECT "wallet_address column already exists"');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- ====================================
-- Enhanced Sponsors Table (add blockchain fields if not exist)
-- ====================================
-- Add wallet_address to sponsors if not exists
SELECT COUNT(*) INTO @sponsor_wallet_exists FROM information_schema.columns 
WHERE table_schema = DATABASE() AND table_name = 'sponsors' AND column_name = 'wallet_address';

SET @sql = IF(@sponsor_wallet_exists = 0, 
    'ALTER TABLE sponsors ADD COLUMN wallet_address VARCHAR(42) AFTER company, ADD COLUMN industry VARCHAR(50) AFTER budget, ADD INDEX idx_sponsor_wallet_address (wallet_address)',
    'SELECT "sponsor wallet_address column already exists"');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- ====================================
-- Enhanced NFT Records Table (extend existing or create)
-- ====================================
-- Check if nft_records exists and has all required columns
SELECT COUNT(*) INTO @nft_table_exists FROM information_schema.tables 
WHERE table_schema = DATABASE() AND table_name = 'nft_records';

-- If table exists, add missing columns
IF @nft_table_exists > 0 THEN
    -- Add recipient_address if missing
    SELECT COUNT(*) INTO @recipient_exists FROM information_schema.columns 
    WHERE table_schema = DATABASE() AND table_name = 'nft_records' AND column_name = 'recipient_address';
    
    SET @sql = IF(@recipient_exists = 0, 
        'ALTER TABLE nft_records ADD COLUMN recipient_address VARCHAR(42) NOT NULL AFTER token_uri, ADD COLUMN block_number BIGINT AFTER transaction_hash, ADD COLUMN royalty_fee INT DEFAULT 0 AFTER metadata, ADD COLUMN status ENUM(\'pending\', \'confirmed\', \'failed\') DEFAULT \'pending\' AFTER royalty_fee',
        'SELECT "nft_records already has required columns"');
    PREPARE stmt FROM @sql;
    EXECUTE stmt;
    DEALLOCATE PREPARE stmt;
    
    -- Add missing indexes
    CREATE INDEX IF NOT EXISTS idx_recipient_address ON nft_records(recipient_address);
    CREATE INDEX IF NOT EXISTS idx_status ON nft_records(status);
    CREATE UNIQUE INDEX IF NOT EXISTS unique_contract_token ON nft_records(contract_address, token_id);
END IF;

-- ====================================
-- Sponsorship Tasks Table (blockchain-specific)
-- ====================================
CREATE TABLE IF NOT EXISTS sponsorship_tasks (
    id INT PRIMARY KEY AUTO_INCREMENT,
    task_id BIGINT UNIQUE NOT NULL, -- On-chain task ID
    sponsor_id INT NOT NULL,
    athlete_id INT NOT NULL,
    description TEXT NOT NULL,
    amount_eth DECIMAL(20,8) NOT NULL, -- ETH amount
    amount_wei VARCHAR(100), -- Wei amount (for precision)
    contract_address VARCHAR(42) NOT NULL,
    status ENUM('created', 'in_progress', 'completed', 'cancelled', 'disputed') DEFAULT 'created',
    transaction_hash VARCHAR(66),
    block_number BIGINT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME NULL,
    approved_by VARCHAR(42), -- Approver's wallet address
    metadata JSON,
    
    -- Foreign key constraints (link to existing tables)
    FOREIGN KEY (sponsor_id) REFERENCES sponsors(user_id) ON DELETE CASCADE,
    FOREIGN KEY (athlete_id) REFERENCES athletes(user_id) ON DELETE CASCADE,
    
    -- Indexes
    INDEX idx_task_id (task_id),
    INDEX idx_sponsor_id (sponsor_id),
    INDEX idx_athlete_id (athlete_id),
    INDEX idx_status (status),
    INDEX idx_contract_address (contract_address),
    INDEX idx_transaction_hash (transaction_hash),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ====================================
-- Smart Contract Events Table (for audit trail)
-- ====================================
CREATE TABLE IF NOT EXISTS contract_events (
    id INT PRIMARY KEY AUTO_INCREMENT,
    contract_address VARCHAR(42) NOT NULL,
    event_name VARCHAR(100) NOT NULL,
    transaction_hash VARCHAR(66) NOT NULL,
    block_number BIGINT NOT NULL,
    log_index INT NOT NULL,
    event_data JSON,
    decoded_data JSON,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    -- Indexes
    INDEX idx_contract_address (contract_address),
    INDEX idx_event_name (event_name),
    INDEX idx_transaction_hash (transaction_hash),
    INDEX idx_block_number (block_number),
    INDEX idx_timestamp (timestamp),
    
    -- Unique constraint to prevent duplicate events
    UNIQUE KEY unique_event (transaction_hash, log_index)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ====================================
-- Wallet Tracking Table
-- ====================================
CREATE TABLE IF NOT EXISTS wallet_transactions (
    id INT PRIMARY KEY AUTO_INCREMENT,
    wallet_address VARCHAR(42) NOT NULL,
    transaction_hash VARCHAR(66) NOT NULL,
    transaction_type ENUM('nft_mint', 'sponsorship_create', 'sponsorship_approve', 'payment_received', 'other') NOT NULL,
    related_table VARCHAR(50), -- 'nft_records', 'sponsorship_tasks', etc.
    related_id INT,
    amount_eth DECIMAL(20,8),
    gas_used BIGINT,
    gas_price VARCHAR(100),
    block_number BIGINT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    status ENUM('pending', 'confirmed', 'failed') DEFAULT 'pending',
    
    -- Indexes
    INDEX idx_wallet_address (wallet_address),
    INDEX idx_transaction_hash (transaction_hash),
    INDEX idx_transaction_type (transaction_type),
    INDEX idx_status (status),
    INDEX idx_timestamp (timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ====================================
-- Contract Configuration (separate from main app)
-- ====================================
CREATE TABLE IF NOT EXISTS contract_config (
    id INT PRIMARY KEY AUTO_INCREMENT,
    contract_name VARCHAR(100) NOT NULL,
    contract_address VARCHAR(42) NOT NULL,
    network VARCHAR(20) NOT NULL,
    abi_json JSON,
    deployment_block BIGINT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- Indexes
    INDEX idx_contract_name (contract_name),
    INDEX idx_contract_address (contract_address),
    INDEX idx_network (network),
    INDEX idx_is_active (is_active),
    
    -- Unique constraint
    UNIQUE KEY unique_contract_network (contract_name, network)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ====================================
-- Enhanced Analytics Events (extend existing)
-- ====================================
-- Rename existing analytics_events to blockchain_events for specificity
CREATE TABLE IF NOT EXISTS blockchain_events (
    id INT PRIMARY KEY AUTO_INCREMENT,
    event_type VARCHAR(50) NOT NULL,
    user_type ENUM('athlete', 'sponsor', 'fan', 'admin') NOT NULL,
    user_id INT,
    wallet_address VARCHAR(42),
    event_data JSON,
    transaction_hash VARCHAR(66),
    ip_address VARCHAR(45),
    user_agent TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    -- Indexes
    INDEX idx_event_type (event_type),
    INDEX idx_user_type (user_type),
    INDEX idx_user_id (user_id),
    INDEX idx_wallet_address (wallet_address),
    INDEX idx_timestamp (timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ====================================
-- API Request Logs (blockchain-specific)
-- ====================================
CREATE TABLE IF NOT EXISTS blockchain_api_logs (
    id INT PRIMARY KEY AUTO_INCREMENT,
    endpoint VARCHAR(255) NOT NULL,
    method VARCHAR(10) NOT NULL,
    request_data JSON,
    response_data JSON,
    status_code INT,
    execution_time_ms INT,
    user_address VARCHAR(42),
    ip_address VARCHAR(45),
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    -- Indexes
    INDEX idx_endpoint (endpoint),
    INDEX idx_status_code (status_code),
    INDEX idx_user_address (user_address),
    INDEX idx_timestamp (timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ====================================
-- NIL Fee Structure Tables
-- Implements competitive 6-8% total effective fee across deployment, transaction, and subscription fees
-- ====================================

-- Deployment Fees Table (off-chain service fees)
CREATE TABLE IF NOT EXISTS deployment_fees (
    id INT PRIMARY KEY AUTO_INCREMENT,
    contract_name VARCHAR(100) NOT NULL,
    contract_address VARCHAR(42),
    deployer_address VARCHAR(42) NOT NULL,
    deployment_fee_usd DECIMAL(10,2) NOT NULL, -- $10-15 per contract
    deployment_fee_eth DECIMAL(20,8), -- ETH equivalent at deployment time
    payment_method ENUM('stripe', 'crypto', 'wallet') DEFAULT 'stripe',
    transaction_hash VARCHAR(66),
    payment_status ENUM('pending', 'completed', 'failed', 'refunded') DEFAULT 'pending',
    deployed_at DATETIME NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- Indexes
    INDEX idx_deployer_address (deployer_address),
    INDEX idx_contract_address (contract_address),
    INDEX idx_payment_status (payment_status),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Subscription Plans Table (monthly monitoring/analytics fees)
CREATE TABLE IF NOT EXISTS subscription_plans (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    user_type ENUM('athlete', 'sponsor') NOT NULL,
    plan_name VARCHAR(50) NOT NULL DEFAULT 'monitoring', -- 'monitoring', 'analytics', 'premium'
    monthly_fee_usd DECIMAL(8,2) NOT NULL DEFAULT 15.00, -- $15/month base fee
    billing_cycle ENUM('monthly', 'quarterly', 'annual') DEFAULT 'monthly',
    payment_method ENUM('stripe', 'crypto') DEFAULT 'stripe',
    subscription_status ENUM('active', 'inactive', 'cancelled', 'past_due') DEFAULT 'active',
    current_period_start DATETIME NOT NULL,
    current_period_end DATETIME NOT NULL,
    next_billing_date DATETIME NOT NULL,
    stripe_subscription_id VARCHAR(100),
    crypto_wallet_address VARCHAR(42),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- Foreign key constraints
    FOREIGN KEY (user_id) REFERENCES athletes(user_id) ON DELETE CASCADE,
    
    -- Indexes
    INDEX idx_user_id (user_id),
    INDEX idx_user_type (user_type),
    INDEX idx_subscription_status (subscription_status),
    INDEX idx_next_billing_date (next_billing_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Premium Features Table (additional revenue from power users)
CREATE TABLE IF NOT EXISTS premium_features (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    user_type ENUM('athlete', 'sponsor') NOT NULL,
    feature_name VARCHAR(100) NOT NULL, -- 'custom_contract', 'priority_oracle', 'advanced_analytics', etc.
    feature_fee_usd DECIMAL(8,2) NOT NULL, -- $5-10 per feature
    payment_method ENUM('stripe', 'crypto', 'wallet') DEFAULT 'stripe',
    transaction_hash VARCHAR(66),
    payment_status ENUM('pending', 'completed', 'failed', 'refunded') DEFAULT 'pending',
    feature_config JSON, -- Configuration data for the feature
    activated_at DATETIME NULL,
    expires_at DATETIME NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- Foreign key constraints
    FOREIGN KEY (user_id) REFERENCES athletes(user_id) ON DELETE CASCADE,
    
    -- Indexes
    INDEX idx_user_id (user_id),
    INDEX idx_feature_name (feature_name),
    INDEX idx_payment_status (payment_status),
    INDEX idx_activated_at (activated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Fee Analytics Table (track total effective fees per deal)
CREATE TABLE IF NOT EXISTS fee_analytics (
    id INT PRIMARY KEY AUTO_INCREMENT,
    deal_id VARCHAR(100) NOT NULL, -- Could be sponsorship_task.id or custom deal identifier
    deal_type ENUM('sponsorship', 'nft_mint', 'custom_contract') NOT NULL,
    deal_value_usd DECIMAL(12,2) NOT NULL, -- Total deal value
    deployment_fee_usd DECIMAL(8,2) DEFAULT 0,
    transaction_fee_usd DECIMAL(8,2) DEFAULT 0,
    subscription_fee_usd DECIMAL(8,2) DEFAULT 0,
    premium_fee_usd DECIMAL(8,2) DEFAULT 0,
    total_effective_fee_usd DECIMAL(8,2) GENERATED ALWAYS AS (
        deployment_fee_usd + transaction_fee_usd + subscription_fee_usd + premium_fee_usd
    ) STORED,
    effective_fee_percentage DECIMAL(5,2) GENERATED ALWAYS AS (
        (deployment_fee_usd + transaction_fee_usd + subscription_fee_usd + premium_fee_usd) / deal_value_usd * 100
    ) STORED,
    user_id INT NOT NULL,
    user_type ENUM('athlete', 'sponsor') NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    -- Indexes
    INDEX idx_deal_id (deal_id),
    INDEX idx_deal_type (deal_type),
    INDEX idx_user_id (user_id),
    INDEX idx_created_at (created_at),
    INDEX idx_effective_fee_percentage (effective_fee_percentage)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ====================================
-- Triggers for Data Integrity
-- ====================================

-- Trigger to update wallet_transactions when NFT is minted
DROP TRIGGER IF EXISTS after_nft_insert;
DELIMITER $$
CREATE TRIGGER after_nft_insert 
    AFTER INSERT ON nft_records
    FOR EACH ROW
BEGIN
    INSERT INTO wallet_transactions (
        wallet_address, 
        transaction_hash, 
        transaction_type, 
        related_table, 
        related_id,
        block_number,
        status
    ) VALUES (
        NEW.recipient_address,
        NEW.transaction_hash,
        'nft_mint',
        'nft_records',
        NEW.id,
        NEW.block_number,
        NEW.status
    );
END$$
DELIMITER ;

-- Trigger to update wallet_transactions when sponsorship task is created
DROP TRIGGER IF EXISTS after_sponsorship_insert;
DELIMITER $$
CREATE TRIGGER after_sponsorship_insert 
    AFTER INSERT ON sponsorship_tasks
    FOR EACH ROW
BEGIN
    INSERT INTO wallet_transactions (
        wallet_address, 
        transaction_hash, 
        transaction_type, 
        related_table, 
        related_id,
        amount_eth,
        block_number,
        status
    ) VALUES (
        (SELECT wallet_address FROM sponsors WHERE user_id = NEW.sponsor_id),
        NEW.transaction_hash,
        'sponsorship_create',
        'sponsorship_tasks',
        NEW.id,
        NEW.amount_eth,
        NEW.block_number,
        CASE WHEN NEW.status = 'created' THEN 'confirmed' ELSE 'pending' END
    );
END$$
DELIMITER ;

-- ====================================
-- Views for Blockchain Analytics
-- ====================================

-- View for athlete blockchain portfolio
DROP VIEW IF EXISTS athlete_blockchain_portfolio;
CREATE VIEW athlete_blockchain_portfolio AS
SELECT 
    a.user_id as athlete_id,
    a.name as athlete_name,
    a.email as athlete_email,
    a.wallet_address,
    COUNT(DISTINCT n.id) as total_nfts,
    SUM(CASE WHEN n.status = 'confirmed' THEN 1 ELSE 0 END) as confirmed_nfts,
    COUNT(DISTINCT st.id) as sponsorship_tasks,
    SUM(CASE WHEN st.status = 'completed' THEN st.amount_eth ELSE 0 END) as total_earned_eth,
    AVG(n.royalty_fee) as avg_royalty_fee,
    MAX(n.minted_at) as latest_nft_mint,
    MAX(st.created_at) as latest_sponsorship
FROM athletes a
LEFT JOIN nft_records n ON a.user_id = n.athlete_id
LEFT JOIN sponsorship_tasks st ON a.user_id = st.athlete_id
WHERE a.wallet_address IS NOT NULL
GROUP BY a.user_id, a.name, a.email, a.wallet_address;

-- View for sponsor blockchain activity
DROP VIEW IF EXISTS sponsor_blockchain_activity;
CREATE VIEW sponsor_blockchain_activity AS
SELECT 
    s.user_id as sponsor_id,
    s.name as sponsor_name,
    s.company,
    s.wallet_address,
    s.budget,
    COUNT(st.id) as total_tasks,
    SUM(st.amount_eth) as total_committed_eth,
    SUM(CASE WHEN st.status = 'completed' THEN st.amount_eth ELSE 0 END) as total_paid_eth,
    COUNT(DISTINCT st.athlete_id) as unique_athletes_sponsored,
    AVG(st.amount_eth) as avg_task_amount
FROM sponsors s
LEFT JOIN sponsorship_tasks st ON s.user_id = st.sponsor_id
WHERE s.wallet_address IS NOT NULL
GROUP BY s.user_id, s.name, s.company, s.wallet_address, s.budget;

-- ====================================
-- Fee Analytics Views
-- ====================================

-- View for total effective fees by deal size
DROP VIEW IF EXISTS fee_analytics_by_deal_size;
CREATE VIEW fee_analytics_by_deal_size AS
SELECT 
    CASE 
        WHEN deal_value_usd < 500 THEN '< $500'
        WHEN deal_value_usd < 1000 THEN '$500 - $999'
        WHEN deal_value_usd < 2000 THEN '$1,000 - $1,999'
        WHEN deal_value_usd < 5000 THEN '$2,000 - $4,999'
        ELSE '$5,000+'
    END as deal_size_range,
    COUNT(*) as total_deals,
    AVG(deal_value_usd) as avg_deal_value,
    AVG(total_effective_fee_usd) as avg_total_fee,
    AVG(effective_fee_percentage) as avg_fee_percentage,
    SUM(total_effective_fee_usd) as total_revenue,
    MIN(effective_fee_percentage) as min_fee_percentage,
    MAX(effective_fee_percentage) as max_fee_percentage
FROM fee_analytics
GROUP BY 
    CASE 
        WHEN deal_value_usd < 500 THEN '< $500'
        WHEN deal_value_usd < 1000 THEN '$500 - $999'
        WHEN deal_value_usd < 2000 THEN '$1,000 - $1,999'
        WHEN deal_value_usd < 5000 THEN '$2,000 - $4,999'
        ELSE '$5,000+'
    END
ORDER BY MIN(deal_value_usd);

-- View for user fee analytics
DROP VIEW IF EXISTS user_fee_analytics;
CREATE VIEW user_fee_analytics AS
SELECT 
    fa.user_id,
    fa.user_type,
    CASE WHEN fa.user_type = 'athlete' THEN a.name ELSE s.name END as user_name,
    COUNT(fa.id) as total_deals,
    SUM(fa.deal_value_usd) as total_deal_value,
    SUM(fa.total_effective_fee_usd) as total_fees_paid,
    AVG(fa.effective_fee_percentage) as avg_fee_percentage,
    SUM(fa.deployment_fee_usd) as total_deployment_fees,
    SUM(fa.transaction_fee_usd) as total_transaction_fees,
    SUM(fa.subscription_fee_usd) as total_subscription_fees,
    SUM(fa.premium_fee_usd) as total_premium_fees,
    MAX(fa.created_at) as last_deal_date
FROM fee_analytics fa
LEFT JOIN athletes a ON fa.user_id = a.user_id AND fa.user_type = 'athlete'
LEFT JOIN sponsors s ON fa.user_id = s.user_id AND fa.user_type = 'sponsor'
GROUP BY fa.user_id, fa.user_type, user_name
ORDER BY total_fees_paid DESC;

-- ====================================
-- Cross-Table Indexes for Performance
-- ====================================

-- Composite indexes for common blockchain queries
CREATE INDEX IF NOT EXISTS idx_athlete_blockchain ON nft_records(athlete_id, status, minted_at);
CREATE INDEX IF NOT EXISTS idx_sponsor_blockchain ON sponsorship_tasks(sponsor_id, status, created_at);
CREATE INDEX IF NOT EXISTS idx_wallet_activity ON wallet_transactions(wallet_address, transaction_type, timestamp);

COMMIT;

SELECT 'Blockchain extensions successfully added to nilbx-db schema!' as status;