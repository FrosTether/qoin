// Build the Merkle root + per-address proofs for FrostAirdrop.
//
// Usage:
//   npm init -y && npm i @openzeppelin/merkle-tree
//   node scripts/build_airdrop.mjs allowlist.csv
//
// allowlist.csv format (one row per recipient, no header needed):
//   0xabc...,1000000000000000000        <- address, amount in WEI (18 decimals)
//
// Output:
//   airdrop-tree.json   full tree (keep private-ish; it's derivable from the CSV)
//   airdrop-root.txt    the Merkle root -> pass to the FrostAirdrop constructor
//   airdrop-claims.json { address: { amount, proof } } -> ship to your claim UI
//
// The leaf types ["address","uint256"] match FrostAirdrop.sol exactly.

import fs from "node:fs";
import { StandardMerkleTree } from "@openzeppelin/merkle-tree";

const csvPath = process.argv[2] || "allowlist.csv";
const raw = fs.readFileSync(csvPath, "utf8").trim();

const rows = [];
const seen = new Set();
for (const [i, line] of raw.split(/\r?\n/).entries()) {
  const t = line.trim();
  if (!t || t.startsWith("#")) continue;
  const [addrRaw, amountRaw] = t.split(",").map((s) => s.trim());
  const addr = addrRaw.toLowerCase();
  if (!/^0x[0-9a-f]{40}$/.test(addr)) throw new Error(`row ${i + 1}: bad address "${addrRaw}"`);
  if (!/^\d+$/.test(amountRaw)) throw new Error(`row ${i + 1}: amount must be an integer in wei, got "${amountRaw}"`);
  if (seen.has(addr)) throw new Error(`row ${i + 1}: duplicate address ${addr}`);
  seen.add(addr);
  rows.push([addrRaw, amountRaw]); // keep original checksum casing for the tree
}
if (rows.length === 0) throw new Error("no rows found");

const tree = StandardMerkleTree.of(rows, ["address", "uint256"]);

const claims = {};
let total = 0n;
for (const [i, value] of tree.entries()) {
  const [address, amount] = value;
  claims[address] = { amount, proof: tree.getProof(i) };
  total += BigInt(amount);
}

fs.writeFileSync("airdrop-tree.json", JSON.stringify(tree.dump(), null, 2));
fs.writeFileSync("airdrop-root.txt", tree.root + "\n");
fs.writeFileSync("airdrop-claims.json", JSON.stringify(claims, null, 2));

console.log(`recipients : ${rows.length}`);
console.log(`total pool : ${total} wei  (${Number(total / 10n ** 15n) / 1000} whole tokens)`);
console.log(`merkle root: ${tree.root}`);
console.log("wrote airdrop-root.txt, airdrop-claims.json, airdrop-tree.json");
console.log("\nFund the FrostAirdrop contract with at least the total pool above before anyone claims.");
