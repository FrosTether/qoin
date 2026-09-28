// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface IERC20 {
    function transfer(address to, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
}

/**
 * @title FrostAirdrop
 * @notice Trust-minimized Merkle claim for distributing a PRE-FUNDED pool of an
 *         ERC-20 (e.g. FSZT) to a fixed list of addresses.
 *
 * How it stays safe for the people claiming:
 *   - The contract can only pay out tokens it already holds. It cannot mint.
 *   - Each eligible address is fixed in the Merkle root at deploy time and can
 *     claim exactly once, exactly its listed amount.
 *   - Anyone may submit a claim on behalf of an address; the tokens always go to
 *     that address, so relaying is harmless (lets you gas-sponsor claims).
 *   - After `deadline`, whatever is left sweeps to `treasury` and nowhere else.
 *   - No owner, no upgrade, no pause. Nothing here can take a claimed balance.
 *
 * Leaf format matches OpenZeppelin's StandardMerkleTree with leaf types
 * ["address","uint256"]:  leaf = keccak256(bytes.concat(keccak256(abi.encode(account, amount))))
 * Build the tree with scripts/build_airdrop.mjs.
 */
contract FrostAirdrop {
    IERC20 public immutable token;
    bytes32 public immutable merkleRoot;
    uint256 public immutable deadline;   // unix time after which unclaimed tokens can be swept
    address public immutable treasury;   // receives the unclaimed remainder

    mapping(address => bool) public claimed;

    event Claimed(address indexed account, uint256 amount);
    event Swept(address indexed treasury, uint256 amount);

    /// @param _token      the ERC-20 being distributed (transfer this contract the pool after deploy)
    /// @param _merkleRoot root of the (account, amount) allowlist
    /// @param _claimWindow seconds the claim stays open, from deployment
    /// @param _treasury   where unclaimed tokens go after the window; must be non-zero
    constructor(address _token, bytes32 _merkleRoot, uint256 _claimWindow, address _treasury) {
        require(_token != address(0), "zero token");
        require(_treasury != address(0), "zero treasury");
        require(_merkleRoot != bytes32(0), "zero root");
        token = IERC20(_token);
        merkleRoot = _merkleRoot;
        deadline = block.timestamp + _claimWindow;
        treasury = _treasury;
    }

    function claim(address account, uint256 amount, bytes32[] calldata proof) external {
        require(block.timestamp <= deadline, "claim closed");
        require(!claimed[account], "already claimed");

        bytes32 leaf = keccak256(bytes.concat(keccak256(abi.encode(account, amount))));
        require(_verify(proof, merkleRoot, leaf), "invalid proof");

        claimed[account] = true;
        _safeTransfer(account, amount);
        emit Claimed(account, amount);
    }

    /// @notice After the window closes, send the remaining pool to the treasury.
    ///         Callable by anyone; destination is fixed at deploy.
    function sweepUnclaimed() external {
        require(block.timestamp > deadline, "claim still open");
        uint256 remaining = token.balanceOf(address(this));
        require(remaining > 0, "nothing to sweep");
        _safeTransfer(treasury, remaining);
        emit Swept(treasury, remaining);
    }

    // --- internals ---

    function _safeTransfer(address to, uint256 amount) internal {
        (bool ok, bytes memory data) = address(token).call(
            abi.encodeWithSelector(IERC20.transfer.selector, to, amount)
        );
        require(ok && (data.length == 0 || abi.decode(data, (bool))), "transfer failed");
    }

    /// @dev OpenZeppelin-compatible commutative (sorted-pair) Merkle verification.
    function _verify(bytes32[] calldata proof, bytes32 root, bytes32 leaf) internal pure returns (bool) {
        bytes32 computed = leaf;
        for (uint256 i = 0; i < proof.length; i++) {
            bytes32 p = proof[i];
            computed = computed <= p
                ? keccak256(abi.encodePacked(computed, p))
                : keccak256(abi.encodePacked(p, computed));
        }
        return computed == root;
    }
}
