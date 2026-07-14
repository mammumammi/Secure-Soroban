import subprocess
import json
import sys
import os
from datetime import datetime

CONTRACT_ID = os.environ.get("DRAIN_CONTRACT_ID", "CCWEK7ILZYTSCOFMQEQJY5SISXFAXJKM7WGT7247YAMZZYVT2WL2YZ5Z")
TOKEN_ID        = os.environ.get("TOKEN_ID", "CDLZFC3SYJYDZT7K67VZ75HPJVIEUVNIXF47ZG2FB2RMQQVU2HHGCYSC")
VICTIM          = os.environ.get("VICTIM_ADDRESS", "GAPJOEEWW4Y5ASHLRB2XAF6LDVHN5GJQFW4VZDPRDR5JODR3ZNYBFJQD")
ATTACKER        = os.environ.get("ATTACKER_ADDRESS", "GBLUFMJRRZBU7TYPP2KKUCTCFCKIPNYA7ELBRLXTOLOQGY3ZFT3GJA4K")
VICTIM_SECRET   = os.environ.get("VICTIM_SECRET", "")
ATTACKER_SECRET = os.environ.get("ATTACKER_SECRET", "")
NETWORK         = os.environ.get("STELLAR_NETWORK", "testnet")
TEST_AMOUNT     = 100
XLM_PRICE       = 0.12

def run(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout.strip(), result.stderr.strip(), result.returncode

def deposit_funds():
    print(f"\n[*] Depositing {TEST_AMOUNT} XLM into drain contract...")
    cmd = f"""stellar contract invoke \
        --id {CONTRACT_ID} \
        --source {VICTIM_SECRET} \
        --network {NETWORK} \
        -- deposit \
        --from {VICTIM} \
        --token {TOKEN_ID} \
        --amount {TEST_AMOUNT}"""
    out, err, code = run(cmd)
    if code != 0:
        print(f"[-] Deposit failed: {err}")
        sys.exit(1)
    print("[+] Deposit successful")

def get_balance():
    cmd = f"""stellar contract invoke \
        --id {CONTRACT_ID} \
        --source {VICTIM_SECRET} \
        --network {NETWORK} \
        -- balance \
        --token {TOKEN_ID}"""
    out, err, code = run(cmd)
    try:
        return int(out.replace('"', '').strip())
    except:
        return 0

def simulate_drain():
    print("\n[*] Simulating unauthorized emergency_withdraw...")
    cmd = f"""stellar contract invoke \
        --id {CONTRACT_ID} \
        --source {ATTACKER_SECRET} \
        --network {NETWORK} \
        -- emergency_withdraw \
        --to {ATTACKER} \
        --token {TOKEN_ID}"""
    out, err, code = run(cmd)
    return code == 0, out

def generate_report(detected, balance_before, balance_after):
    drained = balance_before - balance_after
    estimated_loss = drained * XLM_PRICE
    
    print("\n" + "=" * 55)
    print("   UNAUTHORIZED DRAIN DETECTION REPORT")
    print("=" * 55)
    
    if detected:
        print("\n   CRITICAL — Unauthorized Drain Detected")
        print(f"\n   Vulnerability : No ownership check in emergency_withdraw()")
        print(f"   Funds Drained : {drained} XLM")
        print(f"   Estimated Loss: ${estimated_loss:.2f} USD")
        print(f"\n   Fix : Store admin address on deploy")
        print(f"         Verify caller with admin.require_auth()")
        print("\n   Status: CRITICAL — PUSH BLOCKED")
    else:
        print("\n   PASS — No Unauthorized Drain Found")
        print("\n   Status: SAFE")
    
    print("=" * 55)
    
    return {
        "check": "unauthorized_drain",
        "detected": detected,
        "severity": "CRITICAL" if detected else "NONE",
        "funds_drained_xlm": drained,
        "estimated_loss_usd": round(estimated_loss, 2),
        "fix": "Add admin.require_auth() to emergency_withdraw()"
    }

if __name__ == "__main__":
    print("Running Unauthorized Drain Detection...")
    deposit_funds()
    balance_before = get_balance()
    print(f"[*] Balance before: {balance_before} XLM")
    detected, _ = simulate_drain()
    balance_after = get_balance()
    print(f"[*] Balance after:  {balance_after} XLM")
    report = generate_report(detected, balance_before, balance_after)
    
    report_dir = os.environ.get("REPORT_DIR", "scripts")
    with open(f"{report_dir}/drain_report.json", "w") as f:
        json.dump(report, f, indent=2)
    
    sys.exit(1 if detected else 0)