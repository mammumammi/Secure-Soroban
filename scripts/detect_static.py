import json
import sys
import os
import glob

CONTRACTS_PATH = os.environ.get("CONTRACTS_PATH", "vulnerable_contracts/escrow/contracts")
XLM_PRICE      = 0.12

def scan_file(filepath):
    findings = []
    
    with open(filepath, "r") as f:
        lines = f.readlines()
    
    for i, line in enumerate(lines, 1):
        # Check 1 — unchecked arithmetic
        if " * " in line and "checked_mul" not in line and "//" not in line.split("*")[0]:
            findings.append({
                "line": i,
                "code": line.strip(),
                "issue": "Unchecked multiplication — use checked_mul()",
                "severity": "HIGH"
            })
        
        # Check 2 — missing require_auth pattern
        if "pub fn" in line and "require_auth" not in line:
            func_name = line.strip()
            findings.append({
                "line": i,
                "code": func_name,
                "issue": "Public function — verify require_auth() is called inside",
                "severity": "MEDIUM"
            })
        
        # Check 3 — unwrap without handling
        if ".unwrap()" in line and "unwrap_or" not in line:
            findings.append({
                "line": i,
                "code": line.strip(),
                "issue": "Unsafe unwrap() — use unwrap_or() or handle the error",
                "severity": "MEDIUM"
            })
    
    return findings

def run_static_scan():
    print("\n[*] Running static analysis on all contracts...")
    
    all_findings = {}
    rs_files = glob.glob(f"{CONTRACTS_PATH}/**/src/lib.rs", recursive=True)
    
    for filepath in rs_files:
        contract_name = filepath.split("/")[-3]
        findings = scan_file(filepath)
        if findings:
            all_findings[contract_name] = findings
            print(f"\n[!] {contract_name}: {len(findings)} issues found")
            for f in findings:
                print(f"    Line {f['line']} [{f['severity']}]: {f['issue']}")
        else:
            print(f"[+] {contract_name}: Clean")
    
    return all_findings

def generate_report(all_findings):
    total = sum(len(v) for v in all_findings.values())
    critical = sum(1 for findings in all_findings.values() 
                  for f in findings if f["severity"] == "CRITICAL")
    high = sum(1 for findings in all_findings.values() 
              for f in findings if f["severity"] == "HIGH")
    
    estimated_loss = (critical * 5000 + high * 1000) * XLM_PRICE
    detected = total > 0
    
    print("\n" + "=" * 55)
    print("   STATIC ANALYSIS REPORT")
    print("=" * 55)
    print(f"\n   Files Scanned : {len(all_findings)} contracts")
    print(f"   Total Issues  : {total}")
    print(f"   High Severity : {high}")
    print(f"   Estimated Loss: ${estimated_loss:.2f} USD")
    print("\n   Status: " + ("ISSUES FOUND — REVIEW REQUIRED" if detected else "CLEAN"))
    print("=" * 55)
    
    return {
        "check": "static_analysis",
        "detected": detected,
        "severity": "HIGH" if high > 0 else "MEDIUM" if total > 0 else "NONE",
        "total_issues": total,
        "findings": all_findings,
        "estimated_loss_usd": round(estimated_loss, 2),
        "fix": "Review all flagged lines and apply suggested fixes"
    }

if __name__ == "__main__":
    print("Running Static Analysis...")
    findings = run_static_scan()
    report = generate_report(findings)
    
    report_dir = os.environ.get("REPORT_DIR", "scripts")
    with open(f"{report_dir}/static_report.json", "w") as f:
        json.dump(report, f, indent=2)
    
    sys.exit(1 if report["detected"] else 0)