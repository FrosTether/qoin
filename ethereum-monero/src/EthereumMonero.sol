// SPDX-License-Identifier: UNLICENSED
// Ethereum Monero (EXMR): Monero bridged to Ethereum Classic.
// ERC-20 core from the Qoin Maker 0.1.0 template; bridge functions added by hand.
// Provided AS IS. Have it reviewed before mainnet.
// Not affiliated with the Monero Project, Ethereum Classic, or the Ethereum Foundation.
pragma solidity ^0.8.24;

/// @title Ethereum Monero (EXMR)
/// @notice ERC-20 on Ethereum Classic for XMR held in the bridge vault. 1 EXMR = 1 XMR.
///         Decimals match Monero's 12, so 1 raw unit is exactly 1 piconero.
/// @dev Custodial bridge. `minter` (the relayer's hot key) mints against confirmed Monero
///      deposits and settles burns. `owner` (keep it cold) can only replace the minter and
///      set the daily mint limit. No one can freeze, seize, or tax a balance.
contract EthereumMonero {
    string public constant name = "Ethereum Monero";
    string public constant symbol = "EXMR";
    uint8 public constant decimals = 12;
    uint256 public constant MINT_WINDOW = 1 days;

    enum BurnState {
        None,
        Pending,
        Paid,
        Refunded
    }

    struct Burn {
        address from;
        BurnState state;
        uint64 blockNumber;
        uint256 amount;
        string moneroAddress;
    }

    uint256 public totalSupply;
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;
    address public owner;
    address public minter;

    uint256 public dailyMintLimit;
    uint256 public mintWindowStart;
    uint256 public mintedInWindow;

    mapping(bytes32 => bool) private _depositMinted;
    Burn[] public burns;

    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);
    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);
    event MinterChanged(address indexed previousMinter, address indexed newMinter);
    event DailyMintLimitChanged(uint256 previousLimit, uint256 newLimit);
    event MintedFromMonero(address indexed to, uint256 amount, bytes32 indexed moneroTxId, uint32 subaddressIndex);
    event BurnedToMonero(uint256 indexed burnId, address indexed from, uint256 amount, string moneroAddress);
    event BurnPaid(uint256 indexed burnId, bytes32 moneroTxId);
    event BurnRefunded(uint256 indexed burnId, address indexed to, uint256 amount);

    /// @param minter_ the relayer's ETC address
    /// @param dailyMintLimit_ most EXMR (raw units, 1e12 per XMR) the minter can mint per window
    constructor(address minter_, uint256 dailyMintLimit_) {
        owner = msg.sender;
        emit OwnershipTransferred(address(0), msg.sender);
        minter = minter_;
        emit MinterChanged(address(0), minter_);
        dailyMintLimit = dailyMintLimit_;
        emit DailyMintLimitChanged(0, dailyMintLimit_);
    }

    modifier onlyOwner() {
        require(msg.sender == owner, "not owner");
        _;
    }

    modifier onlyMinter() {
        require(msg.sender == minter, "not minter");
        _;
    }

    function transferOwnership(address next) external onlyOwner {
        require(next != address(0), "zero owner");
        emit OwnershipTransferred(owner, next);
        owner = next;
    }

    /// @notice Replace the relayer key. address(0) stops all minting and settling.
    function setMinter(address next) external onlyOwner {
        emit MinterChanged(minter, next);
        minter = next;
    }

    function setDailyMintLimit(uint256 next) external onlyOwner {
        emit DailyMintLimitChanged(dailyMintLimit, next);
        dailyMintLimit = next;
    }

    // ---------- XMR -> EXMR ----------

    /// @notice Mint EXMR for a Monero deposit that reached the vault. Each
    ///         (moneroTxId, subaddressIndex) pair can be minted once.
    /// @param moneroTxId the Monero transaction that paid the vault
    /// @param subaddressIndex the vault subaddress it paid; each ETC user has their own
    function mintFromMonero(address to, uint256 amount, bytes32 moneroTxId, uint32 subaddressIndex)
        external
        onlyMinter
    {
        bytes32 key = keccak256(abi.encodePacked(moneroTxId, subaddressIndex));
        require(!_depositMinted[key], "deposit already minted");
        require(amount > 0, "zero amount");
        _depositMinted[key] = true;
        if (block.timestamp >= mintWindowStart + MINT_WINDOW) {
            mintWindowStart = block.timestamp;
            mintedInWindow = 0;
        }
        mintedInWindow += amount;
        require(mintedInWindow <= dailyMintLimit, "daily mint limit");
        _mint(to, amount);
        emit MintedFromMonero(to, amount, moneroTxId, subaddressIndex);
    }

    function depositMinted(bytes32 moneroTxId, uint32 subaddressIndex) external view returns (bool) {
        return _depositMinted[keccak256(abi.encodePacked(moneroTxId, subaddressIndex))];
    }

    /// @notice EXMR the minter can still mint before the current window resets.
    function mintHeadroom() external view returns (uint256) {
        if (block.timestamp >= mintWindowStart + MINT_WINDOW) return dailyMintLimit;
        return mintedInWindow >= dailyMintLimit ? 0 : dailyMintLimit - mintedInWindow;
    }

    // ---------- EXMR -> XMR ----------

    /// @notice Burn EXMR to be paid the same amount of XMR, less the Monero network fee.
    /// @param moneroAddress standard, sub- or integrated address (95 or 106 base58 characters)
    /// @return burnId index into `burns`; the relayer settles it with markPaid or refundBurn
    function burnToMonero(uint256 amount, string calldata moneroAddress) external returns (uint256 burnId) {
        require(_looksLikeMoneroAddress(bytes(moneroAddress)), "not a monero address");
        require(amount > 0, "zero amount");
        _burn(msg.sender, amount);
        burnId = burns.length;
        burns.push(
            Burn({
                from: msg.sender,
                state: BurnState.Pending,
                blockNumber: uint64(block.number),
                amount: amount,
                moneroAddress: moneroAddress
            })
        );
        emit BurnedToMonero(burnId, msg.sender, amount, moneroAddress);
    }

    /// @notice Record the Monero transaction that paid a burn.
    function markPaid(uint256 burnId, bytes32 moneroTxId) external onlyMinter {
        require(burnId < burns.length, "no such burn");
        Burn storage b = burns[burnId];
        require(b.state == BurnState.Pending, "not pending");
        b.state = BurnState.Paid;
        emit BurnPaid(burnId, moneroTxId);
    }

    /// @notice Give back a burn the bridge cannot pay (bad address, below the minimum).
    ///         Only the burner gets it back, only the amount burned, only once.
    function refundBurn(uint256 burnId) external onlyMinter {
        require(burnId < burns.length, "no such burn");
        Burn storage b = burns[burnId];
        require(b.state == BurnState.Pending, "not pending");
        b.state = BurnState.Refunded;
        _mint(b.from, b.amount);
        emit BurnRefunded(burnId, b.from, b.amount);
    }

    function burnCount() external view returns (uint256) {
        return burns.length;
    }

    /// @dev Length and alphabet only; the relayer checks the checksum and refunds bad ones.
    ///      Also keeps bytes that aren't valid UTF-8 out of storage and events.
    function _looksLikeMoneroAddress(bytes calldata a) private pure returns (bool) {
        if (a.length != 95 && a.length != 106) return false;
        for (uint256 i; i < a.length; ++i) {
            bytes1 c = a[i];
            bool base58 = (c >= "1" && c <= "9") || (c >= "A" && c <= "Z" && c != "I" && c != "O")
                || (c >= "a" && c <= "z" && c != "l");
            if (!base58) return false;
        }
        return true;
    }

    // ---------- ERC-20 ----------

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
            allowance[from][msg.sender] = allowed - value;
        }
        _transfer(from, to, value);
        return true;
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

    function _mint(address to, uint256 value) internal {
        require(to != address(0), "zero to");
        totalSupply += value;
        balanceOf[to] += value;
        emit Transfer(address(0), to, value);
    }

    function _burn(address from, uint256 value) internal {
        uint256 bal = balanceOf[from];
        require(bal >= value, "balance");
        unchecked {
            balanceOf[from] = bal - value;
            totalSupply -= value;
        }
        emit Transfer(from, address(0), value);
    }
}
