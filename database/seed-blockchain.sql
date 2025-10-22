-- ====================================
-- Blockchain Test Database Seed Data
-- ====================================

USE blockchain_test_db;

-- ====================================
-- Contract Configuration Seed Data
-- ====================================

INSERT INTO contract_config (
    contract_name, 
    contract_address, 
    network, 
    deployment_block, 
    is_active
) VALUES 
('PlayerLegacyNFT', '0x5FbDB2315678afecb367f032d93F642f64180aa3', 'sepolia', 1000000, TRUE),
('SponsorshipContract', '0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512', 'sepolia', 1000001, TRUE),
('PlayerLegacyNFT', '0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0', 'localhost', 1, TRUE),
('SponsorshipContract', '0xCf7Ed3AccA5a467e9e704C703E8D87F634fB0Fc9', 'localhost', 2, TRUE);

-- ====================================
-- Test Athletes Data
-- ====================================

INSERT INTO athletes (
    user_id,
    name, 
    email, 
    sport, 
    bio, 
    wallet_address, 
    profile_picture,
    social_media,
    stats
) VALUES 
(
    1,
    'Michael Jordan Basketball',
    'mjordan@test.com',
    'Basketball',
    'Legendary basketball player specializing in NFT legacy tokens',
    '0x70997970C51812dc3A010C7d01b50e0d17dc79C8',
    'https://example.com/profiles/mjordan.jpg',
    JSON_OBJECT(
        'twitter', '@mjordan_test',
        'instagram', '@mjordan_test',
        'tiktok', '@mjordan_test'
    ),
    JSON_OBJECT(
        'games_played', 1072,
        'points_per_game', 30.1,
        'championships', 6,
        'mvp_awards', 5
    )
),
(
    2,
    'Serena Williams Tennis',
    'swilliams@test.com',
    'Tennis',
    'Tennis champion exploring blockchain sponsorship opportunities',
    '0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC',
    'https://example.com/profiles/swilliams.jpg',
    JSON_OBJECT(
        'twitter', '@swilliams_test',
        'instagram', '@swilliams_test',
        'youtube', '@swilliams_test'
    ),
    JSON_OBJECT(
        'grand_slams', 23,
        'win_percentage', 85.6,
        'career_prize_money', 94518971,
        'weeks_at_number_one', 319
    )
),
(
    3,
    'Lionel Messi Football',
    'lmessi@test.com',
    'Football',
    'Soccer legend entering the NFT space',
    '0x90F79bf6EB2c4f870365E785982E1f101E93b906',
    'https://example.com/profiles/lmessi.jpg',
    JSON_OBJECT(
        'twitter', '@lmessi_test',
        'instagram', '@lmessi_test',
        'facebook', '@lmessi_test'
    ),
    JSON_OBJECT(
        'goals_scored', 672,
        'assists', 268,
        'ballon_dor', 7,
        'champions_league', 4
    )
);

-- ====================================
-- Test Sponsors Data
-- ====================================

INSERT INTO sponsors (
    user_id,
    name, 
    email, 
    company, 
    wallet_address, 
    budget, 
    industry,
    interests,
    contact_info
) VALUES 
(
    4,
    'Nike Partnership Manager',
    'partnerships@nike-test.com',
    'Nike',
    '0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65',
    500000.00,
    'Sportswear',
    JSON_ARRAY('basketball', 'tennis', 'football', 'brand-partnerships', 'nft-collections'),
    JSON_OBJECT(
        'phone', '+1-555-0001',
        'telegram', '@nike_partnerships',
        'discord', 'nike_official#1234'
    )
),
(
    5,
    'Adidas Blockchain Lead',
    'blockchain@adidas-test.com',
    'Adidas',
    '0x9965507D1a55bcC2695C58ba16FB37d819B0A4dc',
    750000.00,
    'Sportswear',
    JSON_ARRAY('football', 'running', 'blockchain-innovation', 'athlete-tokens'),
    JSON_OBJECT(
        'phone', '+1-555-0002',
        'telegram', '@adidas_blockchain',
        'discord', 'adidas_web3#5678'
    )
),
(
    6,
    'Crypto Sports Ventures',
    'investments@cryptosports-test.com',
    'Crypto Sports VC',
    '0x976EA74026E726554dB657fA54763abd0C3a0aa9',
    1000000.00,
    'Venture Capital',
    JSON_ARRAY('nft-investments', 'athlete-tokens', 'sports-defi', 'metaverse'),
    JSON_OBJECT(
        'phone', '+1-555-0003',
        'telegram', '@cryptosports_vc',
        'discord', 'cryptosports#9999'
    )
);

