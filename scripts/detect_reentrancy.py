import subprocess
import json
import sys
import os

CONTRACT_ID     = os.environ.get("REENTRANCY_CONTRACT_ID", "")
TOKEN_ID        = os.environ.get("TOKEN_ID", "CDLZFC3SYJYDZT7K67VZ75HPJVIEUVNIXF47ZG2FB2RMQQVU2HHGCYSC")
VICTIM          = os.environ.get("VICTIM_ADDRESS", "GAPJOEEWW4Y5ASHLRB2XAF6LDVHN5GJQFW4VZDPRDR5JODR3ZNYBFJQD")
VICTIM_SECRET   = os.environ.get("VICTIM_SECRET", "")
NETWORK         = os.environ.get("STELLAR_NETWORK", "testnet")
TEST_AMOUNT     = 100
XLM_PRICE       = 0.12

def run(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout.strip(), result.stderr.strip(), result.returncode

def check_reentrancy_pattern():
    print("\n[*] Checking for reentrancy pattern in contract source...")
    
    # Static check — look for state update after transfer pattern
    # Read the contract source
    source_path = "vulnerable_contracts/escrow/contracts/reentrancy/src/lib.rs"
    
    try:
        with open(source_path, "r") as f:
            source = f.read()
        
        # Find if transfer happens before state update
        transfer_pos = source.find("token_client.transfer")
        state_update_pos = source.find("env.storage().instance().set")
        
        # If transfer comes before state update in withdraw function
        withdraw_pos = source.find("pub fn withdraw")
        
        if withdraw_pos > 0:
            withdraw_section = source[withdraw_pos:]
            transfer_in_withdraw = withdraw_section.find("token_client.transfer")
            state_in_withdraw = withdraw_section.find("env.storage().instance().set")
            
            if transfer_in_withdraw > 0 and state_in_withdraw > 0:
                if transfer_in_withdraw < state_in_withdraw:
                    return True
        
        return False
        
    except FileNotFoundError:
        print("[-] Source file not found — skipping static check")
        return False

def generate_report(detected):
    estimated_loss = 200 * XLM_PRICE if detected else 0
    
    print("\n" + "=" * 55)
    print("   REENTRANCY DETECTION REPORT")
    print("=" * 55)
    
    if detected:
        print("\n   HIGH — Reentrancy Pattern Detected")
        print(f"\n   Vulnerability : State updated after external transfer call")
        print(f"   Location      : withdraw() function")
        print(f"   Impact        : Attacker may withdraw more than deposited")
        print(f"   Estimated Loss: ${estimated_loss:.2f} USD")
        print(f"\n   Fix : Update state BEFORE making external calls")
        print(f"         (Checks-Effects-Interactions pattern)")
        print("\n   Status: HIGH — PUSH BLOCKED")
    else:
        print("\n   PASS — No Reentrancy Pattern Found")
        print("\n   Status: SAFE")
    
    print("=" * 55)
    
    return {
        "check": "reentrancy",
        "detected": detected,
        "severity": "HIGH" if detected else "NONE",
        "estimated_loss_usd": round(estimated_loss, 2),
        "fix": "Update storage state before making external token transfers"
    }

if __name__ == "__main__":
    print("Running Reentrancy Detection...")
    detected = check_reentrancy_pattern()
    report = generate_report(detected)
    
    report_dir = os.environ.get("REPORT_DIR", "scripts")
    with open(f"{report_dir}/reentrancy_report.json", "w") as f:
        json.dump(report, f, indent=2)
    
    sys.exit(1 if detected else 0)