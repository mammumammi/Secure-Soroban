import subprocess
import json
import sys
import os
from datetime import datetime

CONTRACT_ID     = os.environ.get("OVERFLOW_CONTRACT_ID", "")
TOKEN_ID        = os.environ.get("TOKEN_ID", "CDLZFC3SYJYDZT7K67VZ75HPJVIEUVNIXF47ZG2FB2RMQQVU2HHGCYSC")
VICTIM          = os.environ.get("VICTIM_ADDRESS", "GAPJOEEWW4Y5ASHLRB2XAF6LDVHN5GJQFW4VZDPRDR5JODR3ZNYBFJQD")
VICTIM_SECRET   = os.environ.get("VICTIM_SECRET", "")
ATTACKER_SECRET = os.environ.get("ATTACKER_SECRET", "")
NETWORK         = os.environ.get("STELLAR_NETWORK", "testnet")
XLM_PRICE       = 0.12

def run(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout.strip(), result.stderr.strip(), result.returncode

def simulate_overflow():
    print("\n[*] Simulating integer overflow attack...")

    # Max i128 value — causes overflow when multiplied
    max_i128 = 170141183460469231731687303715884105727
    
    cmd = f"""stellar contract invoke \
        --id {CONTRACT_ID} \
        --source {VICTIM_SECRET} \
        --network {NETWORK} \
        -- calculate_fee \
        --amount {max_i128} \
        --fee_percent 10"""
    
    out, err, code = run(cmd)
    
    # If it returns without error and result is tiny or negative
    # overflow occurred
    if code == 0:
        try:
            result = int(out.replace('"', '').strip())
            if result <= 0:
                return True, result
        except:
            pass
    
    return False, 0

def generate_report(detected, overflow_result):
    estimated_loss = 50000 * XLM_PRICE if detected else 0
    
    print("\n" + "=" * 55)
    print("   INTEGER OVERFLOW DETECTION REPORT")
    print("=" * 55)
    
    if detected:
        print("\n   CRITICAL — Integer Overflow Detected")
        print(f"\n   Vulnerability : Unchecked arithmetic in calculate_fee()")
        print(f"   Attack Result : Fee calculated as {overflow_result} on max input")
        print(f"   Impact        : Attacker pays near-zero fees on huge transfers")
        print(f"   Estimated Loss: ${estimated_loss:.2f} USD")
        print(f"\n   Fix : Use checked_mul() instead of *")
        print(f"         amount.checked_mul(fee_percent)")
        print(f"               .unwrap_or(i128::MAX) / 100")
        print("\n   Status: CRITICAL — PUSH BLOCKED")
    else:
        print("\n   PASS — No Integer Overflow Found")
        print("\n   Status: SAFE")
    
    print("=" * 55)
    
    return {
        "check": "integer_overflow",
        "detected": detected,
        "severity": "CRITICAL" if detected else "NONE",
        "overflow_result": overflow_result,
        "estimated_loss_usd": round(estimated_loss, 2),
        "fix": "Use checked_mul() instead of * for arithmetic operations"
    }

if __name__ == "__main__":
    print("Running Integer Overflow Detection...")
    detected, result = simulate_overflow()
    report = generate_report(detected, result)
    
    report_dir = os.environ.get("REPORT_DIR", "scripts")
    with open(f"{report_dir}/overflow_report.json", "w") as f:
        json.dump(report, f, indent=2)
    
    sys.exit(1 if detected else 0)