-- ====================================
-- Test NFT Records Data
-- ====================================

INSERT INTO nft_records (
    athlete_id,
    contract_address,
    token_id,
    token_uri,
    recipient_address,
    transaction_hash,
    block_number,
    blockchain_network,
    metadata,
    royalty_fee,
    status
) VALUES 
(
    1, -- Michael Jordan
    '0x5FbDB2315678afecb367f032d93F642f64180aa3',
    '1',
    'ipfs://QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG/1',
    '0x70997970C51812dc3A010C7d01b50e0d17dc79C8',
    '0xabc123def456789012345678901234567890123456789012345678901234567890',
    2500001,
    'sepolia',
    JSON_OBJECT(
        'name', 'Michael Jordan Legacy NFT #1',
        'description', 'Exclusive digital collectible featuring Michael Jordan career highlights',
        'image', 'ipfs://QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG/image.jpg',
        'attributes', JSON_ARRAY(
            JSON_OBJECT('trait_type', 'Sport', 'value', 'Basketball'),
            JSON_OBJECT('trait_type', 'Rarity', 'value', 'Legendary'),
            JSON_OBJECT('trait_type', 'Era', 'value', '1990s'),
            JSON_OBJECT('trait_type', 'Championship', 'value', '6')
        )
    ),
    500, -- 5% royalty
    'confirmed'
),
(
    2, -- Serena Williams
    '0x5FbDB2315678afecb367f032d93F642f64180aa3',
    '2',
    'ipfs://QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG/2',
    '0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC',
    '0xdef456789012345678901234567890123456789012345678901234567890abcd',
    2500002,
    'sepolia',
    JSON_OBJECT(
        'name', 'Serena Williams Champion NFT #2',
        'description', 'Tennis greatness immortalized in blockchain',
        'image', 'ipfs://QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG/serena.jpg',
        'attributes', JSON_ARRAY(
            JSON_OBJECT('trait_type', 'Sport', 'value', 'Tennis'),
            JSON_OBJECT('trait_type', 'Rarity', 'value', 'Epic'),
            JSON_OBJECT('trait_type', 'Grand Slams', 'value', '23'),
            JSON_OBJECT('trait_type', 'Surface', 'value', 'Hard Court')
        )
    ),
    750, -- 7.5% royalty
    'confirmed'
),
(
    3, -- Lionel Messi
    '0x5FbDB2315678afecb367f032d93F642f64180aa3',
    '3',
    'ipfs://QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG/3',
    '0x90F79bf6EB2c4f870365E785982E1f101E93b906',
    '0x789012345678901234567890123456789012345678901234567890123456abcd',
    2500003,
    'sepolia',
    JSON_OBJECT(
        'name', 'Lionel Messi GOAT NFT #3',
        'description', 'The greatest footballer of all time digital collectible',
        'image', 'ipfs://QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG/messi.jpg',
        'attributes', JSON_ARRAY(
            JSON_OBJECT('trait_type', 'Sport', 'value', 'Football'),
            JSON_OBJECT('trait_type', 'Rarity', 'value', 'Mythic'),
            JSON_OBJECT('trait_type', 'Ballon d\'Or', 'value', '7'),
            JSON_OBJECT('trait_type', 'Position', 'value', 'Forward')
        )
    ),
    1000, -- 10% royalty
    'confirmed'
);

-- ====================================
-- Test Sponsorship Tasks Data
-- ====================================

