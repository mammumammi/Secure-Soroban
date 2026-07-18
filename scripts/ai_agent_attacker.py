import subprocess
import json
import sys
import os
import time
import requests
import glob
from datetime import datetime

# ── Configuration ──────────────────────────────────────────
OLLAMA_URL             = "http://localhost:11434/api/generate"
MODEL                  = "qwen2.5-coder:7b"
CONTRACT_ID            = os.environ.get("CONTRACT_ID", "CBTJ2VU3VJM3WZU3TZTA6ZVGAEFRUUW6WPCIOCD7DNKL4LPLWW536ZUE")
TOKEN_ID               = os.environ.get("TOKEN_ID", "CDLZFC3SYJYDZT7K67VZ75HPJVIEUVNIXF47ZG2FB2RMQQVU2HHGCYSC")
VICTIM                 = os.environ.get("VICTIM_ADDRESS", "GAPJOEEWW4Y5ASHLRB2XAF6LDVHN5GJQFW4VZDPRDR5JODR3ZNYBFJQD")
ATTACKER               = os.environ.get("ATTACKER_ADDRESS", "GBLUFMJRRZBU7TYPP2KKUCTCFCKIPNYA7ELBRLXTOLOQGY3ZFT3GJA4K")
VICTIM_SECRET          = os.environ.get("VICTIM_SECRET", "")
ATTACKER_SECRET        = os.environ.get("ATTACKER_SECRET", "")
NETWORK                = os.environ.get("STELLAR_NETWORK", "testnet")
CONTRACTS_PATH         = os.environ.get("CONTRACTS_PATH", "vulnerable_contracts/escrow/contracts")
RECOVERY_TIMEOUT       = 100
TEST_AMOUNT            = 100
XLM_PRICE              = 0.12

# ── Helper ─────────────────────────────────────────────────
def run(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout.strip(), result.stderr.strip(), result.returncode

# ── Read contract source ────────────────────────────────────
def read_contract_source():
    print("\n[*] Reading contract source code...")
    sources = {}
    rs_files = glob.glob(f"{CONTRACTS_PATH}/**/src/lib.rs", recursive=True)
    for filepath in rs_files:
        contract_name = filepath.split("/")[-3]
        with open(filepath, "r") as f:
            sources[contract_name] = f.read()
        print(f"[+] Loaded: {contract_name}")
    return sources

# ── AI analysis ─────────────────────────────────────────────
def ai_analyze_contract(contract_name, source_code):
    print(f"\n[*] AI Agent analyzing {contract_name}...")

    prompt = f"""You are an expert Soroban smart contract security researcher and attacker.
Analyze this Soroban smart contract written in Rust and identify the most critical vulnerability.

Contract name: {contract_name}
Contract source code:
```rust
{source_code}
```

Respond ONLY with a JSON object in this exact format, no other text:
{{
    "vulnerability_found": true,
    "vulnerability_type": "name of vulnerability",
    "vulnerable_function": "function name",
    "attack_description": "how to exploit it in one sentence",
    "attack_params": {{
        "function_to_call": "function name",
        "caller": "attacker",
        "key_param": "what value to pass"
    }},
    "severity": "CRITICAL",
    "estimated_loss_xlm": 100,
    "fix": "one line fix description"
}}"""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "num_predict": 500
                }
            },
            timeout=120
        )

        if response.status_code == 200:
            raw = response.json()["response"].strip()
            print(f"[+] AI response received")
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(raw[start:end])

        print(f"[-] AI request failed: {response.status_code}")
        return None

    except Exception as e:
        print(f"[-] AI agent error: {e}")
        return None

# ── Get balance ─────────────────────────────────────────────
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

