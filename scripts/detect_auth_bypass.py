import subprocess
import json
import sys
from datetime import datetime

import os

CONTRACT_ID = os.environ.get("CONTRACT_ID", "CBTJ2VU3VJM3WZU3TZTA6ZVGAEFRUUW6WPCIOCD7DNKL4LPLWW536ZUE")
TOKEN_ID    = os.environ.get("TOKEN_ID", "CDLZFC3SYJYDZT7K67VZ75HPJVIEUVNIXF47ZG2FB2RMQQVU2HHGCYSC")
VICTIM      = os.environ.get("VICTIM_ADDRESS", "GAPJOEEWW4Y5ASHLRB2XAF6LDVHN5GJQFW4VZDPRDR5JODR3ZNYBFJQD")
ATTACKER    = os.environ.get("ATTACKER_ADDRESS", "GBLUFMJRRZBU7TYPP2KKUCTCFCKIPNYA7ELBRLXTOLOQGY3ZFT3GJA4K")
NETWORK     = os.environ.get("STELLAR_NETWORK", "testnet")
TEST_AMOUNT = 100
XLM_PRICE   = 0.12
# ── Helper ─────────────────────────────────────────────────
def run(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout.strip(), result.stderr.strip(), result.returncode

# ── Step 1: Deposit funds as victim ────────────────────────
def deposit_funds():
    print(f"\n[*] Depositing {TEST_AMOUNT} XLM as victim...")
    cmd = f"""stellar contract invoke \
        --id {CONTRACT_ID} \
        --source victim \
        --network {NETWORK} \
        -- deposit \
        --from {VICTIM} \
        --token {TOKEN_ID} \
        --amount {TEST_AMOUNT}"""
    
    out, err, code = run(cmd)
    if code != 0:
        print(f"[-] Deposit failed: {err}")
        sys.exit(1)
    print(f"[+] Deposit successful")
    return True

# ── Step 2: Check balance before attack ────────────────────
def get_balance():
    cmd = f"""stellar contract invoke \
        --id {CONTRACT_ID} \
        --source victim \
        --network {NETWORK} \
        -- balance \
        --token {TOKEN_ID}"""
    
    out, err, code = run(cmd)
    try:
        return int(out.replace('"', '').strip())
    except:
        return 0

# ── Step 3: Simulate the attack ────────────────────────────
def simulate_attack():
    print(f"\n[*] Simulating authorization bypass attack...")
    print(f"[*] Attacker: {ATTACKER}")
    print(f"[*] Target:   {CONTRACT_ID}")
    
    cmd = f"""stellar contract invoke \
        --id {CONTRACT_ID} \
        --source attacker \
        --network {NETWORK} \
        -- withdraw \
        --to {ATTACKER} \
        --token {TOKEN_ID} \
        --amount {TEST_AMOUNT}"""
    
    out, err, code = run(cmd)
    
    # Attack succeeded if exit code is 0
    if code == 0:
        return True, out
    else:
        return False, err

# ── Step 4: Generate report ────────────────────────────────
def generate_report(attack_succeeded, balance_before, balance_after):
    funds_at_risk    = balance_before - balance_after
    usd_loss         = funds_at_risk * XLM_PRICE
    
    print("\n")
    print("=" * 55)
    print("   🛡️  STELLAR SHIELD — SECURITY REPORT")
    print("=" * 55)
    print(f"   Contract  : {CONTRACT_ID[:20]}...")
    print(f"   Network   : {NETWORK}")
    print(f"   Timestamp : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 55)
    
    if attack_succeeded:
        print("\n   🔴 CRITICAL — Authorization Bypass Detected")
        print(f"\n   Vulnerability : Missing require_auth() in withdraw()")
        print(f"   Attack Result : Attacker drained contract successfully")
        print(f"   Funds Drained : {funds_at_risk} XLM")
        print(f"   Estimated Loss: ${usd_loss:.2f} USD")
        print(f"\n   Fix : Add require_auth() to withdraw() function")
        print(f"         Example: to.require_auth();")
        print("\n   Push Status : ❌ BLOCKED")
    else:
        print("\n   ✅ PASS — No Authorization Bypass Found")
        print("\n   Push Status : ✅ SAFE TO DEPLOY")
    
    print("=" * 55)
    
    # Save as JSON for GitHub Action to read
    report = {
        "vulnerability": "authorization_bypass",
        "detected": attack_succeeded,
        "severity": "CRITICAL" if attack_succeeded else "NONE",
        "funds_at_risk_xlm": funds_at_risk,
        "estimated_loss_usd": round(usd_loss, 2),
        "fix": "Add require_auth() to withdraw() function"
    }
    
    with open("report.json", "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"\n   Report saved to report.json")
    return attack_succeeded

# ── Main ───────────────────────────────────────────────────
if __name__ == "__main__":
    print("🛡️  Stellar Shield — Starting Security Scan...")
    
    deposit_funds()
    
    balance_before = get_balance()
    print(f"\n[*] Balance before attack: {balance_before} XLM")
    
    attack_succeeded, output = simulate_attack()
    
    balance_after = get_balance()
    print(f"[*] Balance after attack:  {balance_after} XLM")
    
    vulnerable = generate_report(attack_succeeded, balance_before, balance_after)
    
    # Exit code 1 blocks the GitHub Action
    sys.exit(1 if vulnerable else 0)