INSERT INTO sponsorship_tasks (
    task_id,
    sponsor_id,
    athlete_id,
    description,
    amount_eth,
    amount_wei,
    contract_address,
    status,
    transaction_hash,
    block_number,
    approved_by,
    metadata
) VALUES 
(
    1,
    1, -- Nike
    1, -- Michael Jordan
    'Create exclusive basketball content for Nike Air Jordan campaign',
    2.5,
    '2500000000000000000', -- 2.5 ETH in wei
    '0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512',
    'completed',
    '0x111222333444555666777888999000aaabbbcccdddeeefff000111222333444',
    2500010,
    '0x70997970C51812dc3A010C7d01b50e0d17dc79C8', -- MJ's address
    JSON_OBJECT(
        'content_type', 'video',
        'duration_seconds', 30,
        'platforms', JSON_ARRAY('instagram', 'twitter', 'youtube'),
        'deadline', '2024-12-31',
        'deliverables', JSON_ARRAY('4K video content', 'Social media posts', 'Behind-the-scenes')
    )
),
(
    2,
    2, -- Adidas
    2, -- Serena Williams
    'Tennis equipment endorsement and NFT collection collaboration',
    5.0,
    '5000000000000000000', -- 5.0 ETH in wei
    '0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512',
    'in_progress',
    '0x222333444555666777888999000aaabbbcccdddeeefff000111222333444555',
    2500020,
    NULL, -- Not yet approved
    JSON_OBJECT(
        'content_type', 'mixed',
        'campaign_duration_months', 6,
        'nft_collection_size', 100,
        'platforms', JSON_ARRAY('all_social', 'adidas_app', 'tennis_events'),
        'milestone_payments', JSON_ARRAY('1.0 ETH on start', '2.0 ETH mid-campaign', '2.0 ETH completion')
    )
),
(
    3,
    3, -- Crypto Sports VC
    3, -- Lionel Messi
    'Launch Messi Metaverse Experience and NFT drops',
    10.0,
    '10000000000000000000', -- 10.0 ETH in wei
    '0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512',
    'created',
    '0x333444555666777888999000aaabbbcccdddeeefff000111222333444555666',
    2500030,
    NULL, -- Pending approval
    JSON_OBJECT(
        'content_type', 'metaverse',
        'project_scope', 'Full metaverse stadium experience',
        'nft_drops', 3,
        'revenue_share_percentage', 15,
        'exclusivity_period_months', 12,
        'technical_requirements', JSON_ARRAY('VR compatibility', '3D avatar integration', 'Real-time match data')
    )
);

-- ====================================
-- Test Contract Events Data
-- ====================================

INSERT INTO contract_events (
    contract_address,
    event_name,
    transaction_hash,
    block_number,
    log_index,
    event_data,
    decoded_data
) VALUES 
(
    '0x5FbDB2315678afecb367f032d93F642f64180aa3',
    'Transfer',
    '0xabc123def456789012345678901234567890123456789012345678901234567890',
    2500001,
    0,
    JSON_OBJECT(
        'from', '0x0000000000000000000000000000000000000000',
        'to', '0x70997970C51812dc3A010C7d01b50e0d17dc79C8',
        'tokenId', '1'
    ),
    JSON_OBJECT(
        'event', 'NFT Minted',
        'athlete', 'Michael Jordan',
        'token_id', 1,
        'recipient', 'mjordan@test.com'
    )
),
(
    '0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512',
    'TaskCreated',
    '0x111222333444555666777888999000aaabbbcccdddeeefff000111222333444',
    2500010,
    0,
    JSON_OBJECT(
        'taskId', '1',
        'sponsor', '0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65',
        'athlete', '0x70997970C51812dc3A010C7d01b50e0d17dc79C8',
        'amount', '2500000000000000000'
    ),
    JSON_OBJECT(
        'event', 'Sponsorship Task Created',
        'sponsor_company', 'Nike',
        'athlete_name', 'Michael Jordan',
        'amount_eth', '2.5'
    )
);

-- ====================================
-- Test Blockchain Events (Analytics)
-- ====================================

