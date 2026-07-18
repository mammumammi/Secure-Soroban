# SecureSoroban

> Automated smart contract attack simulator for the Stellar ecosystem — built as a GitHub Actions workflow.

SecureSoroban dynamically simulates real attack vectors against your Soroban smart contracts on every push, catches vulnerabilities before they reach mainnet, calculates estimated financial loss in XLM and USD, and blocks deployment automatically if critical issues are found.

Built at **Stellar Build Station Kerala 2026**.

---

## The Problem

Every Soroban smart contract pushed to GitHub today ships without a security net. One logical flaw can drain an entire contract's funds in seconds — and nobody catches it until it's too late.

Existing tools like Scout for Soroban provide **static analysis only** — they read your code and flag patterns. SecureSoroban goes further: it **deploys your contract, runs real exploits against it, confirms what actually breaks, and tells you exactly how much you would have lost.**

---

## What It Detects

| Attack Vector | Type | Severity |
|---|---|---|
| Authorization Bypass | Dynamic | CRITICAL |
| Unauthorized Drain | Dynamic | CRITICAL |
| Multisig Signer Manipulation | Dynamic | CRITICAL |
| Reentrancy Pattern | Static + Dynamic | HIGH |
| Integer Overflow | Static | HIGH |
| Unchecked Arithmetic | Static | HIGH |
| Missing Input Validation | Static | MEDIUM |

---

## How It Works

---

## Quick Start

Add to your `.github/workflows/security.yml`:

```yaml
name: SecureSoroban Security Scan

on: [push, pull_request]

jobs:
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Build Soroban contract
        run: |
          rustup target add wasm32v1-none
          stellar contract build

      - name: Run SecureSoroban
        uses: mammumammi/secure-soroban@v1
        with:
          victim-secret: ${{ secrets.VICTIM_SECRET }}
          attacker-secret: ${{ secrets.ATTACKER_SECRET }}
          victim-address: ${{ secrets.VICTIM_ADDRESS }}
          attacker-address: ${{ secrets.ATTACKER_ADDRESS }}
          token-id: ${{ secrets.TOKEN_ID }}
```

---

## Setup — 5 Minutes

**1. Create testnet accounts:**
```bash
stellar keys generate victim --network testnet
stellar keys generate attacker --network testnet
stellar keys fund victim --network testnet
stellar keys fund attacker --network testnet
```

**2. Get your addresses and secrets:**
```bash
stellar keys address victim
stellar keys address attacker
stellar keys secret victim
stellar keys secret attacker
stellar contract id asset --asset native --network testnet --source victim
```

**3. Add GitHub secrets to your repo:**

Go to Settings → Secrets and Variables → Actions and add:

| Secret | Value |
|---|---|
| VICTIM_SECRET | Output of `stellar keys secret victim` |
| ATTACKER_SECRET | Output of `stellar keys secret attacker` |
| VICTIM_ADDRESS | Output of `stellar keys address victim` |
| ATTACKER_ADDRESS | Output of `stellar keys address attacker` |
| TOKEN_ID | Output of `stellar contract id asset` command |

**4. Push your contract and watch it run.**

---

## Example Report Output

---

## AI Agent (Pro Feature)

SecureSoroban includes a local AI agent powered by **qwen2.5-coder:7b** running via Ollama that:

- Reads your specific contract source code
- Reasons about contract-specific vulnerabilities
- Generates and executes targeted attacks
- Returns drained funds to victim account after 5 minutes automatically

**Run locally:**
```bash
# Install Ollama
brew install ollama
ollama pull qwen2.5-coder:7b

# Run AI agent
python3 scripts/ai_agent_attacker.py
```

---

## Architecture
---

## Why SecureSoroban

| | Scout for Soroban | SecureSoroban |
|---|---|---|
| Analysis type | Static only | Dynamic + Static |
| Executes real exploits | ❌ | ✅ |
| Financial impact | ❌ | ✅ XLM + USD |
| GitHub workflow | Basic | Native, blocks push |
| AI agent | ❌ | ✅ Local Ollama |
| Multisig attacks | ❌ | ✅ (v2) |
| Cost | Free | Free |

---

## Roadmap

- ✅ v1.0 — Authorization bypass, unauthorized drain, reentrancy, integer overflow, static analysis
- ✅ v1.1 — AI agent with local Ollama and 5 minute fund recovery
- 🔄 v2.0 — Multisig signer manipulation attacks
- 📋 v2.1 — Storage exhaustion attacks
- 📋 v3.0 — AI agent writes custom Rust attack contracts per deployment

---

## Disclaimer

SecureSoroban is a security research tool. All attack simulations run against deliberately vulnerable contracts on Stellar testnet. No real funds are ever at risk. All simulated drained funds are automatically returned after 5 minutes.

---

## License

MIT — free to use, modify, and distribute.

---

*Built by Aashin Mammu at Stellar Build Station Kerala 2026*