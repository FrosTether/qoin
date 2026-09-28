// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title Frost Sub-Zero Time (FSZT)
 * @notice Fixed-supply ERC-20. The entire supply is minted once, at deployment,
 *         to `treasury`. There is NO mint function, NO owner, NO pause, and NO
 *         freeze — so no key can inflate the supply or move anyone's balance.
 *         What holders receive can never be diluted by the issuer.
 *
 * This replaces the earlier FrosTether.sol, which did not compile (a function
 * sat after the contract's closing brace) and carried an unused owner. Here the
 * supply is fixed and the contract is ownerless by construction.
 *
 * Holders may `burn` their own tokens. Nothing else changes supply.
 */
contract FrostEther {
    string public constant name = "Frost Sub-Zero Time";
    string public constant symbol = "FSZT";
    uint8 public constant decimals = 18;

    // Fixed forever. Change this constant before deploying if you want a
    // different total; it can never change after deployment.
    uint256 public constant INITIAL_SUPPLY = 25_000_000 * 1e18;

    uint256 public totalSupply;
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);

    /// @param treasury receives the entire initial supply (e.g. the wallet that
    ///        will fund the airdrop claim contract). Must be non-zero.
    constructor(address treasury) {
        require(treasury != address(0), "zero treasury");
        totalSupply = INITIAL_SUPPLY;
        balanceOf[treasury] = INITIAL_SUPPLY;
        emit Transfer(address(0), treasury, INITIAL_SUPPLY);
    }

    function transfer(address to, uint256 value) external returns (bool) {
        _transfer(msg.sender, to, value);
        return true;
    }

    function approve(address spender, uint256 value) external returns (bool) {
        allowance[msg.sender][spender] = value;
        emit Approval(msg.sender, spender, value);
        return true;
    }

    function transferFrom(address from, address to, uint256 value) external returns (bool) {
        uint256 allowed = allowance[from][msg.sender];
        if (allowed != type(uint256).max) {
            require(allowed >= value, "allowance");
            unchecked { allowance[from][msg.sender] = allowed - value; }
        }
        _transfer(from, to, value);
        return true;
    }

    /// @notice Destroy your own tokens. Reduces total supply; cannot be undone.
    function burn(uint256 value) external {
        uint256 bal = balanceOf[msg.sender];
        require(bal >= value, "balance");
        unchecked {
            balanceOf[msg.sender] = bal - value;
            totalSupply -= value;
        }
        emit Transfer(msg.sender, address(0), value);
    }

    function _transfer(address from, address to, uint256 value) internal {
        require(to != address(0), "zero to");
        uint256 bal = balanceOf[from];
        require(bal >= value, "balance");
        unchecked {
            balanceOf[from] = bal - value;
            balanceOf[to] += value;
        }
        emit Transfer(from, to, value);
    }
}
