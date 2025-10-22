// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import "@openzeppelin/contracts/token/ERC721/extensions/ERC721URIStorage.sol";
import "@openzeppelin/contracts/token/ERC721/extensions/ERC721Royalty.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";

/**
 * @title PlayerLegacyNFT
 * @dev NFT contract for NIL (Name, Image, Likeness) compliant athlete legacy tokens
 * @notice This contract creates NFTs for athlete branding and legacy content, NOT performance-based payments
 */
contract PlayerLegacyNFT is ERC721URIStorage, ERC721Royalty, Ownable, ReentrancyGuard {
    uint256 private _tokenIdCounter;
    
    // Mapping from token ID to athlete address
    mapping(uint256 => address) public tokenToAthlete;
    
    // Mapping from athlete to their token count
    mapping(address => uint256) public athleteTokenCount;
    
    // Event emitted when a legacy NFT is minted
    event LegacyNFTMinted(
        uint256 indexed tokenId,
        address indexed athlete,
        address indexed recipient,
        string tokenURI,
        uint96 royaltyFee
    );

    constructor() ERC721("NILbx Player Legacy NFT", "NILBX") {
        _transferOwnership(msg.sender);
        _tokenIdCounter = 1;
    }

    /**
     * @dev Mint a new legacy NFT for an athlete
     * @param athlete The athlete's wallet address
     * @param recipient The address that will receive the NFT
     * @param _tokenURI The metadata URI for the NFT
     * @param royaltyFee The royalty percentage (in basis points, e.g., 500 = 5%)
     * @return The token ID of the newly minted NFT
     */
    function mintLegacyNFT(
        address athlete,
        address recipient,
        string memory _tokenURI,
        uint96 royaltyFee
    ) external onlyOwner nonReentrant returns (uint256) {
        return _mintLegacyNFT(athlete, recipient, _tokenURI, royaltyFee);
    }

    /**
     * @dev Internal function to mint a new legacy NFT for an athlete
     * @param athlete The athlete's wallet address
     * @param recipient The address that will receive the NFT
     * @param _tokenURI The metadata URI for the NFT
     * @param royaltyFee The royalty percentage (in basis points, e.g., 500 = 5%)
     * @return The token ID of the newly minted NFT
     */
    function _mintLegacyNFT(
        address athlete,
        address recipient,
        string memory _tokenURI,
        uint96 royaltyFee
    ) internal returns (uint256) {
        require(athlete != address(0), "Invalid athlete address");
        require(recipient != address(0), "Invalid recipient address");
        require(bytes(_tokenURI).length > 0, "Token URI cannot be empty");
        require(royaltyFee <= 1000, "Royalty fee too high"); // Max 10%

        uint256 tokenId = _tokenIdCounter;
        _tokenIdCounter++;

        // Mint the NFT
        _safeMint(recipient, tokenId);
        _setTokenURI(tokenId, _tokenURI);
        
        // Set royalty for the athlete
        _setTokenRoyalty(tokenId, athlete, royaltyFee);
        
        // Update mappings
        tokenToAthlete[tokenId] = athlete;
        athleteTokenCount[athlete]++;

        emit LegacyNFTMinted(tokenId, athlete, recipient, _tokenURI, royaltyFee);
        
        return tokenId;
    }

    /**
     * @dev Batch mint multiple NFTs for athletes
     * @param athletes Array of athlete wallet addresses
     * @param recipients Array of addresses that will receive the NFTs
     * @param _tokenURIs Array of metadata URIs for the NFTs
     * @param royaltyFees Array of royalty percentages for each NFT
     */
    function batchMintLegacyNFT(
        address[] memory athletes,
        address[] memory recipients,
        string[] memory _tokenURIs,
        uint96[] memory royaltyFees
    ) external onlyOwner nonReentrant returns (uint256[] memory) {
        require(athletes.length == recipients.length, "Array length mismatch");
        require(athletes.length == _tokenURIs.length, "Array length mismatch");
        require(athletes.length == royaltyFees.length, "Array length mismatch");
        require(athletes.length > 0, "Empty arrays");

        uint256[] memory tokenIds = new uint256[](athletes.length);

        for (uint256 i = 0; i < athletes.length; i++) {
            tokenIds[i] = _mintLegacyNFT(
                athletes[i],
                recipients[i],
                _tokenURIs[i],
                royaltyFees[i]
            );
        }

        return tokenIds;
    }

    /**
     * @dev Get all token IDs owned by an address
     * @param owner The address to query
     * @return Array of token IDs
     */
    function tokensOfOwner(address owner) external view returns (uint256[] memory) {
        uint256 tokenCount = balanceOf(owner);
        uint256[] memory tokenIds = new uint256[](tokenCount);
        uint256 index = 0;
        
        for (uint256 tokenId = 1; tokenId < _tokenIdCounter; tokenId++) {
            if (_ownerOf(tokenId) == owner) {
                tokenIds[index] = tokenId;
                index++;
            }
        }
        
        return tokenIds;
    }

    /**
     * @dev Get total number of minted tokens
     */
    function totalSupply() external view returns (uint256) {
        return _tokenIdCounter - 1;
    }

    /**
     * @dev Required override for ERC721URIStorage
     */
    function tokenURI(uint256 tokenId) public view override(ERC721, ERC721URIStorage) returns (string memory) {
        return super.tokenURI(tokenId);
    }

    /**
     * @dev Required override for royalty support
     */
    function supportsInterface(bytes4 interfaceId) public view override(ERC721URIStorage, ERC721Royalty) returns (bool) {
        return super.supportsInterface(interfaceId);
    }

    /**
     * @dev Required override when burning tokens
     */
    function _burn(uint256 tokenId) internal override(ERC721URIStorage, ERC721Royalty) {
        super._burn(tokenId);
    }
}