INSERT INTO blockchain_events (
    event_type,
    user_type,
    user_id,
    wallet_address,
    event_data,
    transaction_hash,
    ip_address
) VALUES 
(
    'nft_mint_requested',
    'athlete',
    1,
    '0x70997970C51812dc3A010C7d01b50e0d17dc79C8',
    JSON_OBJECT(
        'contract_address', '0x5FbDB2315678afecb367f032d93F642f64180aa3',
        'token_id', '1',
        'gas_estimate', '250000',
        'royalty_fee', 500
    ),
    '0xabc123def456789012345678901234567890123456789012345678901234567890',
    '192.168.1.100'
),
(
    'sponsorship_task_created',
    'sponsor',
    1,
    '0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65',
    JSON_OBJECT(
        'task_id', '1',
        'athlete_id', '1',
        'amount_eth', '2.5',
        'description_length', 65
    ),
    '0x111222333444555666777888999000aaabbbcccdddeeefff000111222333444',
    '192.168.1.101'
),
(
    'wallet_connected',
    'athlete',
    2,
    '0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC',
    JSON_OBJECT(
        'wallet_type', 'MetaMask',
        'chain_id', '11155111',
        'balance_eth', '5.24'
    ),
    NULL,
    '192.168.1.102'
);

-- ====================================
-- Create Views for Common Queries
-- ====================================

-- View for athlete NFT portfolio
CREATE VIEW athlete_nft_portfolio AS
SELECT 
    a.id as athlete_id,
    a.name as athlete_name,
    a.email as athlete_email,
    a.wallet_address,
    COUNT(n.id) as total_nfts,
    SUM(CASE WHEN n.status = 'confirmed' THEN 1 ELSE 0 END) as confirmed_nfts,
    AVG(n.royalty_fee) as avg_royalty_fee,
    MAX(n.minted_at) as latest_mint_date,
    GROUP_CONCAT(DISTINCT n.contract_address) as contracts_used
FROM athletes a
LEFT JOIN nft_records n ON a.id = n.athlete_id
GROUP BY a.id, a.name, a.email, a.wallet_address;

-- View for sponsor sponsorship summary
CREATE VIEW sponsor_sponsorship_summary AS
SELECT 
    s.id as sponsor_id,
    s.name as sponsor_name,
    s.company,
    s.wallet_address,
    s.budget,
    COUNT(st.id) as total_tasks,
    SUM(st.amount_eth) as total_committed_eth,
    SUM(CASE WHEN st.status = 'completed' THEN st.amount_eth ELSE 0 END) as total_paid_eth,
    AVG(st.amount_eth) as avg_task_amount,
    COUNT(DISTINCT st.athlete_id) as unique_athletes_sponsored
FROM sponsors s
LEFT JOIN sponsorship_tasks st ON s.id = st.sponsor_id
GROUP BY s.id, s.name, s.company, s.wallet_address, s.budget;

-- View for recent blockchain activity
CREATE VIEW recent_blockchain_activity AS
SELECT 
    'nft_mint' as activity_type,
    n.minted_at as activity_date,
    a.name as athlete_name,
    n.recipient_address as wallet_address,
    CONCAT('NFT #', n.token_id) as description,
    NULL as amount_eth,
    n.transaction_hash,
    n.status
FROM nft_records n
JOIN athletes a ON n.athlete_id = a.id
WHERE n.minted_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)

UNION ALL

SELECT 
    'sponsorship' as activity_type,
    st.created_at as activity_date,
    a.name as athlete_name,
    s.wallet_address,
    CONCAT('Task: ', LEFT(st.description, 50), '...') as description,
    st.amount_eth,
    st.transaction_hash,
    st.status
FROM sponsorship_tasks st
JOIN athletes a ON st.athlete_id = a.id
JOIN sponsors s ON st.sponsor_id = s.id
WHERE st.created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)

ORDER BY activity_date DESC;

COMMIT;

-- ====================================
-- Success Message
-- ====================================
SELECT 'Blockchain test database successfully seeded with sample data!' as status;