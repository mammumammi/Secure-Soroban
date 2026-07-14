# Stellar Shield

Automated smart contract security scanner for Soroban contracts on Stellar.

Stellar Shield runs as a GitHub Actions workflow that automatically 
simulates attack vectors against your Soroban smart contracts on every 
push — catching vulnerabilities before they reach mainnet.

## What It Detects
- Authorization Bypass (Missing require_auth())
- More attack vectors coming in v2

## How It Works
1. Developer pushes Soroban contract code
2. Stellar Shield deploys contract to Stellar testnet sandbox
3. Simulates real attack against the contract
4. Calculates estimated financial loss in XLM and USD
5. Blocks the push if critical vulnerabilities found
6. Posts full security report to the PR

## Setup
Add to your .github/workflows/stellar-shield.yml:
(paste your workflow yaml here)

Add secrets to your GitHub repo:
- VICTIM_SECRET — funded testnet account secret key
- ATTACKER_SECRET — attacker testnet account secret key

## Demo
(add a screenshot of the blocked push output here)

## Roadmap
- v1: Authorization bypass detection (done)
- v2: Integer overflow detection
- v2: Reentrancy simulation  
- Pro: AI agent generates contract-specific attack scripts