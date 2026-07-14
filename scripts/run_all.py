import subprocess
import json
import sys
import os
from datetime import datetime

VICTIM_SECRET       = os.environ.get("VICTIM_SECRET", "")
ATTACKER_SECRET     = os.environ.get("ATTACKER_SECRET", "")
TOKEN_ID            = os.environ.get("TOKEN_ID", "CDLZFC3SYJYDZT7K67VZ75HPJVIEUVNIXF47ZG2FB2RMQQVU2HHGCYSC")
VICTIM              = os.environ.get("VICTIM_ADDRESS", "GAPJOEEWW4Y5ASHLRB2XAF6LDVHN5GJQFW4VZDPRDR5JODR3ZNYBFJQD")
ATTACKER            = os.environ.get("ATTACKER_ADDRESS", "GBLUFMJRRZBU7TYPP2KKUCTCFCKIPNYA7ELBRLXTOLOQGY3ZFT3GJA4K")
NETWORK             = os.environ.get("STELLAR_NETWORK", "testnet")

# Hardcoded deployed contract IDs
AUTH_CONTRACT_ID    = os.environ.get("AUTH_CONTRACT_ID",      "CBTJ2VU3VJM3WZU3TZTA6ZVGAEFRUUW6WPCIOCD7DNKL4LPLWW536ZUE")
DRAIN_CONTRACT_ID   = os.environ.get("DRAIN_CONTRACT_ID",     "CCWEK7ILZYTSCOFMQEQJY5SISXFAXJKM7WGT7247YAMZZYVT2WL2YZ5Z")
OVERFLOW_CONTRACT_ID= os.environ.get("OVERFLOW_CONTRACT_ID",  "CCPN3X25DKVUCIYHUTMUM4YI5LZBGOUHQ6VDDVXBNZ32WM7YIHJXTWLJ")
REENTRANCY_CONTRACT_ID = os.environ.get("REENTRANCY_CONTRACT_ID", "CCC5TMGGNHVQG2PH7PZ3BBLQKKBPAEJICGETSRJ7QNJUYEB7R5N4NDGV")

def run(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout.strip(), result.stderr.strip(), result.returncode

def load_report(filename):
    try:
        with open(filename, "r") as f:
            return json.load(f)
    except:
        return {"detected": False, "severity": "NONE", "estimated_loss_usd": 0}

def print_final_report(reports):
    total_loss = sum(r.get("estimated_loss_usd", 0) for r in reports.values())
    critical_found = any(
        r.get("severity") in ["CRITICAL", "HIGH"]
        for r in reports.values()
    )

    print("\n")
    print("=" * 60)
    print("   STELLAR SHIELD — FULL SECURITY REPORT")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    checks = {
        "auth_bypass":        ("Authorization Bypass",  "scripts/report.json"),
        "integer_overflow":   ("Integer Overflow",      "scripts/overflow_report.json"),
        "unauthorized_drain": ("Unauthorized Drain",    "scripts/drain_report.json"),
        "reentrancy":         ("Reentrancy Pattern",    "scripts/reentrancy_report.json"),
        "static_analysis":    ("Static Analysis",       "scripts/static_report.json"),
    }

    for key, (label, filename) in checks.items():
        r = reports.get(key, {})
        detected = r.get("detected", False)
        severity = r.get("severity", "NONE")
        loss = r.get("estimated_loss_usd", 0)

        if detected:
            icon = severity
            print(f"\n   [{icon}] {label}")
            print(f"           Loss: ${loss:.2f} USD")
            fix = r.get("fix", "")
            if fix:
                print(f"           Fix:  {fix}")
        else:
            print(f"\n   [PASS] {label}")

    print("\n" + "=" * 60)
    print(f"   TOTAL FUNDS AT RISK: ${total_loss:.2f} USD")
    print(f"   PUSH STATUS: {'BLOCKED' if critical_found else 'SAFE TO DEPLOY'}")
    print("=" * 60)

    combined = {
        "timestamp": datetime.now().isoformat(),
        "total_loss_usd": round(total_loss, 2),
        "push_blocked": critical_found,
        "checks": reports
    }

    with open("scripts/combined_report.json", "w") as f:
        json.dump(combined, f, indent=2)

    return critical_found

if __name__ == "__main__":
    print("STELLAR SHIELD — Full Security Scan Starting...")
    print("=" * 60)

    env_vars = {
        **os.environ,
        "CONTRACT_ID":             AUTH_CONTRACT_ID,
        "DRAIN_CONTRACT_ID":       DRAIN_CONTRACT_ID,
        "OVERFLOW_CONTRACT_ID":    OVERFLOW_CONTRACT_ID,
        "REENTRANCY_CONTRACT_ID":  REENTRANCY_CONTRACT_ID,
        "TOKEN_ID":                TOKEN_ID,
        "VICTIM_ADDRESS":          VICTIM,
        "ATTACKER_ADDRESS":        ATTACKER,
        "VICTIM_SECRET":           VICTIM_SECRET,
        "ATTACKER_SECRET":         ATTACKER_SECRET,
        "STELLAR_NETWORK":         NETWORK,
        "CONTRACTS_PATH":          "vulnerable_contracts/escrow/contracts"
    }

    scripts = [
        ("auth_bypass",        "scripts/detect_auth_bypass.py"),
        ("unauthorized_drain", "scripts/detect_unauthorized_drain.py"),
        ("integer_overflow",   "scripts/detect_integer_overflow.py"),
        ("reentrancy",         "scripts/detect_reentrancy.py"),
        ("static_analysis",    "scripts/detect_static.py"),
    ]

    for key, script in scripts:
        print(f"\n{'='*60}")
        print(f"Running: {script}")
        subprocess.run(["python3", script], env=env_vars, capture_output=False)

    reports = {
        "auth_bypass":        load_report("scripts/report.json"),
        "unauthorized_drain": load_report("scripts/drain_report.json"),
        "integer_overflow":   load_report("scripts/overflow_report.json"),
        "reentrancy":         load_report("scripts/reentrancy_report.json"),
        "static_analysis":    load_report("scripts/static_report.json"),
    }

    blocked = print_final_report(reports)
    sys.exit(1 if blocked else 0)