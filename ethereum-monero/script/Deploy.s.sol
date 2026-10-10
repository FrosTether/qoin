// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.24;

import "forge-std/Script.sol";
import "../src/EthereumMonero.sol";

contract Deploy is Script {
    function run() external {
        uint256 pk = vm.envUint("PRIVATE_KEY"); // becomes owner: keep it cold
        address minter = vm.envAddress("EXMR_MINTER"); // the relayer's address (BRIDGE_ETC_KEY)
        uint256 dailyMintLimit = vm.envUint("EXMR_DAILY_LIMIT_XMR") * 1e12;
        vm.startBroadcast(pk);
        EthereumMonero token = new EthereumMonero(minter, dailyMintLimit);
        vm.stopBroadcast();
        console2.log("EXMR", address(token));
    }
}