# ── Execute AI attack ───────────────────────────────────────
def execute_ai_attack(analysis):
    if not analysis or not analysis.get("vulnerability_found"):
        print("[*] AI found no vulnerability to exploit")
        return False, 0

    print(f"\n[*] AI identified: {analysis['vulnerability_type']}")
    print(f"[*] Executing attack on: {analysis['vulnerable_function']}")
    print(f"[*] Attack plan: {analysis['attack_description']}")

    print(f"\n[*] Depositing {TEST_AMOUNT} XLM as victim...")
    deposit_cmd = f"""stellar contract invoke \
        --id {CONTRACT_ID} \
        --source {VICTIM_SECRET} \
        --network {NETWORK} \
        -- deposit \
        --from {VICTIM} \
        --token {TOKEN_ID} \
        --amount {TEST_AMOUNT}"""

    out, err, code = run(deposit_cmd)
    if code != 0:
        print(f"[-] Deposit failed: {err}")
        return False, 0
    print(f"[+] Victim deposited {TEST_AMOUNT} XLM")

    balance_before = get_balance()
    print(f"[*] Balance before attack: {balance_before} XLM")

    func = analysis["attack_params"].get("function_to_call", "withdraw")

    print(f"\n[*] AI Agent executing attack as attacker...")
    attack_cmd = f"""stellar contract invoke \
        --id {CONTRACT_ID} \
        --source {ATTACKER_SECRET} \
        --network {NETWORK} \
        -- {func} \
        --to {ATTACKER} \
        --token {TOKEN_ID} \
        --amount {TEST_AMOUNT}"""

    out, err, code = run(attack_cmd)
    attack_succeeded = code == 0

    balance_after = get_balance()
    drained = balance_before - balance_after

    print(f"[*] Balance after attack: {balance_after} XLM")

    if attack_succeeded:
        print(f"\n[!] ATTACK SUCCEEDED — {drained} XLM drained")
    else:
        print(f"\n[*] Attack blocked — contract may be secure")

    return attack_succeeded, drained

# ── Recover funds ───────────────────────────────────────────
def recover_funds(amount):
    print(f"\n[*] Executing fund recovery — returning {amount} XLM to victim...")

    xlm_amount = amount / 10000000

    recovery_cmd = f"""stellar tx new payment \
        --source {ATTACKER_SECRET} \
        --network {NETWORK} \
        --destination {VICTIM} \
        --asset native \
        --amount {xlm_amount}"""

    out, err, code = run(recovery_cmd)

    if code == 0:
        print(f"[+] RECOVERY SUCCESSFUL — {amount} XLM returned to victim")
        try:
            with open("scripts/recovery_task.json", "r") as f:
                task = json.load(f)
            task["status"] = "completed"
            task["completed_at"] = datetime.now().isoformat()
            with open("scripts/recovery_task.json", "w") as f:
                json.dump(task, f, indent=2)
        except:
            pass
    else:
        print(f"[-] Recovery failed: {err}")
        print(f"[-] Manual recovery needed: send {amount} XLM to {VICTIM}")

# ── Schedule fund recovery ──────────────────────────────────
def schedule_fund_recovery(drained_amount):
    if drained_amount <= 0:
        return

    print(f"\n[*] Scheduling fund recovery in {RECOVERY_TIMEOUT} seconds (5 minutes)...")
    print(f"[*] {drained_amount} XLM will be returned to victim account")
    print(f"[*] This is a security simulation — funds are always returned")

    recovery_task = {
        "scheduled_at": datetime.now().isoformat(),
        "recover_at": datetime.fromtimestamp(
            time.time() + RECOVERY_TIMEOUT
        ).isoformat(),
        "amount": drained_amount,
        "from_secret": ATTACKER_SECRET,
        "to_address": VICTIM,
        "token_id": TOKEN_ID,
        "network": NETWORK,
        "status": "pending"
    }

    with open("scripts/recovery_task.json", "w") as f:
        json.dump(recovery_task, f, indent=2)

    print(f"[+] Recovery task saved to scripts/recovery_task.json")
    print(f"\n[*] Waiting {RECOVERY_TIMEOUT} seconds before returning funds...")

    for remaining in range(RECOVERY_TIMEOUT, 0, -30):
        print(f"    Recovery in {remaining} seconds...")
        time.sleep(30)

    recover_funds(drained_amount)

