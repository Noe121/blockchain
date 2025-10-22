// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";
import "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";

/**
 * @title SponsorshipContract
 * @dev Contract for NIL-compliant sponsorship and marketing task payments
 * @notice This contract handles payments for completed marketing deliverables, NOT athletic performance
 */
contract SponsorshipContract is Ownable, ReentrancyGuard {
    using ECDSA for bytes32;

    enum TaskStatus {
        Created,
        Assigned,
        Submitted,
        Completed,
        Paid,
        Cancelled
    }

    struct Task {
        uint256 taskId;
        address sponsor;
        address athlete;
        uint256 amount;
        string description;
        TaskStatus status;
        uint256 createdAt;
        uint256 completedAt;
        bytes32 deliverableHash; // Hash of the completed deliverable
    }

    // Mappings
    mapping(uint256 => Task) public tasks;
    mapping(address => uint256[]) public athleteTasks;
    mapping(address => uint256[]) public sponsorTasks;
    mapping(address => uint256) public athleteEarnings;
    mapping(address => uint256) public sponsorSpending;

    // State variables
    uint256 private _taskIdCounter;
    uint256 public platformFeePercentage = 400; // 4% platform fee (increased from 2.5%
    // for competitive 6-8% total effective fee)
    address public platformFeeRecipient;

    // Events
    event TaskCreated(
        uint256 indexed taskId,
        address indexed sponsor,
        address indexed athlete,
        uint256 amount,
        string description
    );
    
    event TaskSubmitted(uint256 indexed taskId, address indexed athlete, bytes32 deliverableHash);
    
    event TaskCompleted(uint256 indexed taskId, address indexed athlete, address indexed sponsor);
    
    event PaymentReleased(
        uint256 indexed taskId,
        address indexed athlete,
        uint256 athleteAmount,
        uint256 platformFee
    );

    event TaskCancelled(uint256 indexed taskId, address indexed sponsor);

    // Custom errors
    error InvalidFeeRecipient();
    error InvalidAthleteAddress();
    error PaymentRequired();
    error InvalidDescription();
    error NotAssignedAthlete();
    error TaskNotAvailable();
    error OnlyAthleteCanSubmit();
    error TaskNotInProgress();
    error InvalidDeliverableHash();
    error OnlySponsorCanApprove();
    error TaskNotSubmitted();
    error TaskNotCompleted();
    error OnlySponsorCanCancel();
    error CannotCancelTask();
    error FeeTooHigh();
    error InvalidRecipient();
    error NotAuthorized();

    modifier onlyTaskParticipant(uint256 taskId) {
        Task memory task = tasks[taskId];
        if (msg.sender != task.sponsor && msg.sender != task.athlete) revert NotAuthorized();
        _;
    }

    constructor(address _platformFeeRecipient) {
        if (_platformFeeRecipient == address(0)) revert InvalidFeeRecipient();
        platformFeeRecipient = _platformFeeRecipient;
        _taskIdCounter = 1;
        _transferOwnership(msg.sender);
    }

    /**
     * @dev Create a new marketing task
     * @param athlete The athlete's address
     * @param description Description of the marketing deliverable
     */
    function createTask(address athlete, string memory description) external payable nonReentrant returns (uint256) {
        if (athlete == address(0)) revert InvalidAthleteAddress();
        if (msg.value == 0) revert PaymentRequired();
        if (bytes(description).length == 0) revert InvalidDescription();

        uint256 taskId = _taskIdCounter;
        _taskIdCounter++;

        tasks[taskId] = Task({
            taskId: taskId,
            sponsor: msg.sender,
            athlete: athlete,
            amount: msg.value,
            description: description,
            status: TaskStatus.Created,
            createdAt: block.timestamp,
            completedAt: 0,
            deliverableHash: bytes32(0)
        });

        athleteTasks[athlete].push(taskId);
        sponsorTasks[msg.sender].push(taskId);
        sponsorSpending[msg.sender] += msg.value;

        emit TaskCreated(taskId, msg.sender, athlete, msg.value, description);
        
        return taskId;
    }

    /**
     * @dev Athlete accepts a task
     * @param taskId The task ID to accept
     */
    function acceptTask(uint256 taskId) external {
        Task storage task = tasks[taskId];
        if (task.athlete != msg.sender) revert NotAssignedAthlete();
        if (task.status != TaskStatus.Created) revert TaskNotAvailable();

        task.status = TaskStatus.Assigned;
    }

    /**
     * @dev Athlete submits completed deliverable
     * @param taskId The task ID
     * @param deliverableHash Hash of the completed work
     */
    function submitDeliverable(uint256 taskId, bytes32 deliverableHash) external onlyTaskParticipant(taskId) {
        Task storage task = tasks[taskId];
        if (task.athlete != msg.sender) revert OnlyAthleteCanSubmit();
        if (task.status != TaskStatus.Assigned) revert TaskNotInProgress();
        if (deliverableHash == bytes32(0)) revert InvalidDeliverableHash();

        task.status = TaskStatus.Submitted;
        task.deliverableHash = deliverableHash;

        emit TaskSubmitted(taskId, msg.sender, deliverableHash);
    }

    /**
     * @dev Sponsor approves completed task and releases payment
     * @param taskId The task ID to approve
     */
    function approveTask(uint256 taskId) external onlyTaskParticipant(taskId) {
        Task storage task = tasks[taskId];
        if (task.sponsor != msg.sender) revert OnlySponsorCanApprove();
        if (task.status != TaskStatus.Submitted) revert TaskNotSubmitted();

        task.status = TaskStatus.Completed;
        task.completedAt = block.timestamp;

        emit TaskCompleted(taskId, task.athlete, msg.sender);
        
        // Auto-release payment
        _releasePayment(taskId);
    }

    /**
     * @dev Cancel a task (only if not submitted)
     * @param taskId The task ID to cancel
     */
    function cancelTask(uint256 taskId) external onlyTaskParticipant(taskId) {
        Task storage task = tasks[taskId];
        if (task.sponsor != msg.sender) revert OnlySponsorCanCancel();
        if (task.status != TaskStatus.Created && task.status != TaskStatus.Assigned) revert CannotCancelTask();

        // Update state before external calls
        task.status = TaskStatus.Cancelled;
        sponsorSpending[task.sponsor] -= task.amount;
        
        // Transfer refund (external call last)
        payable(task.sponsor).transfer(task.amount);

        emit TaskCancelled(taskId, msg.sender);
    }

    /**
     * @dev Emergency withdrawal (only owner)
     */
    function emergencyWithdraw() external onlyOwner {
        payable(owner()).transfer(address(this).balance);
    }

    /**
     * @dev Get task details
     * @param taskId The task ID
     * @return Task struct
     */
    function getTask(uint256 taskId) external view returns (Task memory) {
        return tasks[taskId];
    }

    /**
     * @dev Get tasks for an athlete
     * @param athlete The athlete's address
     * @return Array of task IDs
     */
    function getAthleteTasks(address athlete) external view returns (uint256[] memory) {
        return athleteTasks[athlete];
    }

    /**
     * @dev Get tasks for a sponsor
     * @param sponsor The sponsor's address
     * @return Array of task IDs
     */
    function getSponsorTasks(address sponsor) external view returns (uint256[] memory) {
        return sponsorTasks[sponsor];
    }

    /**
     * @dev Get total number of tasks created
     */
    function totalTasks() external view returns (uint256) {
        return _taskIdCounter - 1;
    }

    /**
     * @dev Release payment to athlete (with platform fee)
     * @param taskId The task ID
     */
    function _releasePayment(uint256 taskId) internal {
        Task storage task = tasks[taskId];
        if (task.status != TaskStatus.Completed) revert TaskNotCompleted();

        uint256 platformFee = (task.amount * platformFeePercentage) / 10000;
        uint256 athleteAmount = task.amount - platformFee;

        // Update state before external calls
        task.status = TaskStatus.Paid;
        athleteEarnings[task.athlete] += athleteAmount;

        // Transfer payments (external calls last)
        payable(task.athlete).transfer(athleteAmount);
        payable(platformFeeRecipient).transfer(platformFee);

        emit PaymentReleased(taskId, task.athlete, athleteAmount, platformFee);
    }
}
