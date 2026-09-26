# Security

## What this project is not

Qoin Maker is a **code generator**. It does not custody keys, does not run a
chain, and does not take a fee on tokens you deploy.

## Reporting a generator bug

Open a private advisory or an issue titled `SECURITY` if you find:

- a template that can lock user funds unexpectedly
- an injection path from `--name` / `--symbol` into Solidity
- a license bypass that is accidental (not "I disagree with pricing")

Do not file issues asking for honeypot, tax-on-transfer, or blacklist-drain
templates. Those requests will be closed.

## Deployer checklist

1. Read the generated `src/*.sol` line by line.
2. Confirm `decimals`, supply math, and cap.
3. If mintable, decide whether you will later call `transferOwnership`.
4. Test on a public testnet.
5. Pay for an independent audit if the token will have real users.
6. Store the deployer key as if it were a root password.

## Supply-chain

Pin your own compiler version. The default template targets `solc 0.8.24`.