# ── Generate AI report ──────────────────────────────────────
def generate_ai_report(analyses, attack_results):
    total_loss = sum(
        r.get("drained", 0) * XLM_PRICE
        for r in attack_results.values()
    )
    any_critical = any(
        a.get("severity") in ["CRITICAL", "HIGH"]
        for a in analyses.values()
        if a
    )

    print("\n")
    print("=" * 60)
    print("   SECURESOROBAN — AI AGENT SECURITY REPORT")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print(f"   Model Used : {MODEL}")
    print(f"   Mode       : Autonomous Attack Simulation")
    print("=" * 60)

    for contract_name, analysis in analyses.items():
        if not analysis:
            print(f"\n   [SKIP] {contract_name} — AI analysis failed")
            continue

        result = attack_results.get(contract_name, {})
        succeeded = result.get("succeeded", False)
        drained = result.get("drained", 0)

        if analysis.get("vulnerability_found") and succeeded:
            print(f"\n   [AI-CRITICAL] {contract_name}")
            print(f"   Type     : {analysis['vulnerability_type']}")
            print(f"   Function : {analysis['vulnerable_function']}")
            print(f"   Attack   : {analysis['attack_description']}")
            print(f"   Drained  : {drained} XLM (${drained * XLM_PRICE:.2f} USD)")
            print(f"   Fix      : {analysis['fix']}")
        elif analysis.get("vulnerability_found"):
            print(f"\n   [AI-FOUND] {contract_name} — vulnerability identified")
            print(f"   Type     : {analysis['vulnerability_type']}")
            print(f"   Severity : {analysis['severity']}")
        else:
            print(f"\n   [AI-PASS] {contract_name} — no vulnerability found")

    print("\n" + "=" * 60)
    print(f"   TOTAL AI-IDENTIFIED LOSS: ${total_loss:.2f} USD")
    print(f"   PUSH STATUS: {'❌ BLOCKED' if any_critical else '✅ SAFE'}")
    print(f"   FUND RECOVERY: Scheduled 5 minutes after attack")
    print("=" * 60)

    report = {
        "timestamp": datetime.now().isoformat(),
        "model": MODEL,
        "mode": "ai_agent_attack",
        "total_loss_usd": round(total_loss, 2),
        "push_blocked": any_critical,
        "analyses": analyses,
        "attack_results": attack_results,
        "fund_recovery": "scheduled_5_minutes"
    }

    with open("scripts/ai_agent_report.json", "w") as f:
        json.dump(report, f, indent=2)

    print("\n   Report saved to scripts/ai_agent_report.json")
    return any_critical

# ── Main ────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Secure Soroban — AI Agent Attacker Starting...")
    print(f"Model: {MODEL}")
    print("=" * 60)

    sources = read_contract_source()

    if not sources:
        print("[-] No contract source files found")
        sys.exit(1)

    analyses = {}
    attack_results = {}
    total_drained = 0

    target_contract = "hello-world"

    if target_contract in sources:
        analysis = ai_analyze_contract(target_contract, sources[target_contract])
        analyses[target_contract] = analysis

        if analysis:
            print(f"\n[*] AI Analysis Result:")
            print(f"    Vulnerability: {analysis.get('vulnerability_type', 'None')}")
            print(f"    Severity: {analysis.get('severity', 'None')}")
            print(f"    Attack Plan: {analysis.get('attack_description', 'None')}")

            succeeded, drained = execute_ai_attack(analysis)
            attack_results[target_contract] = {
                "succeeded": succeeded,
                "drained": drained
            }
            total_drained += drained

    for name, source in sources.items():
        if name != target_contract:
            analysis = ai_analyze_contract(name, source)
            analyses[name] = analysis
            attack_results[name] = {"succeeded": False, "drained": 0}

    blocked = generate_ai_report(analyses, attack_results)

    if total_drained > 0:
        schedule_fund_recovery(total_drained)

    sys.exit(1 if blocked else 0)