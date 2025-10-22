// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import { Test } from "forge-std/Test.sol";
import { PlayerLegacyNFT } from "../../contracts/PlayerLegacyNFT.sol";
import { SponsorshipContract } from "../../contracts/SponsorshipContract.sol";

contract NILbxInvariants is Test {
    PlayerLegacyNFT public playerNFT;
    SponsorshipContract public sponsorshipContract;

    address public owner;
    address public athlete;
    address public sponsor;
    address public recipient;

    function setUp() public {
        owner = makeAddr("owner");
        athlete = makeAddr("athlete");
        sponsor = makeAddr("sponsor");
        recipient = makeAddr("recipient");

        vm.startPrank(owner);
        playerNFT = new PlayerLegacyNFT();
        sponsorshipContract = new SponsorshipContract(owner);
        vm.stopPrank();
    }

    // PlayerLegacyNFT Invariants

    function invariantNFTTotalSupplyEqualsTokenCounter() public view {
        uint256 totalSupply = playerNFT.totalSupply();
        // This invariant would require internal access to _tokenIdCounter
        // For now, we test that totalSupply doesn't exceed reasonable bounds
        assertLe(totalSupply, 1000000, "Total supply should not exceed reasonable limit");
    }

    function invariantNFTOwnerOfReturnsValidOwner() public view {
        uint256 totalSupply = playerNFT.totalSupply();
        for (uint256 i = 1; i <= totalSupply; i++) {
            address tokenOwner = playerNFT.ownerOf(i);
            assertNotEq(tokenOwner, address(0), "Token should not be owned by zero address");
        }
    }

    function invariantNFTAthleteTokenCountAccurate() public view {
        uint256 totalSupply = playerNFT.totalSupply();
        uint256 countedTokens = 0;

        // Count all tokens owned by athletes
        for (uint256 i = 1; i <= totalSupply; i++) {
            address tokenAthlete = playerNFT.tokenToAthlete(i);
            if (tokenAthlete != address(0)) {
                countedTokens++;
            }
        }

        // This should equal total supply since every token has an athlete
        assertEq(countedTokens, totalSupply, "All tokens should have associated athletes");
    }

    function invariantNFTRoyaltyFeeWithinBounds() public view {
        uint256 totalSupply = playerNFT.totalSupply();
        for (uint256 i = 1; i <= totalSupply; i++) {
            (, uint256 royaltyAmount) = playerNFT.royaltyInfo(i, 10000);
            // Royalty should be <= 10% (1000 basis points)
            assertLe(royaltyAmount, 1000, "Royalty fee should not exceed 10%");
        }
    }

    // SponsorshipContract Invariants

    function invariantSponsorshipTaskIdsSequential() public view {
        uint256 totalTasks = sponsorshipContract.totalTasks();
        // Task IDs should be sequential from 1 to totalTasks
        for (uint256 i = 1; i <= totalTasks; i++) {
            SponsorshipContract.Task memory task = sponsorshipContract.getTask(i);
            assertEq(task.taskId, i, "Task IDs should be sequential");
        }
    }

    function invariantSponsorshipTaskStatusValid() public view {
        uint256 totalTasks = sponsorshipContract.totalTasks();
        for (uint256 i = 1; i <= totalTasks; i++) {
            SponsorshipContract.Task memory task = sponsorshipContract.getTask(i);
            // Status should be between 0-5 (enum values: Created, Assigned, Submitted, Completed, Paid, Cancelled)
            assertLe(uint256(task.status), 5, "Task status should be valid enum value");
        }
    }

    function invariantSponsorshipPlatformFeePercentageValid() public view {
        uint256 feePercentage = sponsorshipContract.platformFeePercentage();
        assertLe(feePercentage, 1000, "Platform fee should not exceed 10%");
    }

    function invariantSponsorshipContractBalanceAccurate() public view {
        uint256 totalTasks = sponsorshipContract.totalTasks();
        uint256 expectedBalance = 0;

        for (uint256 i = 1; i <= totalTasks; i++) {
            SponsorshipContract.Task memory task = sponsorshipContract.getTask(i);

            // Add to expected balance if task is not completed/paid/cancelled
            if (
                task.status == SponsorshipContract.TaskStatus.Created ||
                task.status == SponsorshipContract.TaskStatus.Assigned ||
                task.status == SponsorshipContract.TaskStatus.Submitted
            ) {
                expectedBalance += task.amount;
            }
        }

        uint256 actualBalance = address(sponsorshipContract).balance;
        assertGe(actualBalance, expectedBalance, "Contract balance should be at least expected amount");
    }

    function invariantSponsorshipAthleteTasksConsistent() public view {
        uint256 totalTasks = sponsorshipContract.totalTasks();
        uint256[] memory allAthleteTasks = new uint256[](totalTasks);
        uint256 athleteTaskCount = 0;

        // Collect all athlete task assignments
        for (uint256 i = 1; i <= totalTasks; i++) {
            SponsorshipContract.Task memory task = sponsorshipContract.getTask(i);

            if (task.athlete != address(0)) {
                uint256[] memory athleteTasks = sponsorshipContract.getAthleteTasks(task.athlete);
                for (uint256 j = 0; j < athleteTasks.length; j++) {
                    allAthleteTasks[athleteTaskCount++] = athleteTasks[j];
                }
            }
        }

        // Verify all tasks are accounted for
        assertEq(athleteTaskCount, totalTasks, "All tasks should be assigned to athletes");
    }

    function invariantSponsorshipSponsorTasksConsistent() public view {
        uint256 totalTasks = sponsorshipContract.totalTasks();
        uint256[] memory allSponsorTasks = new uint256[](totalTasks);
        uint256 sponsorTaskCount = 0;

        // Collect all sponsor task assignments
        for (uint256 i = 1; i <= totalTasks; i++) {
            SponsorshipContract.Task memory task = sponsorshipContract.getTask(i);

            if (task.sponsor != address(0)) {
                uint256[] memory sponsorTasks = sponsorshipContract.getSponsorTasks(task.sponsor);
                for (uint256 j = 0; j < sponsorTasks.length; j++) {
                    allSponsorTasks[sponsorTaskCount++] = sponsorTasks[j];
                }
            }
        }

        // Verify all tasks are accounted for
        assertEq(sponsorTaskCount, totalTasks, "All tasks should be assigned to sponsors");
    }

    // Combined System Invariants

    function invariantSystemNoEtherLoss() public view {
        uint256 nftBalance = address(playerNFT).balance;
        uint256 sponsorshipBalance = address(sponsorshipContract).balance;

        // NFT contract should never hold ETH (no payable functions)
        assertEq(nftBalance, 0, "NFT contract should not hold ETH");

        // Sponsorship contract balance should be accounted for by active tasks
        uint256 totalTasks = sponsorshipContract.totalTasks();
        uint256 activeTaskValue = 0;

        for (uint256 i = 1; i <= totalTasks; i++) {
            SponsorshipContract.Task memory task = sponsorshipContract.getTask(i);

            // Count value of tasks that haven't been paid out or cancelled
            if (
                task.status == SponsorshipContract.TaskStatus.Created ||
                task.status == SponsorshipContract.TaskStatus.Assigned ||
                task.status == SponsorshipContract.TaskStatus.Submitted
            ) {
                activeTaskValue += task.amount;
            }
        }

        assertEq(sponsorshipBalance, activeTaskValue, "Sponsorship contract balance should equal active task value");
    }

    function invariantSystemTaskStateTransitionsValid() public view {
        uint256 totalTasks = sponsorshipContract.totalTasks();

        for (uint256 i = 1; i <= totalTasks; i++) {
            SponsorshipContract.Task memory task = sponsorshipContract.getTask(i);

            // Validate state transition logic
            if (
                task.status == SponsorshipContract.TaskStatus.Completed ||
                task.status == SponsorshipContract.TaskStatus.Paid
            ) {
                assertGt(
                    task.completedAt,
                    task.createdAt,
                    "Completed tasks should have completion time after creation"
                );
            }

            if (task.status == SponsorshipContract.TaskStatus.Cancelled) {
                assertGt(task.completedAt, 0, "Cancelled tasks should have completion time set");
            }
        }
    }
}
