// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.24;

import "forge-std/Script.sol";
import "../src/GCIICoin.sol";

contract Deploy is Script {
    function run() external {
        uint256 pk = vm.envUint("PRIVATE_KEY");
        vm.startBroadcast(pk);
        GCIICoin token = new GCIICoin();
        vm.stopBroadcast();
        console2.log("token", address(token));
    }
}
